const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require(process.env.DADOK_TEST_JSDOM || 'jsdom');
const root = path.resolve(__dirname, '..');
const response = (data, status = 200) => ({ok: status >= 200 && status < 300, status, json: async () => data});
async function mount(page, handler, now) {
  const dom = new JSDOM(fs.readFileSync(path.join(root, 'screen', page + '.html'), 'utf8'),
    {url: 'http://localhost/screen/' + page + '.html', runScripts: 'outside-only'});
  const w = dom.window;
  await new Promise(r => w.addEventListener('load', r, {once: true}));
  const calls = [], charts = [], alerts = [];
  if (now) {
    const OriginalDate = w.Date;
    w.Date = class extends OriginalDate {
      constructor(...args) { super(...(args.length ? args : [now])); }
      static now() { return new OriginalDate(now).getTime(); }
    };
  }
  w.localStorage.setItem('token', 'access');
  w.alert = value => alerts.push(value);
  w.HTMLCanvasElement.prototype.getContext = function () { return this; };
  w.Chart = function (canvas, config) { charts.push({id: canvas.id, config}); this.destroy = () => {}; };
  w.Headers = Headers;
  w.fetch = async (url, options = {}) => { calls.push({url, ...options}); return handler(url, options); };
  for (const file of ['security.js', 'api.js', page + '.js']) {
    w.eval(fs.readFileSync(path.join(root, 'scripts', file), 'utf8'));
  }
  w.document.dispatchEvent(new w.Event('DOMContentLoaded'));
  const flush = async () => { for (let i=0; i<8; i++) await new Promise(r => setImmediate(r)); };
  await flush();
  return {dom, w, d: w.document, calls, charts, alerts, flush};
}
function currentPeriod() {
  const parts = new Intl.DateTimeFormat('en-US', {timeZone: 'Asia/Seoul', year: 'numeric', month: 'numeric'}).formatToParts(new Date());
  return {year: Number(parts.find(p => p.type === 'year').value), month: Number(parts.find(p => p.type === 'month').value)};
}
function zeroData(url) {
  const query = new URL(url, 'http://localhost').searchParams;
  const year = Number(query.get('year'));
  return response({year, month: query.has('month') ? Number(query.get('month')) : null, goal_id: null,
    goal_books: 0, read_books: 0, progress: 0,
    monthly_reading: Object.fromEntries(Array.from({length: 12}, (_, i) => [`${year}-${String(i+1).padStart(2,'0')}`,0]))});
}
test('목표 화면은 현재 서울 연도·월을 명시하고 실제 0과 기록일 기준을 표시한다', async () => {
  const m = await mount('goals', async url => zeroData(url));
  const period = currentPeriod();
  assert.ok(m.calls.length >= 3);
  assert.ok(m.calls.every(c => new URL(c.url, 'http://localhost').searchParams.get('year') === String(period.year)));
  assert.ok(m.calls.some(c => new URL(c.url, 'http://localhost').searchParams.get('month') === String(period.month)));
  assert.equal(m.d.querySelector('#goal-target').textContent, '0 권');
  assert.equal(m.d.querySelector('#goal-progress').textContent, '0 권');
  assert.match(m.d.querySelector('#statistics-basis').textContent, /리뷰 기록일/);
  assert.match(m.d.querySelector('#statistics-basis').textContent, /완독일.*아님/);
  assert.deepEqual(Array.from(m.charts.find(c => c.id === 'goalChart').config.data.datasets[0].data), [0,0]);
  assert.equal(m.charts.find(c => c.id === 'monthlyChart').config.data.datasets[0].data.length, 12);
  m.dom.window.close();
});

test('연간 신규 생성·월간 수정은 명시 기간과 목표만 저장하며 counter를 제출하지 않는다', async () => {
  let annual = null, monthly = {id: 55, total_books: 2};
  const m = await mount('goals', async (url, options) => {
    const params = new URL(url, 'http://localhost').searchParams;
    if (options.method) {
      const payload = JSON.parse(options.body);
      if (params.has('month')) monthly = {id: 55, total_books: payload.total_books};
      else annual = {id: 101, total_books: payload.total_books};
      return response(params.has('month') ? monthly : annual, options.method === 'POST' ? 201 : 200);
    }
    const data = await zeroData(url).json();
    if (url.includes('/progress/')) {
      const goal = params.has('month') ? monthly : annual;
      if (goal) {data.goal_id = goal.id; data.goal_books = goal.total_books;}
    }
    return response(data);
  });
  m.d.querySelector('#annual-goal-input').value = '12';
  m.d.querySelector('#save-annual-goal').click(); await m.flush();
  const annualCall = m.calls.find(c => c.method === 'POST');
  assert.ok(annualCall);
  assert.deepEqual(JSON.parse(annualCall.body), {year: currentPeriod().year, month: null, total_books: 12});
  assert.equal(m.d.querySelector('#goal-target').textContent, '12 권');
  m.d.querySelector('#monthly-goal-input').value = '4';
  m.d.querySelector('#save-monthly-goal').click(); await m.flush();
  const monthlyCall = m.calls.find(c => c.method === 'PATCH');
  assert.ok(monthlyCall.url.includes('/goal/55/'));
  assert.deepEqual(JSON.parse(monthlyCall.body), {total_books: 4});
  assert.equal(new URL(monthlyCall.url,'http://localhost').searchParams.get('month'), String(currentPeriod().month));
  assert.equal(m.d.querySelector('#monthly-goal-target').textContent, '4 권');
  const count = m.calls.filter(c => c.method).length;
  for (const value of ['0', '-3', '1.5', '']) {
    m.d.querySelector('#annual-goal-input').value = value;
    m.d.querySelector('#save-annual-goal').click(); await m.flush();
  }
  assert.equal(m.calls.filter(c => c.method).length, count);
  m.dom.window.close();
});

test('내 정보 연간 목표는 legacy를 올해로 해석하지 않고 새 기간을 생성한다', async () => {
  let current = null;
  const old = {id: 8, total_books: 77, year: null, month: null};
  const m = await mount('mypage', async (url, options) => {
    if (url.includes('/me/')) return response({nickname: '독자', email: 'reader@example.test'});
    if (options.method) {
      current = {id: 9, ...JSON.parse(options.body)};
      return response(current, 201);
    }
    return response(current ? [old, current] : [old]);
  });
  const firstGoal = m.calls.find(c => c.url.includes('/api/goal/goal/'));
  assert.equal(new URL(firstGoal.url,'http://localhost').searchParams.get('year'), String(currentPeriod().year));
  assert.equal(m.d.querySelector('#goal-input').value, '');
  m.d.querySelector('#goal-input').value = '15';
  m.d.querySelector('.set-goal-btn').click(); await m.flush();
  const write = m.calls.find(c => c.method);
  assert.equal(write.method, 'POST');
  assert.deepEqual(JSON.parse(write.body), {total_books: 15, year: currentPeriod().year, month: null});
  assert.equal(m.d.querySelector('#goal-input').value, '15');
  assert.ok(m.alerts.some(value => /저장/.test(value)));
  m.dom.window.close();
});

test('내 정보 기존 현재연도 목표 수정은 해당 ID만 사용하고 소수 입력을 거부한다', async () => {
  let goal = {id: 21, total_books: 6, year: currentPeriod().year, month: null};
  const m = await mount('mypage', async (url, options) => {
    if (url.includes('/me/')) return response({nickname: '독자', email: 'reader@example.test'});
    if (options.method) {goal.total_books = JSON.parse(options.body).total_books; return response(goal);}
    return response([{id: 5, total_books: 99, year: currentPeriod().year - 1, month: null}, goal]);
  });
  assert.equal(m.d.querySelector('#goal-input').value, '6');
  m.d.querySelector('#goal-input').value = '1.5';
  m.d.querySelector('.set-goal-btn').click(); await m.flush();
  assert.equal(m.calls.filter(c => c.method).length, 0);
  m.d.querySelector('#goal-input').value = '8';
  m.d.querySelector('.set-goal-btn').click(); await m.flush();
  const write = m.calls.find(c => c.method);
  assert.equal(write.method, 'PATCH');
  assert.ok(write.url.includes('/goal/21/'));
  assert.deepEqual(JSON.parse(write.body), {total_books: 8});
  m.dom.window.close();
});

test('UTC 연말이어도 서울의 새해·1월 기간을 사용한다', async () => {
  const m = await mount('goals', async url => zeroData(url), '2026-12-31T15:30:00Z');
  assert.equal(m.d.querySelector('#goal-year').value, '2027');
  assert.equal(m.d.querySelector('#goal-month').value, '1');
  assert.ok(m.calls.every(c => new URL(c.url, 'http://localhost').searchParams.get('year') === '2027'));
  m.dom.window.close();
});

test('목표 조회 실패 시 새 목표를 잘못 생성하지 않고 오류를 표시한다', async () => {
  const m = await mount('goals', async () => response({}, 500));
  assert.equal(m.d.querySelector('#save-annual-goal').disabled, true);
  assert.match(m.d.querySelector('#goal-status').textContent, /불러오지 못/);
  m.d.querySelector('#annual-goal-input').value = '3';
  m.d.querySelector('#save-annual-goal').click(); await m.flush();
  assert.equal(m.calls.filter(c => c.method).length, 0);
  m.dom.window.close();
});

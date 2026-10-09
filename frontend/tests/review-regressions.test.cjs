const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require(process.env.DADOK_TEST_JSDOM || 'jsdom');
const root = path.resolve(__dirname, '..');
const response = (data, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => data });
const user = { id: 1, nickname: '독자', email: 'reader@example.test', profile_image: 'profile_images/profile_image3.svg' };
const review = { id: 7, isbn: '123', content: '기존 리뷰', rating: 4.5 };
const book = { isbn: '123', title: '책', image_url: 'https://example.test/book.jpg' };
function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}
async function mount(t, page, handler, query = '') {
  const errors = [], alerts = [], calls = [], charts = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', error => { if (!error.message.includes('navigation')) errors.push(error.message); });
  const dom = new JSDOM(fs.readFileSync(path.join(root, 'screen', page + '.html'), 'utf8'), {
    url: 'http://localhost:5500/screen/' + page + '.html' + query, runScripts: 'outside-only', virtualConsole: vc
  });
  t.after(() => dom.window.close());
  const w = dom.window, d = w.document;
  await new Promise(done => w.addEventListener('load', done, { once: true }));
  w.Headers = global.Headers;
  w.localStorage.setItem('token', 'expired-access');
  w.localStorage.setItem('refresh_token', 'valid-refresh');
  w.DADOK_API_BASE_URL = 'https://api.example.test';
  w.alert = message => alerts.push(message);
  w.console = { log() {}, warn() {}, error: (...args) => errors.push(String(args[0])) };
  w.HTMLCanvasElement.prototype.getContext = function () { return this; };
  w.Chart = function (canvas, config) { charts.push({ id: canvas.id, config }); this.destroy = () => {}; };
  w.fetch = async (url, init = {}) => {
    calls.push({ url: String(url), ...init });
    return handler(new URL(url), init);
  };
  // Run every actual local script in HTML order, including the real API/JWT helper.
  for (const script of d.querySelectorAll('script')) {
    if (!script.src) { w.eval(script.textContent); continue; }
    const url = new URL(script.src);
    if (url.origin === w.location.origin) w.eval(fs.readFileSync(path.join(root, url.pathname), 'utf8'));
  }
  d.dispatchEvent(new w.Event('DOMContentLoaded'));
  const flush = async () => { for (let i = 0; i < 8; i++) await new Promise(done => setImmediate(done)); };
  await flush();
  return { w, d, calls, errors, alerts, charts, flush };
}
function click(m, selector) {
  // dispatchEvent bypasses disabled-button browser behavior to prove the handler guard too.
  m.d.querySelector(selector).dispatchEvent(new m.w.MouseEvent('click', { bubbles: true }));
}
function writes(m) { return m.calls.filter(call => ['POST', 'PUT', 'PATCH', 'DELETE'].includes(call.method)); }

test('호환성 신규 리뷰 작성은 기존 POST 경로와 ISBN·본문·선택 평점을 유지한다', async t => {
  const m = await mount(t, 'review-write', async (url, init) => {
    if (url.pathname === '/api/user/me/') return response(user);
    if (url.pathname === '/api/book/isbn/123/') return response(book);
    if (url.pathname === '/api/review/' && init.method === 'POST') return response({ id: 8 }, 201);
    throw new Error('Unexpected API: ' + url.href);
  }, '?isbn=123');
  assert.equal(m.d.querySelector('#publish-review').disabled, false);
  m.d.querySelector('#review-text').value = '  새 리뷰  ';
  click(m, '.star[data-value="4"]');
  click(m, '#publish-review'); await m.flush();
  assert.equal(writes(m).length, 1);
  assert.equal(writes(m)[0].url, 'https://api.example.test/api/review/');
  assert.deepEqual(JSON.parse(writes(m)[0].body), { isbn: '123', content: '새 리뷰', rating: 4 });
  assert.ok(m.alerts.some(message => message === '리뷰가 발행되었습니다.'));
  assert.deepEqual(m.errors, []);
});

// Captured by the independent review's isolated Django APIClient probe (not live production).
const shortYearProgress = {
  goal_id: null, goal_period: null, goal_books: 0, read_books: 1, progress: 0,
  year: 999, month: null, scope: 'annual', date_basis: 'REVIEW_RECORD_DATE',
  date_field: 'review.created_at', date_basis_label: '리뷰 기록일 기준 도서 수 (실제 완독일이 아님)', timezone: 'Asia/Seoul'
};
const shortYearMonthly = {
  goal_id: null, goal_period: null, goal_books: 0, read_books: 1,
  monthly_reading: {
    '0999-01': 0, '0999-02': 0, '0999-03': 0, '0999-04': 0, '0999-05': 0, '0999-06': 0,
    '0999-07': 1, '0999-08': 0, '0999-09': 0, '0999-10': 0, '0999-11': 0, '0999-12': 0
  },
  year: 999, month: null, scope: 'annual', date_basis: 'REVIEW_RECORD_DATE',
  date_field: 'review.created_at', date_basis_label: '리뷰 기록일 기준 도서 수 (실제 완독일이 아님)', timezone: 'Asia/Seoul'
};

test('F4 연도 999 목표 화면은 실제 API의 0999 월별 키로 7월 기록 1권을 표시한다', async t => {
  const m = await mount(t, 'goals', async url => {
    if (url.pathname === '/api/goal/monthly-progress/') return response(shortYearMonthly);
    if (url.pathname === '/api/goal/progress/') {
      return response(url.searchParams.has('month') ? { ...shortYearProgress, month: 7, scope: 'monthly' } : shortYearProgress);
    }
    throw new Error('Unexpected API: ' + url.href);
  });
  m.d.querySelector('#goal-year').value = '999';
  m.d.querySelector('#goal-month').value = '7';
  m.calls.length = 0; m.charts.length = 0;
  click(m, '#load-period'); await m.flush();
  assert.ok(m.calls.every(call => new URL(call.url).searchParams.get('year') === '999'), 'API 입력은 기존 숫자 연도 유지');
  assert.equal(m.d.querySelector('#goal-progress').textContent, '1 권');
  const monthly = m.charts.find(chart => chart.id === 'monthlyChart').config.data;
  assert.deepEqual(Array.from(monthly.datasets[0].data), [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0]);
  assert.deepEqual(Array.from(monthly.labels), Array.from({ length: 12 }, (_, i) => (i + 1) + '월'));
  assert.deepEqual(m.errors, []);
});

test('F3 리뷰 수정 초기 조회 실패 후 PUT을 차단하고 다시 연 화면에서 기존 평점을 로드한 뒤 저장한다', async t => {
  let stored = { ...review }, available = false;
  const handler = async (url, init) => {
    if (url.pathname === '/api/user/me/') return response(user);
    if (url.pathname === '/api/review/7/') {
      if (init.method === 'PUT') { stored = { ...stored, ...JSON.parse(init.body) }; return response(stored); }
      return available ? response(stored) : response({}, 503);
    }
    if (url.pathname === '/api/book/isbn/123/') return response(book);
    throw new Error('Unexpected API: ' + url.href);
  };
  const failed = await mount(t, 'review-write', handler, '?id=7');
  failed.d.querySelector('#review-text').value = '조회 실패 후 새 본문';
  click(failed, '#publish-review'); await failed.flush();
  assert.equal(writes(failed).length, 0, '기존 평점을 읽지 못했으면 PUT 금지');
  assert.equal(stored.rating, 4.5);
  assert.equal(failed.d.querySelector('#publish-review').disabled, true);
  assert.ok(failed.alerts.some(message => /불러오지 못.*다시/.test(message)));
  assert.ok(!failed.alerts.some(message => /수정되었습니다/.test(message)));
  available = true; // Retry by reopening/refreshing the actual edit screen, without a new UI control.
  const loaded = await mount(t, 'review-write', handler, '?id=7');
  assert.equal(loaded.d.querySelector('#publish-review').disabled, false);
  assert.equal(loaded.d.querySelector('#publish-review').textContent, '수정');
  assert.equal(loaded.d.querySelector('#rating-value').textContent, '4.5점');
  assert.equal(loaded.d.querySelector('#review-text').value, review.content);
  loaded.d.querySelector('#review-text').value = '로드 후 새 본문';
  click(loaded, '#publish-review'); await loaded.flush();
  assert.equal(writes(loaded).length, 1);
  assert.deepEqual(JSON.parse(writes(loaded)[0].body), { isbn: '123', content: '로드 후 새 본문', rating: 4.5 });
  assert.equal(stored.rating, 4.5);
  assert.ok(loaded.d.querySelector('.publish-button'));
  assert.deepEqual(loaded.errors, []);
});

test('F3 리뷰 수정 조회 중 저장은 비활성이며 조회 성공 이후에만 기존 평점으로 PUT한다', async t => {
  const initial = deferred();
  const m = await mount(t, 'review-write', async (url, init) => {
    if (url.pathname === '/api/user/me/') return response(user);
    if (url.pathname === '/api/review/7/') return init.method === 'PUT' ? response(review) : initial.promise;
    if (url.pathname === '/api/book/isbn/123/') return response(book);
    throw new Error('Unexpected API: ' + url.href);
  }, '?id=7');
  assert.equal(m.d.querySelector('#publish-review').disabled, true, '수정 리뷰 조회 중 저장 비활성');
  m.d.querySelector('#review-text').value = '로드 전 입력';
  click(m, '#publish-review'); await m.flush();
  assert.equal(writes(m).length, 0);
  initial.resolve(response(review)); await m.flush();
  assert.equal(m.d.querySelector('#publish-review').disabled, false);
  m.d.querySelector('#review-text').value = '로드 완료 후 입력';
  click(m, '#publish-review'); await m.flush();
  assert.equal(writes(m).length, 1);
  assert.equal(JSON.parse(writes(m)[0].body).rating, 4.5);
  assert.deepEqual(m.errors, []);
});

test('F2 프로필 로드 후 기존 이미지를 보존하며 저장 중 중복 요청을 막고 실패 후 재시도한다', async t => {
  const initial = deferred(), pendingSave = deferred();
  let firstSave = true;
  const m = await mount(t, 'mypage_edit', async (url, init) => {
    if (url.pathname === '/api/user/me/') return initial.promise;
    if (url.pathname === '/api/user/update_profile/') {
      return firstSave ? pendingSave.promise : response({ user: { ...user, ...JSON.parse(init.body) } });
    }
    throw new Error('Unexpected API: ' + url.href);
  });
  assert.equal(m.d.querySelector('#save-profile').disabled, true, '조회 중에는 저장 비활성');
  click(m, '#save-profile'); await m.flush();
  assert.equal(writes(m).length, 0);
  initial.resolve(response(user)); await m.flush();
  assert.equal(m.d.querySelector('#save-profile').disabled, false);
  assert.ok(m.d.querySelector('#profile-image').src.endsWith('/profile_image3.svg'));
  m.d.querySelector('#user-nickname').value = '변경한 닉네임';
  click(m, '#save-profile'); click(m, '#save-profile'); await m.flush();
  assert.equal(writes(m).length, 1, '저장 중 강제 click도 중복 PUT을 만들지 않아야 함');
  assert.equal(m.d.querySelector('#save-profile').disabled, true);
  assert.deepEqual(JSON.parse(writes(m)[0].body), { nickname: '변경한 닉네임', profile_image: user.profile_image });
  pendingSave.resolve(response({}, 503)); await m.flush();
  assert.equal(m.d.querySelector('#save-profile').disabled, false, '저장 실패 후 재시도 허용');
  firstSave = false;
  click(m, '#save-profile'); await m.flush();
  assert.equal(writes(m).length, 2);
  assert.equal(JSON.parse(writes(m)[1].body).profile_image, user.profile_image);
  assert.equal(m.w.localStorage.getItem('username'), '변경한 닉네임');
  assert.deepEqual(m.errors, []);
});

test('F1 내 정보는 설정 API 주소에서 401 갱신 후 새 JWT로 재조회한다', async t => {
  const m = await mount(t, 'mypage', async (url, init) => {
    if (url.pathname === '/api/auth/token/refresh/') {
      assert.deepEqual(JSON.parse(init.body), { refresh: 'valid-refresh' });
      return response({ access: 'renewed-access', refresh: 'rotated-refresh' });
    }
    if (url.pathname === '/api/user/me/') {
      return new Headers(init.headers).get('Authorization') === 'Bearer renewed-access' ? response(user) : response({}, 401);
    }
    if (url.pathname === '/api/goal/goal/') return response([]);
    throw new Error('Unexpected API: ' + url.href);
  });
  const me = m.calls.filter(call => new URL(call.url).pathname === '/api/user/me/');
  assert.ok(me.every(call => new URL(call.url).origin === 'https://api.example.test'), '내 정보도 공통 API 호스트를 따라야 함');
  assert.equal(me.length, 2, '401 후 내 정보 GET을 한 번 재시도');
  assert.deepEqual(me.map(call => new Headers(call.headers).get('Authorization')), ['Bearer expired-access', 'Bearer renewed-access']);
  assert.equal(m.calls.filter(call => call.url.endsWith('/api/auth/token/refresh/')).length, 1);
  assert.equal(m.w.localStorage.getItem('refresh_token'), 'rotated-refresh');
  assert.equal(m.d.querySelector('#user-email').value, user.email);
  assert.equal(m.d.querySelector('#username-display').textContent, user.nickname);
  assert.ok(m.d.querySelector('.profile-picture img').src.endsWith('/profile_image3.svg'));
  assert.ok(m.d.querySelector('.set-goal-btn'));
  assert.deepEqual(m.errors, []);
});

for (const changePassword of [false, true]) {
  test('F2 프로필 초기 조회 실패는 ' + (changePassword ? '비밀번호' : '닉네임') + ' 저장 및 이미지 덮어쓰기를 차단한다', async t => {
    let stored = { ...user };
    const m = await mount(t, 'mypage_edit', async (url, init) => {
      if (url.pathname === '/api/user/me/') return response({}, 503);
      if (url.pathname === '/api/user/update_profile/') {
        stored = { ...stored, ...JSON.parse(init.body) };
        return response({ user: stored });
      }
      throw new Error('Unexpected API: ' + url.href);
    });
    m.d.querySelector('#user-nickname').value = '변경한 닉네임';
    if (changePassword) {
      m.d.querySelector('#current-password').value = ' old secret ';
      m.d.querySelector('#user-password').value = ' new secret ';
    }
    click(m, '#save-profile');
    await m.flush();
    assert.equal(writes(m).length, 0, '초기 GET 실패 후 PUT 금지');
    assert.equal(stored.profile_image, user.profile_image, '기존 선택 이미지 보존');
    assert.equal(m.d.querySelector('#save-profile').disabled, true);
    assert.ok(m.alerts.some(message => message.includes('불러오지 못')));
    assert.ok(!m.alerts.some(message => message.includes('성공')));
    assert.ok(m.d.querySelector('.save-btn'));
    assert.deepEqual(m.errors, []);
  });
}

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require(process.env.DADOK_TEST_JSDOM || 'jsdom');
const root = path.resolve(__dirname, '..');
const response = (data, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => data, text: async () => JSON.stringify(data) });
function deferred() { let resolve; const promise = new Promise(r => resolve = r); return { promise, resolve }; }
function sharedStorage() { const data = new Map(); return { getItem: k => data.get(k) ?? null, setItem: (k, v) => data.set(k, String(v)), removeItem: k => data.delete(k) }; }
const seed = (w, name = 'A') => w.AppAPI.saveSession({ access_token: name + '-access', refresh_token: name + '-refresh', user: { nickname: name } });
async function flush() { for (let i = 0; i < 8; i++) await new Promise(r => setImmediate(r)); }
async function mount(page = 'index', shared, query = '') {
  const dom = new JSDOM(fs.readFileSync(path.join(root, 'screen', page + '.html'), 'utf8'), { url: 'https://frontend.example.test/screen/' + page + '.html' + query, runScripts: 'outside-only', virtualConsole: new VirtualConsole() });
  const w = dom.window;
  await new Promise(r => w.addEventListener('load', r, { once: true }));
  if (shared) Object.defineProperty(w, 'localStorage', { value: shared });
  w.Headers = Headers; w.alert = () => {}; w.confirm = () => true; w.prompt = () => 'synthetic update';
  w.DADOK_API_BASE_URL = 'https://api.example.test';
  w.HTMLCanvasElement.prototype.getContext = function () { return this; };
  w.Chart = function () { this.destroy = () => {}; };
  for (const file of ['security.js', 'api.js']) w.eval(fs.readFileSync(path.join(root, 'scripts', file), 'utf8'));
  return { dom, w, d: w.document, start: async file => { w.eval(fs.readFileSync(path.join(root, 'scripts', file + '.js'), 'utf8')); w.document.dispatchEvent(new w.Event('DOMContentLoaded')); await flush(); } };
}
for (const switchAccount of [false, true]) {
  test('B1 cross-tab late refresh cannot ' + (switchAccount ? 'mix accounts' : 'restore logout'), async () => {
    const shared = sharedStorage(), a = await mount('index', shared), b = await mount('index', shared), late = deferred();
    try {
      seed(a.w); a.w.fetch = () => late.promise;
      const flight = a.w.AppAPI.refresh().catch(() => null);
      if (switchAccount) seed(b.w, 'B'); else b.w.AppAPI.clearSession();
      late.resolve(response({ access: 'A-late', refresh: 'A-rotated' })); await flight;
      assert.ok(shared.getItem('token') === (switchAccount ? 'B-access' : null), 'late A refresh must not overwrite shared session');
      assert.ok(shared.getItem('refresh_token') === (switchAccount ? 'B-refresh' : null));
    } finally { a.dom.window.close(); b.dom.window.close(); }
  });
}
for (const bodyDelay of [false, true]) {
  test('B2 real login is cancelled after session clear at ' + (bodyDelay ? 'JSON await' : 'fetch await'), async () => {
    const m = await mount(), late = deferred();
    try {
      m.w.fetch = () => bodyDelay ? Promise.resolve({ ...response({}), json: () => late.promise }) : late.promise;
      await m.start('login');
      m.d.querySelector('#username').value = 'synthetic'; m.d.querySelector('#password').value = 'synthetic-only';
      m.d.querySelector('#login-form').dispatchEvent(new m.w.Event('submit', { cancelable: true }));
      await flush(); m.w.AppAPI.clearSession();
      const data = { access_token: 'late-access', refresh_token: 'late-refresh', user: { nickname: 'synthetic' } };
      late.resolve(bodyDelay ? data : response(data)); await flush();
      assert.equal(m.w.localStorage.getItem('token'), null, 'obsolete login cannot restore credentials');
    } finally { m.dom.window.close(); }
  });
  test('B2 real mypage does not render A after logout at ' + (bodyDelay ? 'JSON await' : 'fetch await'), async () => {
    const m = await mount('mypage'), late = deferred();
    try {
      seed(m.w); m.w.fetch = url => url.endsWith('/me/') ? (bodyDelay ? Promise.resolve({ ...response({}), json: () => late.promise }) : late.promise) : Promise.resolve(response([]));
      await m.start('mypage'); m.w.AppAPI.clearSession();
      const data = { nickname: 'private-A', email: 'synthetic-A@example.test', profile_image: '' };
      late.resolve(bodyDelay ? data : response(data)); await flush();
      assert.equal(m.d.querySelector('#user-email').value, '', 'stale PII must not render');
      assert.equal(m.d.querySelector('.set-goal-btn').disabled, true);
    } finally { m.dom.window.close(); }
  });
}
function fixture(url) {
  if (url.endsWith('/me/')) return response({ id: 1, nickname: 'private-A', email: 'synthetic-A@example.test', profile_image: '' });
  if (url.includes('monthly-progress')) return response({ monthly_reading: { '2026-01': 3 } });
  if (url.includes('/progress/')) return response({ goal_id: 2, goal_books: 10, read_books: 3 });
  if (url.includes('/goal/goal/')) return response([{ id: 2, total_books: 10, year: 2026, month: null }]);
  if (url.includes('comments/list')) return response([{ id: 1, user: 1, user_nickname: 'private-A', content: 'public comment' }]);
  if (url.includes('/liked/')) return response([{ review_id: 1 }]);
  if (url.includes('/library/')) return response([{ isbn: '123', title: 'private-library', short_review: 'private-review', rating: 4 }]);
  if (url.includes('/review/1/')) return response({ id: 1, isbn: '123', user_nickname: 'private-A', content: 'private-draft', rating: 4 });
  if (url.includes('/isbn/')) return response({ isbn: '123', title: 'public title', author: 'public author' });
  if (url.includes('personalized')) return response([{ title: 'private-recommendation' }]);
  return response([]);
}
for (const [page, query, selector, event, check] of [
  ['mypage', '', '.set-goal-btn', 'click', m => { assert.equal(m.d.querySelector('#user-email').value, ''); assert.equal(m.d.querySelector('#goal-input').value, ''); }],
  ['goals', '', '#save-annual-goal', 'click', m => { assert.equal(m.d.querySelector('#annual-goal-input').value, ''); assert.equal(m.d.querySelector('#goal-target').textContent, '-'); }],
  ['review-write', '?id=1', '#publish-review', 'click', m => { assert.equal(m.d.querySelector('#review-text').value, ''); assert.equal(m.d.querySelector('#review-author').textContent, ''); }],
  ['review-detail', '?id=1', '#comment-input', 'keypress', m => { assert.equal(m.d.querySelector('#comment-input').value, ''); assert.equal(m.d.querySelector('#comment-username').textContent, ''); assert.equal(m.d.querySelector('#edit-button').style.display, 'none'); }],
  ['library', '', null, null, m => assert.equal(m.d.querySelector('#book-grid').children.length, 0)],
  ['welcome', '', null, null, m => assert.equal(m.d.querySelector('#user-name').textContent, '')],
  ['main', '', null, null, m => assert.equal(m.d.querySelector('#goal-target').textContent, '-')],
  ['book-detail', '?isbn=123', null, null, m => assert.equal(m.d.querySelector('#recommendation-grid').children.length, 0)]
]) {
  test('B2 loaded private DOM cleared and B write blocked: ' + page, async () => {
    const shared = sharedStorage(), m = await mount(page, shared, query), other = await mount('index', shared); let writes = 0;
    try {
      seed(m.w); m.w.fetch = async (url, init) => { if (init?.method && init.method !== 'GET') writes++; return fixture(url); };
      await m.start(page); if (page === 'review-detail') m.d.querySelector('#comment-input').value = 'private unsent';
      seed(other.w, 'B'); m.w.dispatchEvent(new m.w.StorageEvent('storage', { key: 'dadok_session_epoch' }));
      check(m);
      if (selector) m.d.querySelector(selector).dispatchEvent(event === 'keypress' ? new m.w.KeyboardEvent(event, { key: 'Enter', cancelable: true }) : new m.w.Event(event));
      await flush(); assert.equal(writes, 0, 'stale UI must not write as B');
      assert.ok(shared.getItem('token') === 'B-access');
    } finally { m.dom.window.close(); other.dom.window.close(); }
  });
}
for (const pendingRefresh of [false, true]) {
  test('B4 old A logout cannot revoke or clear B: ' + (pendingRefresh ? 'waiting rotation' : 'late 401'), async () => {
    const m = await mount(), late = deferred(); const sent = [];
    try {
      seed(m.w); m.w.fetch = async (url, init) => { sent.push({ url, body: JSON.parse(init.body) }); return sent.length === 1 ? late.promise : response({ access: 'B-renewed' }); };
      let refresh;
      if (pendingRefresh) refresh = m.w.AppAPI.refresh().catch(() => null);
      const logout = m.w.AppAPI.logout(); await flush(); seed(m.w, 'B');
      late.resolve(pendingRefresh ? response({ access: 'A-renewed', refresh: 'A-rotated' }) : response({}, 401));
      await logout; if (refresh) await refresh;
      assert.equal(sent.length, 1, 'old logout must not send B refresh/revocation');
      assert.ok(m.w.localStorage.getItem('token') === 'B-access', 'old logout must preserve B');
      assert.ok(m.w.localStorage.getItem('refresh_token') === 'B-refresh');
    } finally { m.dom.window.close(); }
  });
}
test('B4 logout flights are account-owned, B does not join pending A logout', async () => {
  const m = await mount(), late = deferred(); let calls = 0;
  try {
    seed(m.w); m.w.fetch = () => ++calls === 1 ? late.promise : Promise.resolve(response({}));
    const a = m.w.AppAPI.logout(); await flush(); seed(m.w, 'B');
    const b = m.w.AppAPI.logout(); await flush();
    assert.equal(calls, 2, 'B needs its own revocation flight');
    assert.notEqual(a, b); late.resolve(response({}, 401)); await Promise.all([a, b]);
    assert.equal(m.w.localStorage.getItem('token'), null);
  } finally { m.dom.window.close(); }
});
test('B4 logout waits owned refresh and blacklists latest rotation', async () => {
  const m = await mount(), late = deferred(); const sent = [];
  try {
    seed(m.w); m.w.fetch = async (url, init) => { sent.push({ url, body: JSON.parse(init.body) }); return url.endsWith('/refresh/') ? late.promise : response({}); };
    const refresh = m.w.AppAPI.refresh(), logout = m.w.AppAPI.logout(); await flush();
    assert.equal(sent.length, 1); late.resolve(response({ access: 'A-renewed', refresh: 'A-rotated' }));
    await Promise.all([refresh, logout]);
    assert.equal(sent.length, 2); assert.ok(sent[1].body.refresh_token === 'A-rotated');
    assert.equal(m.w.localStorage.getItem('token'), null);
  } finally { m.dom.window.close(); }
});
test('B3 delayed A retry 401 cannot clear newer B login', async () => {
  const m = await mount(), late = deferred(); let calls = 0;
  try {
    seed(m.w); m.w.fetch = async url => url.endsWith('/refresh/') ? response({ access: 'A-renewed' }) : ++calls === 1 ? response({}, 401) : late.promise;
    const request = m.w.AppAPI.request('/api/user/me/').catch(() => null);
    await flush(); assert.equal(calls, 2); seed(m.w, 'B'); late.resolve(response({}, 401)); await request;
    assert.ok(m.w.localStorage.getItem('token') === 'B-access', 'old 401 must not delete B');
    assert.ok(m.w.localStorage.getItem('refresh_token') === 'B-refresh');
  } finally { m.dom.window.close(); }
});
test('B2 delayed reset response must not clear a new B login', async () => {
  const shared = sharedStorage(), m = await mount('find-account', shared, '?uid=synthetic-uid&token=synthetic-reset'), b = await mount('index', shared), late = deferred();
  try {
    seed(m.w); m.w.fetch = () => late.promise; await m.start('find-account');
    m.d.querySelector('#reset-new-password').value = 'synthetic-only'; m.d.querySelector('#reset-confirm-password').value = 'synthetic-only';
    m.d.querySelector('#reset-password-form').dispatchEvent(new m.w.Event('submit', { cancelable: true }));
    await flush(); seed(b.w, 'B'); late.resolve(response({ message: 'synthetic success' })); await flush();
    assert.ok(shared.getItem('token') === 'B-access', 'reset for old A must not clear B');
  } finally { m.dom.window.close(); b.dom.window.close(); }
});
test('B1 interleaved credential commit cannot leave mixed A/B legacy pair', async () => {
  const shared = sharedStorage(), a = await mount('index', shared), b = await mount('index', shared);
  try {
    seed(a.w); let switched = false;
    const set = shared.setItem;
    shared.setItem = (key, value) => {
      if (!switched && key === 'token' && value === 'A-renewed') { switched = true; seed(b.w, 'B'); }
      set(key, value);
    };
    a.w.fetch = async () => response({ access: 'A-renewed', refresh: 'A-rotated' });
    await a.w.AppAPI.refresh().catch(() => null);
    assert.ok(shared.getItem('token') === 'B-access', 'legacy pair must converge to authoritative B');
    assert.ok(shared.getItem('refresh_token') === 'B-refresh');
    let bearer;
    b.w.fetch = async (url, init) => { bearer = new Headers(init.headers).get('Authorization'); return response({}); };
    await b.w.AppAPI.request('/api/user/me/'); assert.ok(bearer === 'Bearer B-access');
  } finally { a.dom.window.close(); b.dom.window.close(); }
});
test('B1 a B refresh must not join pending A refresh flight', async () => {
  const m = await mount(), late = deferred(); let calls = 0;
  try {
    seed(m.w); m.w.fetch = () => ++calls === 1 ? late.promise : Promise.resolve(response({ access: 'B-renewed', refresh: 'B-rotated' }));
    const a = m.w.AppAPI.refresh().catch(() => null); seed(m.w, 'B'); const b = m.w.AppAPI.refresh();
    await b; assert.equal(calls, 2); late.resolve(response({ access: 'A-renewed' })); await a;
    assert.ok(m.w.localStorage.getItem('token') === 'B-renewed'); assert.ok(m.w.localStorage.getItem('refresh_token') === 'B-rotated');
  } finally { m.dom.window.close(); }
});
test('B1 real profile form loaded as A cannot PUT with B credentials', async () => {
  const shared = sharedStorage(), a = await mount('mypage_edit', shared), b = await mount('index', shared); let writes = 0;
  try {
    seed(a.w); a.w.fetch = async url => url.endsWith('/me/') ? response({ nickname: 'private-A', profile_image: '' }) : (writes++, response({ user: { nickname: 'private-A' } }));
    await a.start('mypage_edit'); assert.equal(a.d.querySelector('#save-profile').disabled, false);
    seed(b.w, 'B'); a.d.querySelector('#save-profile').click(); await flush();
    assert.equal(writes, 0, 'A form must not be sent as B');
    assert.equal(a.d.querySelector('#user-nickname').value, '');
    assert.equal(a.d.querySelector('#save-profile').disabled, true);
  } finally { a.dom.window.close(); b.dom.window.close(); }
});

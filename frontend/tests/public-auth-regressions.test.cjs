const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require(process.env.DADOK_TEST_JSDOM || 'jsdom');
const root = path.resolve(__dirname, '..');
const response = (data, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => data });
const jwt = (owner, kind, extra = {}) => ['eyJhbGciOiJub25lIn0', Buffer.from(JSON.stringify({ user_id: owner, token_type: kind, ...extra })).toString('base64url'), 'synthetic-signature'].join('.');
const pair = owner => ({ access_token: jwt(owner, 'access'), refresh_token: jwt(owner, 'refresh'), user: { nickname: 'Synthetic ' + owner } });
function sharedStorage() { const data = new Map(); return { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, String(value)), removeItem: key => data.delete(key) }; }
async function flush() { for (let i = 0; i < 8; i++) await new Promise(resolve => setImmediate(resolve)); }
async function mount(page, shared = sharedStorage(), query = '') {
  const dom = new JSDOM(fs.readFileSync(path.join(root, 'screen', page + '.html'), 'utf8'), { url: 'https://frontend.example.test/screen/' + page + '.html' + query, runScripts: 'outside-only', virtualConsole: new VirtualConsole() });
  const w = dom.window;
  await new Promise(resolve => w.addEventListener('load', resolve, { once: true }));
  Object.defineProperty(w, 'localStorage', { value: shared });
  w.Headers = Headers; w.DADOK_API_BASE_URL = 'https://api.example.test';
  const alerts = []; w.alert = text => alerts.push(text);
  for (const file of ['security.js', 'api.js']) w.eval(fs.readFileSync(path.join(root, 'scripts', file), 'utf8'));
  return { dom, w, d: w.document, alerts, start: async () => { w.eval(fs.readFileSync(path.join(root, 'scripts', page + '.js'), 'utf8')); w.document.dispatchEvent(new w.Event('DOMContentLoaded')); await flush(); } };
}

const resetQuery = owner => '?uid=' + Buffer.from(String(owner)).toString('base64url') + '&token=synthetic-reset';
function submitReset(m) {
  m.d.getElementById('reset-new-password').value = 'Synthetic-New-48!';
  m.d.getElementById('reset-confirm-password').value = 'Synthetic-New-48!';
  m.d.getElementById('reset-password-form').dispatchEvent(new m.w.Event('submit', { cancelable: true }));
}
function assertResetSuccess(m) {
  assert.match(m.d.getElementById('reset-result').textContent, /비밀번호가 변경되었습니다/);
  assert.equal(m.d.getElementById('reset-password-form').hidden, true, 'consumed reset form must be hidden');
  assert.equal(m.d.getElementById('reset-new-password').value, '', 'new password must be removed');
  assert.equal(m.d.getElementById('reset-confirm-password').value, '', 'confirmation must be removed');
}
for (const loginBeforeOpen of [true, false]) {
  test('R2 reset target A preserves B logged in ' + (loginBeforeOpen ? 'before opening link' : 'after opening link before submit'), async () => {
    const shared = sharedStorage(); const m = await mount('find-account', shared, resetQuery(1)); const b = await mount('register', shared); const calls = [];
    try {
      await m.w.AppAPI.saveSession(pair(loginBeforeOpen ? 2 : 1));
      m.w.fetch = async (url, init) => { calls.push({ url, authorization: new Headers(init.headers).get('Authorization'), body: JSON.parse(init.body) }); return response({ message: 'changed' }); };
      await m.start();
      if (!loginBeforeOpen) await b.w.AppAPI.saveSession(pair(2));
      const record = shared.getItem('dadok_session_record');
      submitReset(m); await flush();
      assert.equal(shared.getItem('token'), pair(2).access_token, 'A password reset must preserve B access');
      assert.equal(shared.getItem('refresh_token'), pair(2).refresh_token, 'A password reset must preserve B refresh');
      assert.equal(shared.getItem('dadok_session_record'), record, 'unrelated account epoch must not change');
      assert.equal(calls.length, 1); assert.equal(calls[0].authorization, null);
      assert.equal(calls[0].body.uid, Buffer.from('1').toString('base64url'));
      assertResetSuccess(m);
    } finally { m.dom.window.close(); b.dom.window.close(); }
  });
}

function deferred() { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; }
for (const bodyDelay of [false, true]) {
  test('R3 public reset remains successful after B login during ' + (bodyDelay ? 'JSON parsing' : 'fetch'), async () => {
    const shared = sharedStorage(); const m = await mount('find-account', shared, resetQuery(1)); const b = await mount('register', shared); const late = deferred(); const calls = []; let reading = false;
    try {
      await m.w.AppAPI.saveSession(pair(1));
      m.w.fetch = (url, init) => {
        calls.push({ url, authorization: new Headers(init.headers).get('Authorization') });
        return bodyDelay ? Promise.resolve({ ...response({}), json: () => { reading = true; return late.promise; } }) : late.promise;
      };
      await m.start(); submitReset(m); await flush();
      assert.equal(calls.length, 1); assert.equal(calls[0].authorization, null);
      if (bodyDelay) assert.equal(reading, true, 'test must pause inside response JSON');
      await b.w.AppAPI.saveSession(pair(2));
      const record = shared.getItem('dadok_session_record');
      late.resolve(bodyDelay ? { message: 'changed' } : response({ message: 'changed' })); await flush();
      assertResetSuccess(m);
      assert.equal(shared.getItem('token'), pair(2).access_token);
      assert.equal(shared.getItem('refresh_token'), pair(2).refresh_token);
      assert.equal(shared.getItem('dadok_session_record'), record, 'successful reset must not mutate newer B epoch');
    } finally { m.dom.window.close(); b.dom.window.close(); }
  });
}

for (const [label, query, credentials] of [
  ['opaque legacy owner', resetQuery(1), { access_token: 'opaque-access', refresh_token: 'opaque-refresh' }],
  ['invalid base64', '?uid=*&token=synthetic-reset', pair(1)],
  ['truncated base64', '?uid=M&token=synthetic-reset', pair(1)],
  ['Unicode username UID', resetQuery('사용자'), pair(1)],
  ['nonnumeric UID', resetQuery('synthetic-user'), pair(1)],
]) {
  test('R2 unidentified reset ownership preserves session: ' + label, async () => {
    const m = await mount('find-account', undefined, query);
    try {
      await m.w.AppAPI.saveSession(credentials);
      const record = m.w.localStorage.getItem('dadok_session_record');
      m.w.fetch = async () => response({ message: 'changed' });
      await m.start(); submitReset(m); await flush();
      assertResetSuccess(m);
      assert.equal(m.w.localStorage.getItem('dadok_session_record'), record);
      assert.equal(m.w.localStorage.getItem('token'), credentials.access_token);
      assert.equal(m.w.localStorage.getItem('refresh_token'), credentials.refresh_token);
    } finally { m.dom.window.close(); }
  });
}
for (const owner of [1, '9007199254740993']) {
  test('R2 matching reset owner clears only captured current session: ' + owner, async () => {
    const m = await mount('find-account', undefined, resetQuery(owner));
    try {
      await m.w.AppAPI.saveSession(pair(owner));
      m.w.fetch = async () => response({ message: 'changed' });
      await m.start(); submitReset(m); await flush();
      assertResetSuccess(m);
      assert.equal(m.w.localStorage.getItem('token'), null);
      assert.equal(m.w.localStorage.getItem('refresh_token'), null);
      assert.equal(m.w.AppAPI.snapshot().active, false);
    } finally { m.dom.window.close(); }
  });
}
test('R3 newer login of same reset owner preserves its replacement epoch', async () => {
  const shared = sharedStorage(); const m = await mount('find-account', shared, resetQuery(1)); const b = await mount('register', shared); const late = deferred();
  try {
    await m.w.AppAPI.saveSession(pair(1)); m.w.fetch = () => late.promise;
    await m.start(); submitReset(m); await flush();
    const oldEpoch = m.w.AppAPI.snapshot().epoch;
    await b.w.AppAPI.saveSession(pair(1));
    const record = shared.getItem('dadok_session_record');
    assert.notEqual(m.w.AppAPI.snapshot().epoch, oldEpoch);
    late.resolve(response({ message: 'changed' })); await flush();
    assertResetSuccess(m); assert.equal(shared.getItem('dadok_session_record'), record);
  } finally { m.dom.window.close(); b.dom.window.close(); }
});
test('R3 rejected reset leaves form available and matching session intact', async () => {
  const m = await mount('find-account', undefined, resetQuery(1));
  try {
    await m.w.AppAPI.saveSession(pair(1));
    const record = m.w.localStorage.getItem('dadok_session_record');
    m.w.fetch = async () => response({ error: 'Expired link' }, 400);
    await m.start(); submitReset(m); await flush();
    assert.equal(m.d.getElementById('reset-result').textContent, 'Expired link');
    assert.equal(m.d.getElementById('reset-password-form').hidden, false);
    assert.equal(m.w.localStorage.getItem('dadok_session_record'), record);
  } finally { m.dom.window.close(); }
});

test('R1 public signup ignores expired access and blacklisted refresh credentials', async () => {
  const m = await mount('register'); const calls = [];
  try {
    const credentials = { ...pair(1), access_token: jwt(1, 'access', { exp: 1 }) };
    await m.w.AppAPI.saveSession(credentials);
    const record = m.w.localStorage.getItem('dadok_session_record');
    m.w.fetch = async (url, init) => {
      const authorization = new Headers(init.headers).get('Authorization');
      calls.push({ url, authorization, body: JSON.parse(init.body) });
      if (url.endsWith('/refresh/')) return response({ detail: 'Token is blacklisted' }, 401);
      return authorization ? response({ detail: 'Token is expired' }, 401) : response({ message: 'created' }, 201);
    };
    await m.start();
    for (const [id, value] of Object.entries({ username: 'synthetic-new', password: 'Synthetic-New-48!', nickname: 'Synthetic New', email: 'synthetic-new@example.test' })) m.d.getElementById(id).value = value;
    m.d.getElementById('register-form').dispatchEvent(new m.w.Event('submit', { cancelable: true }));
    await flush();
    assert.equal(calls[0].authorization, null, 'signup must never attach an expired Bearer');
    assert.equal(calls.length, 1, 'anonymous signup must not attempt refresh');
    assert.ok(calls[0].url.endsWith('/api/user/signup/'));
    assert.equal(calls[0].body.username, 'synthetic-new');
    assert.ok(m.alerts.some(text => text.includes('회원가입 성공')), 'anonymous 201 must reach success UI');
    assert.equal(m.w.localStorage.getItem('dadok_session_record'), record, 'public signup must preserve existing session');
  } finally { m.dom.window.close(); }
});

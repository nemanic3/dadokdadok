const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require(process.env.DADOK_TEST_JSDOM || 'jsdom');
const root = path.resolve(__dirname, '..');
const attack = '<img src=x onerror="window.__xss=1"><svg onload="window.__xss=2"></svg>';
const book = { isbn: "1');window.__xss=3;//", title: attack, author: attack, publisher: attack, published_date: attack, image_url: 'javascript:alert(1)', image: 'data:text/html,bad', link: 'javascript:alert(1)', rating: 4, short_review: attack };
const review = { id: 1, review_id: 1, isbn: '123', user: attack, user_nickname: attack, content: attack, rating: 4, likes_count: 0, created_at: '2026-01-01' };
function response(data, status = 200) { return { ok: status >= 200 && status < 300, status, json: async () => data, text: async () => JSON.stringify(data) }; }
async function mount(page, query = '', options = {}) {
  const errors = [], calls = [], alerts = [], charts = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', e => { if (!e.message.includes('navigation')) errors.push(e.message); });
  const dom = new JSDOM(fs.readFileSync(path.join(root, 'screen', page + '.html'), 'utf8'), { url: 'http://localhost:5500/screen/' + page + '.html' + query, runScripts: 'outside-only', virtualConsole: vc });
  const w = dom.window;
  await new Promise(r => w.addEventListener('load', r, { once: true }));
  if (options.now) {
    const OriginalDate = w.Date;
    w.Date = class extends OriginalDate {
      constructor(...args) { super(...(args.length ? args : [options.now])); }
      getFullYear() { return options.localYear ?? super.getFullYear(); }
    };
  }
  w.alert = message => alerts.push(message); w.confirm = () => true; w.prompt = () => '수정 내용';
  w.console = { log() {}, error: (...args) => errors.push(String(args[0])), warn() {} };
  w.Headers = global.Headers;
  w.HTMLCanvasElement.prototype.getContext = function () { return this; };
  w.Chart = function (canvas, config) { charts.push({ id: canvas.id, config }); };
  if (options.auth !== false) { w.localStorage.setItem('token', 'access'); w.localStorage.setItem('refresh_token', 'refresh'); w.localStorage.setItem('username', options.nickname || attack); }
  if (options.baseURL) w.DADOK_API_BASE_URL = options.baseURL;
  w.fetch = async (url, init = {}) => {
    calls.push({ url: String(url), ...init });
    if (options.fetch) return options.fetch(String(url), init, calls);
    if (String(url).includes('/me/')) return response({ id: 1, nickname: attack, profile_image: 'profile_images/profile_image2.svg', email: 'a@example.test' });
    if (String(url).includes('comments/list')) return response([{ id: 1, user_nickname: attack, content: attack, profile_image: 'javascript:alert(1)' }]);
    if (String(url).includes('/liked/')) return response([]);
    if (String(url).includes('/library/123')) return response([review]);
    if (String(url).includes('/review/1/')) return response(review);
    if (String(url).includes('progress/')) return response({ goal_books: 0, read_books: 0, monthly_reading: {} });
    if (String(url).includes('/isbn/')) return response(book);
    return response([book]);
  };
  if (options.fixtureButton) { const button = w.document.createElement('button'); button.id = 'write-review-btn'; w.document.body.append(button); }
  for (const script of w.document.querySelectorAll('script')) {
    if (script.src && !script.src.startsWith('http://localhost:5500/')) continue;
    const source = script.src ? fs.readFileSync(path.join(root, new URL(script.src).pathname), 'utf8') : script.textContent;
    w.eval(source);
  }
  w.document.dispatchEvent(new w.Event('DOMContentLoaded'));
  const flush = async () => { for (let i = 0; i < 8; i++) await new Promise(r => setImmediate(r)); };
  await flush();
  return { dom, w, d: w.document, errors, calls, alerts, charts, flush };
}
function assertSafe(d, selector) {
  const node = d.querySelector(selector); assert.ok(node, selector);
  assert.equal(node.querySelectorAll('svg, script, [onerror], [onload], [onclick]').length, 0, '실행 가능한 사용자 DOM이 없어야 함');
  for (const el of node.querySelectorAll('[src], [href]')) {
    const value = el.getAttribute(el.hasAttribute('src') ? 'src' : 'href');
    assert.ok(!/^\s*(?:javascript|data|vbscript):/i.test(value), '위험 URL 금지: ' + value);
  }
  assert.ok(node.textContent.includes(attack), '사용자 콘텐츠는 원문 텍스트로 보존');
}
test('P0 서재 사용자 콘텐츠/ISBN/표지 URL은 실행 가능한 DOM을 만들지 않는다', async () => {
  const { dom, d } = await mount('library', '', { fixtureButton: true });
  assertSafe(d, '#book-grid'); assert.ok(d.querySelector('.book-card .book-cover')); assert.ok(d.querySelector('.book-info h3 .rating')); dom.window.close();
});
test('P0 검색 제목/저자/속성/링크는 안전한 DOM으로 표시된다', async () => {
  const { dom, d } = await mount('search', '?query=책'); assertSafe(d, '#search-results'); assert.ok(d.querySelector('.book-cover-container .book-cover')); dom.window.close();
});
test('P0 최근 도서 사용자 콘텐츠 및 이벤트 속성은 안전하다', async () => {
  const { dom, d } = await mount('main', '', { auth: false }); assertSafe(d, '#recent-books-container'); dom.window.close();
});
test('P0 도서 상세 리뷰와 추천 콘텐츠/외부 URL은 안전하다', async () => {
  const { dom, d } = await mount('book-detail', '?isbn=123'); assertSafe(d, '#reviews-list'); assertSafe(d, '#recommendation-grid');
  assert.ok(!d.querySelector('#book-image').src.startsWith('javascript:'));
  assert.ok(!d.querySelector('#book-link').href.startsWith('javascript:')); dom.window.close();
});
test('P0 댓글 닉네임/본문은 원문 텍스트이며 실행 속성이 없다', async () => {
  const { dom, d } = await mount('review-detail', '?id=1'); assertSafe(d, '#comment-list'); assert.equal(d.querySelector('.comment-text').textContent, attack); dom.window.close();
});
for (const [page, query] of [['review-detail', '?id=1'], ['review-write', '?isbn=123']]) {
  test('P0 ' + page + ' 표지 URL도 위험 scheme을 거부한다', async () => {
    const { dom, d } = await mount(page, query);
    assert.ok(!/^javascript:/.test(d.querySelector('#book-image').src), page + ' 표지 URL'); dom.window.close();
  });
}
test('P1 로그인은 refresh를 저장하고 설정한 공통 API 주소를 사용한다', async () => {
  const m = await mount('index', '', { auth: false, baseURL: 'https://api.example.test', fetch: async () => response({ access_token: 'new-access', refresh_token: 'new-refresh', user: { nickname: '독자' } }) });
  m.d.querySelector('#username').value = 'reader'; m.d.querySelector('#password').value = 'secret';
  m.d.querySelector('#login-form').dispatchEvent(new m.w.Event('submit', { cancelable: true })); await m.flush();
  assert.equal(m.w.localStorage.getItem('refresh_token'), 'new-refresh'); assert.equal(m.calls[0].url, 'https://api.example.test/api/user/login/'); m.dom.window.close();
});
test('P1 동시 401은 refresh single-flight 후 각각 한번만 재시도한다', async () => {
  const m = await mount('search'); assert.ok(m.w.AppAPI, '공통 API helper 필요');
  m.calls.length = 0;
  m.w.fetch = async (url, init) => {
    m.calls.push({ url, ...init });
    if (String(url).endsWith('/api/auth/token/refresh/')) { await m.flush(); return response({ access: 'renewed', refresh: 'rotated' }); }
    return new Headers(init.headers).get('Authorization') === 'Bearer renewed' ? response({ ok: true }) : response({}, 401);
  };
  const results = await Promise.all([m.w.AppAPI.request('/api/user/me/'), m.w.AppAPI.request('/api/user/me/')]);
  assert.ok(results.every(r => r.ok)); assert.equal(m.calls.filter(c => c.url.endsWith('/api/auth/token/refresh/')).length, 1);
  assert.equal(m.calls.filter(c => c.url.endsWith('/api/user/me/')).length, 4); assert.equal(m.w.localStorage.getItem('refresh_token'), 'rotated'); m.dom.window.close();
});
test('P1 auth/common을 함께 로드해도 로그아웃 요청은 한번이고 실패에도 로컬 세션을 지운다', async () => {
  const m = await mount('main', '', { fetch: async url => url.includes('logout') ? response({}, 500) : url.includes('recent-reviews') ? response([]) : response({ goal_books: 0, read_books: 0 }) });
  m.d.querySelector('#logout-btn').click(); await m.flush();
  const calls = m.calls.filter(c => c.url.includes('logout')); assert.equal(calls.length, 1); assert.equal(JSON.parse(calls[0].body).refresh_token, 'refresh');
  for (const key of ['token', 'refresh_token', 'username']) assert.equal(m.w.localStorage.getItem(key), null); m.dom.window.close();
});
test('P1 검색 query/q 동시 입력은 canonical query 한번만 요청하고 q 단독도 호환한다', async () => {
  for (const query of ['?query=정식&q=구형', '?q=정식']) {
    const m = await mount('search', query); assert.equal(m.calls.length, 1); assert.equal(new URL(m.calls[0].url).searchParams.get('query'), '정식'); assert.equal(new URL(m.calls[0].url).searchParams.has('q'), false); m.dom.window.close();
  }
});
test('P1 빈 서재 객체와 없는 리뷰쓰기 DOM은 오류 없이 빈 상태를 표시한다', async () => {
  const m = await mount('library', '', { fetch: async () => response({ message: 'No books' }) });
  assert.match(m.d.querySelector('#book-grid').textContent, /아직 작성한 리뷰/); assert.deepEqual(m.errors, []); m.dom.window.close();
});
test('P1 null 리뷰 평점/본문은 댓글 조회를 막지 않는다', async () => {
  const m = await mount('review-detail', '?id=1', { auth: false, fetch: async url => url.includes('comments/list') ? response([]) : url.includes('/isbn/') ? response(book) : response({ ...review, rating: null, content: null }) });
  assert.match(m.d.querySelector('#rating-value').textContent, /평점 없음/); assert.equal(m.d.querySelector('#review-rating').querySelectorAll('img').length, 5);
  assert.ok(m.calls.some(c => c.url.includes('comments/list'))); assert.deepEqual(m.errors, []);
  for (const c of m.calls) assert.equal(new Headers(c.headers).has('Authorization'), false); m.dom.window.close();
});
test('P1 프로필 이미지 API JSON을 img URL로 사용하지 않는다', async () => {
  const m = await mount('review-detail', '?id=1');
  assert.ok(m.d.querySelector('#user-profile').src.endsWith('/assets/images/profile_image2.svg'));
  assert.ok([...m.d.querySelectorAll('img')].every(img => !img.src.includes('/api/user/profile/'))); m.dom.window.close();
});
test('P1 welcome은 기존 사용자 데이터로 DOM 오류 없이 마운트된다', async () => {
  const m = await mount('welcome'); assert.deepEqual(m.errors, []); assert.equal(m.d.querySelector('#user-name').textContent, attack); m.dom.window.close();
});
test('P1 화면의 로컬 링크/이미지 참조는 존재하는 파일이다', () => {
  const missing = [];
  for (const file of fs.readdirSync(path.join(root, 'screen')).filter(n => n.endsWith('.html'))) {
    const dom = new JSDOM(fs.readFileSync(path.join(root, 'screen', file), 'utf8'), { url: 'http://localhost/screen/' + file });
    for (const node of dom.window.document.querySelectorAll('[src], [href]')) {
      const value = node.getAttribute(node.hasAttribute('src') ? 'src' : 'href'); if (!value || value === '#' || /^https?:/.test(value)) continue;
      const p = path.join(root, new URL(value, dom.window.location.href).pathname); if (!fs.existsSync(p)) missing.push(file + ': ' + value);
    }
    dom.window.close();
  }
  assert.deepEqual(missing, []);
});
test('P1 서버의 is_liked 초기 상태와 0 좋아요를 표시한다', async () => {
  const m = await mount('review-detail', '?id=1', { fetch: async url => url.includes('/me/') ? response({ id: 1, nickname: '독자' }) : url.includes('comments/list') ? response([]) : url.includes('/isbn/') ? response(book) : response({ ...review, is_liked: true }) });
  assert.ok(m.d.querySelector('#heart-icon').src.endsWith('/full_heart.svg')); assert.equal(m.d.querySelector('#review-likes').textContent, '0');
  assert.ok(!m.calls.some(c => c.url.includes('/liked/'))); m.dom.window.close();
});
test('P1 본인 댓글 수정/삭제 버튼은 PATCH/DELETE 계약과 재조회에 연결된다', async () => {
  let content = attack, deleted = false;
  const m = await mount('review-detail', '?id=1', { fetch: async (url, init) => {
    if (url.includes('/me/')) return response({ id: 1, nickname: '독자' });
    if (url.includes('comments/list')) return response(deleted ? [] : [{ id: 7, user: 1, user_nickname: '독자', content }]);
    if (url.endsWith('/comments/')) { const body = JSON.parse(init.body); assert.equal(body.comment_id, 7); if (init.method === 'PATCH') content = body.content; if (init.method === 'DELETE') deleted = true; return response({}); }
    if (url.includes('/liked/')) return response([]); if (url.includes('/isbn/')) return response(book); return response(review);
  } });
  assert.ok(m.d.querySelector('.edit-comment')); m.d.querySelector('.edit-comment').click(); await m.flush();
  assert.equal(m.d.querySelector('.comment-text').textContent, '수정 내용'); assert.ok(m.calls.some(c => c.method === 'PATCH'));
  m.d.querySelector('.delete-comment').click(); await m.flush(); assert.equal(m.d.querySelectorAll('.comment-item').length, 0); assert.ok(m.calls.some(c => c.method === 'DELETE')); m.dom.window.close();
});
test('P1 비밀번호 변경은 현재 비밀번호를 전송하고 성공 후 재로그인을 요구한다', async () => {
  const m = await mount('mypage_edit', '', { nickname: '이전', fetch: async url => url.includes('/me/') ? response({ id: 1, nickname: '이전', profile_image: null }) : response({ message: 'Profile updated successfully.', user: { nickname: '변경' } }) });
  assert.ok(m.d.querySelector('#current-password')); m.d.querySelector('#current-password').value = ' old '; m.d.querySelector('#user-password').value = ' new '; m.d.querySelector('#user-nickname').value = '변경';
  m.d.querySelector('#save-profile').click(); await m.flush(); const body = JSON.parse(m.calls.find(c => c.method === 'PUT').body);
  assert.equal(body.current_password, ' old '); assert.equal(body.password, ' new '); assert.equal(m.w.localStorage.getItem('token'), null); assert.deepEqual(m.errors, []); m.dom.window.close();
});
test('P1 복구 uid/token 폼은 동일 reset-password endpoint에 새 비밀번호를 보낸다', async () => {
  const m = await mount('find-account', '?uid=MQ&token=reset-token', { auth: false, fetch: async () => response({ message: '비밀번호가 변경되었습니다.' }) });
  const jwt = kind => 'eyJhbGciOiJub25lIn0.' + Buffer.from(JSON.stringify({ user_id: 1, token_type: kind })).toString('base64url') + '.synthetic-signature';
  await m.w.AppAPI.saveSession({ access_token: jwt('access'), refresh_token: jwt('refresh'), user: { nickname: 'Synthetic A' } });
  const form = m.d.querySelector('#reset-password-form'); assert.ok(form); assert.equal(form.hidden, false);
  m.d.querySelector('#reset-new-password').value = ' new secret '; m.d.querySelector('#reset-confirm-password').value = ' new secret ';
  form.dispatchEvent(new m.w.Event('submit', { cancelable: true })); await m.flush();
  assert.ok(m.calls[0].url.endsWith('/api/user/reset-password/')); assert.deepEqual(JSON.parse(m.calls[0].body), { uid: 'MQ', token: 'reset-token', new_password: ' new secret ' });
  assert.equal(new Headers(m.calls[0].headers).get('Authorization'), null);
  assert.equal(m.w.localStorage.getItem('token'), null); assert.equal(m.w.localStorage.getItem('refresh_token'), null);
  assert.equal(form.hidden, true); assert.equal(m.d.querySelector('#reset-new-password').value, '');
  assert.equal(m.w.location.search, ''); assert.match(m.d.querySelector('#reset-result').textContent, /변경/); m.dom.window.close();
});
test('P2 최근 도서는 서버 최신순을 유지하고 ISBN 중복을 제거한다', async () => {
  const m = await mount('main', '', { auth: false, fetch: async () => response([{ ...book, isbn: '1', title: '최신' }, { ...book, isbn: '2', title: '이전' }, { ...book, isbn: '1', title: '중복' }]) });
  assert.deepEqual([...m.d.querySelectorAll('.book-title')].map(n => n.textContent), ['최신', '이전']); m.dom.window.close();
});
test('P2 main은 0 목표와 목표 초과 독서량을 보존하고 월별 차트를 정렬한다', async () => {
  const m = await mount('main', '', { fetch: async url => url.includes('recent-reviews') ? response([]) : url.includes('monthly-progress') ? response({ monthly_reading: { '2026-02': 0, '2026-01': 20 } }) : response({ goal_books: 0, read_books: 20 }) });
  assert.equal(m.d.querySelector('#goal-target').textContent, '0권'); assert.equal(m.d.querySelector('#goal-progress').textContent, '20권');
  assert.equal(m.charts.length, 2); const goal = m.charts.find(c => c.id === 'goalChart').config;
  assert.deepEqual(Array.from(goal.data.datasets[0].data), [0, 20]); assert.ok(goal.options.scales.y.max >= 20);
  const month = m.charts.find(c => c.id === 'monthlyChart').config; assert.deepEqual(Array.from(month.data.labels), ['1월', '2월']); assert.deepEqual(Array.from(month.data.datasets[0].data), [20, 0]); m.dom.window.close();
});
test('P1 추천 error 응답은 빈 정상 결과와 구별하고 nullable 제목은 오류를 만들지 않는다', async () => {
  const m = await mount('book-detail', '?isbn=123', { auth: false, fetch: async url => url.includes('/isbn/') ? response({ ...book, title: null }) : url.includes('recommendation') ? response({ error: 'upstream unavailable' }) : response([]) });
  assert.match(m.d.querySelector('#recommendation-grid').textContent, /오류/); assert.deepEqual(m.errors, []); m.dom.window.close();
});
test('P2 사용자/리뷰/토큰 응답 디버그 로그를 남기지 않는다', () => {
  const offenders = fs.readdirSync(path.join(root, 'scripts')).filter(name => !['goals.js', 'mypage.js'].includes(name) && /console\.log\(/.test(fs.readFileSync(path.join(root, 'scripts', name), 'utf8')));
  assert.deepEqual(offenders, []);
});
test('P1 공개 도서/리뷰/댓글은 세션 유무와 무관하게 인증 헤더 없이 조회한다', async () => {
  const publicCalls = [];
  const m = await mount('review-detail', '?id=1', { fetch: async (url, init) => {
    if (url.includes('/me/')) return response({ id: 1, nickname: '독자' });
    if (url.includes('/token/refresh/') || url.includes('/liked/')) return response({}, 401);
    publicCalls.push({ url, init });
    if (url.includes('comments/list')) return response([]); if (url.includes('/isbn/')) return response(book); return response(review);
  } });
  assert.ok(publicCalls.some(c => c.url.includes('comments/list')));
  for (const c of publicCalls) assert.equal(new Headers(c.init.headers).has('Authorization'), false, c.url); m.dom.window.close();
});
test('P0 ISBN URL segment를 인코딩해 쿼리/다른 경로 주입을 막는다', async () => {
  const m = await mount('book-detail', '?isbn=' + encodeURIComponent('123/../../user/me?injected=1'), { auth: false });
  const calls = m.calls.filter(c => c.url.includes('/isbn/') || c.url.includes('/library/'));
  assert.equal(calls.length, 2); for (const c of calls) { assert.ok(c.url.includes('123%2F..%2F..%2Fuser%2Fme%3Finjected%3D1')); assert.equal(new URL(c.url).search, ''); } m.dom.window.close();
});
test('P1 main 기간 요청은 현재 연도를 지정하며 목표404라도 월별 독서량을 조회한다', async () => {
  const m = await mount('main', '', { fetch: async url => url.includes('recent-reviews') ? response([]) : url.includes('monthly-progress') ? response({ monthly_reading: {} }) : response({}, 404) });
  const requests = m.calls.filter(c => c.url.includes('/api/goal/')); assert.equal(requests.length, 2);
  for (const request of requests) assert.equal(new URL(request.url).searchParams.get('year'), new m.w.Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Seoul', year: 'numeric' }).formatToParts(new m.w.Date()).find(part => part.type === 'year').value);
  assert.ok(m.charts.some(c => c.id === 'monthlyChart')); m.dom.window.close();
});
test('P1 만료 access로 로그아웃하면 refresh 후 최신 refresh를 한번 폐기한다', async () => {
  const m = await mount('search'); m.calls.length = 0;
  m.w.fetch = async (url, init) => {
    m.calls.push({ url, ...init });
    if (url.endsWith('/api/auth/token/refresh/')) return response({ access: 'renewed', refresh: 'rotated' });
    if (new Headers(init.headers).get('Authorization') !== 'Bearer renewed') return response({}, 401);
    assert.equal(JSON.parse(init.body).refresh_token, 'rotated'); return response({});
  };
  await m.w.AppAPI.logout();
  assert.equal(m.calls.filter(c => c.url.includes('/token/refresh/')).length, 1);
  assert.equal(m.calls.filter(c => c.url.includes('/logout/')).length, 2);
  assert.equal(m.w.localStorage.getItem('refresh_token'), null); m.dom.window.close();
});
test('P1 refresh 없는 만료 세션도 로컬 인증 정보를 지운다', async () => {
  const m = await mount('search'); m.w.localStorage.removeItem('refresh_token'); m.calls.length = 0;
  m.w.fetch = async (url, init) => { m.calls.push({ url, ...init }); return response({}, 401); };
  assert.equal((await m.w.AppAPI.request('/api/user/me/')).status, 401);
  assert.equal(m.w.localStorage.getItem('token'), null); assert.equal(m.w.localStorage.getItem('username'), null); assert.equal(m.calls.length, 1); m.dom.window.close();
});
test('P1 잘못된 refresh는 무한 재시도 없이 세션을 지운다', async () => {
  const m = await mount('search'); m.calls.length = 0;
  m.w.fetch = async (url, init) => { m.calls.push({ url, ...init }); return response({}, 401); };
  assert.equal((await m.w.AppAPI.request('/api/user/me/')).status, 401); assert.equal(m.calls.length, 2);
  assert.equal(m.w.localStorage.getItem('token'), null); assert.equal(m.w.localStorage.getItem('refresh_token'), null); m.dom.window.close();
});
test('P0 위험/제어문자/credentials URL을 거부하고 정상 HTTPS와 상대 링크를 보존한다', async () => {
  const m = await mount('search');
  for (const value of ['javascript:alert(1)', ' java\nscript:alert(1)', 'data:image/svg+xml,<svg/>', 'vbscript:alert(1)', 'file:///etc/passwd', 'https://user:password@example.test/', '']) assert.equal(m.w.SafeDOM.url(value), '');
  assert.equal(m.w.SafeDOM.url('https://example.test/book'), 'https://example.test/book');
  assert.equal(m.w.SafeDOM.url('/assets/images/logo.png'), 'http://localhost:5500/assets/images/logo.png');
  await assert.rejects(m.w.AppAPI.request('https://attacker.example/api/user/me/')); m.dom.window.close();
});
test('P1 다른 사용자 댓글에는 변경 버튼이 없다', async () => {
  const m = await mount('review-detail', '?id=1', { fetch: async url => url.includes('/me/') ? response({ id: 1, nickname: '같은 표시명' }) : url.includes('comments/list') ? response([{ id: 7, user: 2, user_nickname: '같은 표시명', content: attack }]) : url.includes('/liked/') ? response([]) : url.includes('/isbn/') ? response(book) : response(review) });
  assert.equal(m.d.querySelectorAll('.edit-comment, .delete-comment').length, 0); assertSafe(m.d, '#comment-list'); m.dom.window.close();
});
test('P1 null 도서 메타데이터에는 null/undefined 문자열을 표시하지 않는다', async () => {
  const m = await mount('book-detail', '?isbn=123', { auth: false, fetch: async url => url.includes('/isbn/') ? response({ ...book, author: null, translator: null, publisher: null, published_date: null }) : response([]) });
  for (const id of ['book-author', 'book-publisher']) assert.ok(!/null|undefined/.test(m.d.getElementById(id).textContent)); m.dom.window.close();
});
test('P1 null 리뷰 날짜와 좋아요는 미정 날짜/0으로 표시한다', async () => {
  const m = await mount('review-detail', '?id=1', { auth: false, fetch: async url => url.includes('/isbn/') ? response(book) : url.includes('comments/list') ? response([]) : response({ ...review, likes_count: null, created_at: null }) });
  assert.equal(m.d.querySelector('#review-likes').textContent, '0'); assert.equal(m.d.querySelector('#review-date').textContent, '-'); m.dom.window.close();
});
test('P1 main도 미국 현지 연말이 아니라 서버 서울 연도 기준으로 요청한다', async () => {
  const m = await mount('main', '', { now: '2026-12-31T16:00:00Z', localYear: 2026, fetch: async url => url.includes('recent-reviews') ? response([]) : response({ goal_books: 0, read_books: 0, monthly_reading: {} }) });
  for (const call of m.calls.filter(c => c.url.includes('/api/goal/'))) assert.equal(new URL(call.url).searchParams.get('year'), '2027'); m.dom.window.close();
});
test('P1 공개 상세의 is_liked=false가 로그인 사용자의 저장된 좋아요를 덮지 않는다', async () => {
  const m = await mount('review-detail', '?id=1', { fetch: async (url, init) => {
    if (url.includes('/me/')) return response({ id: 1, nickname: '독자' });
    if (url.includes('/liked/')) {
      assert.equal(new Headers(init.headers).get('Authorization'), 'Bearer access');
      return response([{ review_id: 1 }]);
    }
    if (url.includes('comments/list')) return response([]);
    if (url.includes('/isbn/')) return response(book);
    return response({ ...review, is_liked: false });
  } });
  assert.ok(m.d.querySelector('#heart-icon').src.endsWith('/full_heart.svg'));
  assert.equal(m.calls.filter(c => c.url.includes('/liked/')).length, 1);
  m.dom.window.close();
});
test('P1 가입 비밀번호의 의도된 앞뒤 공백은 로그인 계약과 동일하게 보존한다', async () => {
  const m = await mount('register', '', { auth: false, fetch: async () => response({}, 201) });
  m.d.querySelector('#username').value = 'reader'; m.d.querySelector('#nickname').value = '독자';
  m.d.querySelector('#email').value = 'reader@example.test'; m.d.querySelector('#password').value = ' Strong-reader-key! ';
  m.d.querySelector('#register-form').dispatchEvent(new m.w.Event('submit', { cancelable: true })); await m.flush();
  assert.equal(JSON.parse(m.calls[0].body).password, ' Strong-reader-key! '); m.dom.window.close();
});
test('P2 Chart.js CDN은 검증한 정확한 버전으로 고정된다', () => {
  for (const page of ['main', 'goals']) {
    const dom = new JSDOM(fs.readFileSync(path.join(root, 'screen', page + '.html'), 'utf8'));
    const chart = [...dom.window.document.scripts].find(node => node.src.includes('chart.js'));
    assert.equal(chart?.getAttribute('src'), 'https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js');
    dom.window.close();
  }
});
module.exports = { mount, response, attack, book, review, assertSafe };

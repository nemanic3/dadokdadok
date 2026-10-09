const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { JSDOM, VirtualConsole } = require(process.env.DADOK_TEST_JSDOM || 'jsdom');
const root = path.resolve(__dirname, '..');
const current = '9780132350884';
const attack = '<img src=x onerror="window.__xss=1"><svg onload="window.__xss=2"></svg>';
const candidate = { isbn: '9780201633610', title: attack, author: 'Author', publisher: 'Publisher', image: 'javascript:alert(1)', link: 'javascript:alert(1)' };
function response(data, status = 200) { return { ok: status >= 200 && status < 300, status, json: async () => data }; }
async function mount({ auth = true, personalized = [candidate], personalizedStatus = 200, naver = [candidate], naverStatus = 200 } = {}) {
  const calls = [], errors = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', error => errors.push(error.message));
  const dom = new JSDOM(fs.readFileSync(path.join(root, 'screen/book-detail.html'), 'utf8'), { url: 'http://localhost:5500/screen/book-detail.html?isbn=' + current, runScripts: 'outside-only', virtualConsole: vc });
  const w = dom.window;
  await new Promise(resolve => w.addEventListener('load', resolve, { once: true }));
  w.Headers = global.Headers;
  w.alert = () => {};
  if (auth) w.localStorage.setItem('token', 'fixture-access');
  w.fetch = async (url, init) => {
    const parsed = new URL(url);
    calls.push({ url: String(url), init });
    if (parsed.pathname === '/api/book/isbn/' + current + '/') return response({ isbn: current, title: '현재 제목', author: 'A', image_url: '', link: '' });
    if (parsed.pathname === '/api/review/library/' + current + '/') return response([]);
    if (parsed.pathname === '/api/recommendation/personalized/') return response(personalized, personalizedStatus);
    if (parsed.pathname === '/api/recommendation/naver/') return response(naver, naverStatus);
    throw new Error('Unexpected request: ' + url);
  };
  for (const script of w.document.querySelectorAll('script[src]')) {
    w.eval(fs.readFileSync(path.join(root, new URL(script.src).pathname), 'utf8'));
  }
  w.document.dispatchEvent(new w.Event('DOMContentLoaded'));
  for (let i = 0; i < 10; i++) await new Promise(resolve => setImmediate(resolve));
  return { dom, w, d: w.document, calls, errors };
}
function recommendationCalls(m) { return m.calls.filter(call => new URL(call.url).pathname.startsWith('/api/recommendation/')); }
function assertSafeGrid(m) {
  const grid = m.d.querySelector('#recommendation-grid');
  assert.equal(grid.querySelectorAll('.recommendation-item').length, 1);
  assert.equal(grid.querySelectorAll('svg, script, [onerror], [onload]').length, 0);
  assert.equal(grid.querySelector('p').textContent, attack);
  assert.equal(grid.querySelector('a').hasAttribute('href'), false);
  assert.ok(!grid.querySelector('img').src.startsWith('javascript:'));
  assert.equal(grid.style.display, 'grid');
  assert.equal(grid.style.minHeight, '200px');
  assert.deepEqual(m.errors, []);
}
test('로그인 상세 화면은 같은 안전한 grid에 개인화 추천을 우선 표시한다', async () => {
  const m = await mount();
  try {
    const calls = recommendationCalls(m);
    assert.deepEqual(calls.map(call => new URL(call.url).pathname), ['/api/recommendation/personalized/']);
    assert.equal(new URL(calls[0].url).searchParams.get('isbn'), current);
    assert.equal(new Headers(calls[0].init.headers).get('Authorization'), 'Bearer fixture-access');
    assertSafeGrid(m);
  } finally { m.dom.window.close(); }
});
test('개인화 후보가 없으면 네이버 관련추천으로 한번 fallback한다', async () => {
  const m = await mount({ personalized: [] });
  try {
    const calls = recommendationCalls(m);
    assert.deepEqual(calls.map(call => new URL(call.url).pathname), ['/api/recommendation/personalized/', '/api/recommendation/naver/']);
    const fallback = new URL(calls[1].url);
    assert.equal(fallback.searchParams.get('isbn'), current);
    assert.equal(fallback.searchParams.get('query'), '현재 제목');
    assert.equal(new Headers(calls[1].init.headers).has('Authorization'), false);
    assertSafeGrid(m);
  } finally { m.dom.window.close(); }
});
test('익명은 개인화를 호출하지 않고 기존 공개 네이버 흐름과 클래스/안전한 DOM을 보존한다', async () => {
  const m = await mount({ auth: false });
  try {
    assert.deepEqual(recommendationCalls(m).map(call => new URL(call.url).pathname), ['/api/recommendation/naver/']);
    for (const call of m.calls) assert.equal(new Headers(call.init.headers).has('Authorization'), false);
    assertSafeGrid(m);
  } finally { m.dom.window.close(); }
});

test('개인화 오류에도 공개 관련추천 fallback으로 기존 상세 기능이 유지된다', async () => {
  const m = await mount({ personalizedStatus: 503, personalized: { error: 'service unavailable' } });
  try {
    assert.deepEqual(recommendationCalls(m).map(call => new URL(call.url).pathname), ['/api/recommendation/personalized/', '/api/recommendation/naver/']);
    assertSafeGrid(m);
  } finally { m.dom.window.close(); }
});

test('정상 빈 네이버 목록과 502/504 장애는 서로 다른 grid 메시지다', async () => {
  for (const status of [200, 502, 504]) {
    const m = await mount({ auth: false, naver: status === 200 ? [] : { error: 'upstream failed' }, naverStatus: status });
    try {
      assert.match(m.d.querySelector('#recommendation-grid').textContent, status === 200 ? /추천할 도서가 없습니다/ : /오류가 발생/);
      assert.equal(m.d.querySelector('#recommendation-grid').style.minHeight, '200px');
    } finally { m.dom.window.close(); }
  }
});

test('actual HTML/scripts에서 관측한 GET 경로는 Django URLconf에 실제 존재한다', async () => {
  const m = await mount({ personalized: [] });
  try {
    const paths = [...new Set(m.calls.map(call => new URL(call.url).pathname))];
    assert.equal(paths.length, 4);
    const project = path.resolve(process.env.DADOK_PROJECT_ROOT || path.resolve(root, '..'));
    const backend = path.join(project, 'backend');
    const python = process.env.DADOK_TEST_PYTHON || ['.venv-dev', '.venv-runtime', '.venv']
      .map(name => path.join(project, name, 'bin/python')).find(file => fs.existsSync(file)) || 'python3';
    const result = spawnSync(python, ['-B', '-c', `
import json, os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'dadokdadok.settings'
import django
django.setup()
from django.urls import resolve
paths = json.loads(sys.argv[1])
for route in paths:
    match = resolve(route)
    assert match.func is not None, route
print(json.dumps({'resolved_get_paths': paths}))
`, JSON.stringify(paths)], { cwd: backend, encoding: 'utf8', env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', DJANGO_DEBUG: '1', DJANGO_SECRET_KEY: 'isolated-finalization-tests-not-production-key', JWT_SIGNING_KEY: 'isolated-finalization-tests-not-production-key', DJANGO_DB_PATH: ':memory:' } });
    assert.equal(result.status, 0, result.error?.message || String(result.stdout || '') + String(result.stderr || ''));
    assert.deepEqual(JSON.parse(result.stdout).resolved_get_paths, paths);
  } finally { m.dom.window.close(); }
});

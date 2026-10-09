#!/usr/bin/env python3
"""Real Chromium E2E against isolated Django WSGI and original static files.

Run from the repository with .venv-dev/bin/python -B tests/browser_smoke.py.
Install optional Playwright tools as documented in README before rerunning.
Only the Naver upstream HTTP response is synthetic; APIs/JWT/DB/DOM/Chart are real.
No existing DB, CSS, source, credentials, SMTP, or remote accounts are modified.
Evidence is redacted; no HAR/trace, response bodies, passwords or tokens are logged.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import http.server
import io
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path(tempfile.gettempdir()) / 'dadokdadok-browser-smoke'
CDN = {
    'chart': ('https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js', 'chart-4.5.1.umd.min.js', 'application/javascript'),
    'pretendard': ('https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/static/pretendard.css', 'pretendard-1.3.9.css', 'text/css'),
}
CHART_SRI = 'sha384-jb8JQMbMoBUzgWatfe6COACi2ljcDdZQ2OxczGA3bGNeWe+6DChMTBJemed7ZnvJ'
PREOBTAINED_CHART = DEFAULT_OUTPUT / 'chart.umd.min.js'
XSS = '<img src=x onerror="window.__smokeXSS=1"><script>window.__smokeXSS=2</script>'
BOOK_ISBN = '9780132350884'
SECRETS: list[str] = []
FLOW_LABELS = {
    'signup_browser': '브라우저 회원가입', 'email_login_browser': '이메일 로그인',
    'network_outside_loopback_denied': '루프백 외 Python·브라우저 네트워크 차단',
    'empty_library': '빈 내 서재 표시', 'mock_upstream_search_to_detail': '검색 → 도서 상세 (네이버 상류만 모의)',
    'recommendations_real_api_mock_upstream': '실제 추천 API·모의 상류', 'new_book_empty_reviews_state': '신규 도서 빈 리뷰 안내',
    'review_create_browser_readback': '리뷰 작성 및 실제 API 재조회', 'review_xss_inert': '리뷰 XSS 문자열 비실행',
    'review_edit_browser_readback': '리뷰 수정 및 재조회', 'second_user_signup_login_browser': '두 번째 사용자 가입·로그인',
    'two_user_review_owner_denial_real_api': '타 사용자 리뷰 변경·삭제 거부', 'liked_toggle_reload_persistence': '좋아요 토글·새로고침 저장 유지',
    'comment_add_browser_xss_inert': '댓글 작성·XSS 비실행', 'two_user_comment_owner_denial_real_api': '타 사용자 댓글 변경·삭제 거부',
    'comment_edit_browser_readback': '댓글 수정·재조회', 'comment_delete_browser_readback': '댓글 삭제·재조회',
    'yearly_monthly_target_create_update_readback': '연간·월간 목표 생성·수정·재조회',
    'real_chartjs_goal_and_main_render': '실제 Chart.js 4.5.1·SRI·목표/메인 차트',
    'goal_heading_explanation_no_overlap': '목표 제목·설명 겹침 없음',
    'profile_selected_image_nickname_persistence': '선택 프로필 이미지·닉네임 저장 유지',
    'expired_access_real_jwt_refresh_retry': '만료된 실제 JWT → refresh → 요청 재시도',
    'review_delete_browser_readback': '리뷰 삭제·재조회',
    'password_change_new_login_refresh_revoked': '비밀번호 변경·새 로그인·기존 refresh 폐기',
    'reset_request_browser_locmem_mail': '브라우저 복구 요청·locmem 메일 생성',
    'reset_mail_link_browser_confirm_new_login': '메일 링크 → 브라우저 재설정·새 로그인',
    'reset_one_time_reuse_denied_browser': '일회용 복구 링크 재사용 거부',
    'logout_browser_refresh_blacklist': '브라우저 로그아웃·refresh 블랙리스트',
    'mobile_horizontal_overflow': '390px 모바일 가로 넘침 없음', 'no_uncaught_javascript_errors': '미처리 JavaScript 오류 없음',
    'original_db_sha256_unchanged': '원본 SQLite SHA256 보존', 'original_css_unchanged': '원본 CSS 보존',
    'own_servers_shutdown': '직접 시작한 서버 종료·포트 폐쇄',
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def redact(value):
    text = str(value)
    for secret in SECRETS:
        if secret:
            text = text.replace(secret, '[REDACTED]')
    text = re.sub(r'https?://[^\s\"\'<>]+\?(?:[^\s\"\'<>]*)(?:uid|token)=[^\s\"\'<>]+', '[REDACTED_RESET_URL]', text)
    text = re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[REDACTED_JWT]', text)
    return text[:3000]


def obtain_assets(base, allow_download):
    cache = base / 'cdn-cache'
    cache.mkdir(parents=True, exist_ok=True)
    assets, metadata = {}, {}
    for key, (url, filename, mime) in CDN.items():
        path = cache / filename
        sri = None
        try:
            if not path.exists() and key == 'chart' and PREOBTAINED_CHART.exists():
                supplied = PREOBTAINED_CHART.read_bytes()
                sri = 'sha384-' + base64.b64encode(hashlib.sha384(supplied).digest()).decode()
                if sri != CHART_SRI:
                    raise RuntimeError('Pre-obtained real Chart.js does not match exact SRI')
                path.write_bytes(supplied)
            if not path.exists():
                if not allow_download:
                    raise RuntimeError('Missing pinned CDN cache; rerun with --obtain-cdn for read-only approved CDN assets')
                # Fixed read-only allowlist; no user-provided URL, credentials or redirects.
                class NoRedirect(urllib.request.HTTPRedirectHandler):
                    def redirect_request(self, *args, **kwargs):
                        raise RuntimeError('CDN redirects are not allowed')
                opener = urllib.request.build_opener(NoRedirect())
                with opener.open(url, timeout=30) as response:
                    data = response.read(2_000_001)
                if len(data) > 2_000_000:
                    raise RuntimeError('CDN asset exceeds bounded download size')
                if key == 'chart' and b'Chart.js v4.5.1' not in data[:1000]:
                    raise RuntimeError('Unexpected Chart.js version/header')
                if key == 'pretendard' and b'@font-face' not in data:
                    raise RuntimeError('Unexpected Pretendard stylesheet')
                path.write_bytes(data)
            data = path.read_bytes()
            if key == 'chart':
                sri = 'sha384-' + base64.b64encode(hashlib.sha384(data).digest()).decode()
                if b'Chart.js v4.5.1' not in data[:1000] or sri != CHART_SRI:
                    raise RuntimeError('Cached Chart.js does not match pinned version and exact SRI')
            assets[key] = (data, mime)
            metadata[key] = {'source': url, 'path': str(path), 'sha256': digest(path), 'bytes': len(data), 'available': True}
            if key == 'chart':
                metadata[key]['integrity'] = sri
        except Exception as exc:
            metadata[key] = {'source': url, 'available': False, 'error': redact(exc)}
    return assets, metadata


@contextlib.contextmanager
def loopback_only():
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create = socket.create_connection

    def check(address):
        if not isinstance(address, tuple):
            return  # AF_UNIX is local IPC.
        host = address[0]
        if host == 'localhost':
            return
        try:
            allowed = ipaddress.ip_address(host).is_loopback
        except ValueError:
            allowed = False
        if not allowed:
            raise OSError('Smoke harness denied non-loopback Python network')

    def connect(sock, address):
        check(address)
        return original_connect(sock, address)

    def connect_ex(sock, address):
        check(address)
        return original_connect_ex(sock, address)

    def create(address, *args, **kwargs):
        check(address)
        return original_create(address, *args, **kwargs)

    socket.socket.connect, socket.socket.connect_ex, socket.create_connection = connect, connect_ex, create
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex, socket.create_connection = original_connect, original_connect_ex, original_create


class QuietStatic(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


class QuietWSGI(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass

    def get_stderr(self):
        return io.StringIO()  # Never emit recovery query strings or auth request context.


class ThreadedWSGI(ThreadingMixIn, WSGIServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass


class Harness:
    def __init__(self, output, assets, cdn):
        self.output, self.assets = output, assets
        self.report = {'mode': 'real Chromium + real Django WSGI + isolated SQLite', 'tests': [],
                       'python_executable': sys.executable,
                       'api_statuses': [], 'js_errors': [], 'console_errors': [], 'blocked_external': [],
                       'screenshots': [], 'source_findings': [], 'cdn': cdn, 'limits': [
                           '네이버 requests.get 상류 응답만 합성 데이터입니다. 실제 네이버 서비스·자격정보 성공은 검증하지 않았습니다.',
                           '허용된 읽기 전용 CDN 파일은 고정된 실제 Chart.js·Pretendard CSS뿐이며 브라우저에 동일 캐시 바이트를 제공합니다.',
                           '외부 폰트 파일은 차단합니다. 스크린샷에는 대체 폰트가 쓰일 수 있어 CDN 글꼴의 정확한 외형은 미검증입니다.',
                           '기존 CSS 그대로 데스크톱·모바일 캡처 및 일부 레이아웃 검사를 했습니다. 픽셀 기준선·전체 접근성 감사는 아닙니다.',
                           '로컬 HTTP·locmem 메일만 검증했습니다. 운영 HTTPS·SMTP 전달·유료 계정·배포는 하지 않았습니다.',
                           '실제 JWT를 합성 서명키로 발급하고 만료시간을 과거로 설정합니다. 기본 한 시간 만료를 기다리는 테스트는 아닙니다.',
                       ]}
        self.servers, self.threads, self.contexts = [], [], []
        self.passed, self.state = set(), {}
        self.prompt_value = None
        self.current_test = 'setup'

    def log(self, text):
        text = redact(text)
        with (self.output / 'smoke.log').open('a') as stream:
            stream.write(text + '\n')
        print(text, flush=True)

    def start_servers(self):
        static = http.server.ThreadingHTTPServer(('127.0.0.1', 0),
            lambda *a, **kw: QuietStatic(*a, directory=str(ROOT / 'frontend'), **kw))
        self.servers.append(static)
        self.front = f'http://127.0.0.1:{static.server_port}'
        db = self.output / f'isolated-{uuid.uuid4().hex}.sqlite3'
        assert db.resolve() != (ROOT / 'backend/db.sqlite3').resolve() and not db.exists()
        # Explicit synthetic values override any local credential file; never read/print it.
        os.environ.update(DJANGO_SETTINGS_MODULE='dadokdadok.settings', DJANGO_DEBUG='1',
            DJANGO_SECRET_KEY='synthetic-browser-smoke-only-not-production-signing-key',
            JWT_SIGNING_KEY='synthetic-browser-smoke-only-not-production-signing-key',
            DJANGO_DB_PATH=str(db), DJANGO_ALLOWED_HOSTS='127.0.0.1,localhost',
            DJANGO_CORS_ALLOWED_ORIGINS=self.front, NAVER_CLIENT_ID='', NAVER_CLIENT_SECRET='',
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', EMAIL_HOST_USER='',
            EMAIL_HOST_PASSWORD='', PASSWORD_RESET_URL=self.front + '/screen/find-account.html')
        sys.path.insert(0, str(ROOT / 'backend'))
        import django
        django.setup()
        from django.conf import settings
        assert settings.DATABASES['default']['NAME'] == str(db)
        assert settings.EMAIL_BACKEND == 'django.core.mail.backends.locmem.EmailBackend'
        assert not settings.NAVER_CLIENT_ID and not settings.NAVER_CLIENT_SECRET
        self.report['django_version'] = django.get_version()
        self.report['isolated_database'] = str(db)
        from django.core.management import call_command
        call_command('migrate', verbosity=0, interactive=False, stdout=io.StringIO(), stderr=io.StringIO())
        # Disable request/console logging; our evidence records method/path/status only.
        logging.disable(logging.CRITICAL)
        import requests
        self.original_get = requests.get
        front = self.front
        fixture = [
            {'title': '스모크 테스트 도서', 'author': '테스트 저자', 'publisher': '격리 출판사',
             'pubdate': '20200101', 'isbn': BOOK_ISBN, 'image': front + '/assets/images/logo.png',
             'link': front + '/screen/book-detail.html?isbn=' + BOOK_ISBN, 'description': '격리 도서 설명'},
            {'title': '연관 테스트 도서', 'author': '다른 저자', 'publisher': '격리 출판사',
             'pubdate': '20200101', 'isbn': '9780201633610', 'image': front + '/assets/images/logo.png',
             'link': front + '/screen/book-detail.html?isbn=9780201633610', 'description': '격리 연관 도서'},
        ]
        self.report['naver_upstream_calls'] = 0

        def naver_get(url, *args, **kwargs):
            if url != settings.NAVER_BOOKS_API_URL:
                return self.original_get(url, *args, **kwargs)
            self.report['naver_upstream_calls'] += 1
            query = str(kwargs.get('params', {}).get('query', ''))
            items = [book for book in fixture if query in book['isbn']] if query.isdecimal() else fixture
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({'items': items, 'total': len(items)}, ensure_ascii=False).encode()
            response.headers['Content-Type'] = 'application/json'
            return response
        requests.get = naver_get
        from django.core.wsgi import get_wsgi_application
        api = make_server('127.0.0.1', 0, get_wsgi_application(), server_class=ThreadedWSGI, handler_class=QuietWSGI)
        self.servers.append(api)
        self.api = f'http://127.0.0.1:{api.server_port}'
        self.report.update(frontend_origin=self.front, api_origin=self.api)
        for server in self.servers:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)
        with urllib.request.urlopen(self.api + '/', timeout=10) as response:
            assert response.status == 200
        with urllib.request.urlopen(self.front + '/screen/index.html', timeout=10) as response:
            assert response.status == 200

    def new_page(self, browser):
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, service_workers='block')
        context.add_init_script('window.DADOK_API_BASE_URL = ' + json.dumps(self.api) + '; window.__smokeXSS = 0;')
        context.route('**/*', self.route)
        page = context.new_page()
        page.set_default_timeout(12000)
        page.on('dialog', lambda dialog: dialog.accept(self.prompt_value or '수정된 안전 댓글') if dialog.type == 'prompt' else dialog.accept())
        page.on('pageerror', lambda error: self.report['js_errors'].append({'test': self.current_test, 'message': redact(error)}))
        # Console body can contain application data/tokens; capture error location/type only.
        page.on('console', lambda msg: self.report['console_errors'].append(
            {'test': self.current_test, 'type': msg.type, 'location': self.safe_location(msg.location)}) if msg.type == 'error' else None)
        page.on('response', self.response)
        self.contexts.append(context)
        return page

    @staticmethod
    def safe_location(location):
        return {'path': urllib.parse.urlsplit(location.get('url', '')).path,
                'line': location.get('lineNumber'), 'column': location.get('columnNumber')}

    def route(self, route):
        parsed = urllib.parse.urlsplit(route.request.url)
        origin = f'{parsed.scheme}://{parsed.netloc}'
        if origin in (self.front, self.api):
            route.continue_()
            return
        key = None
        if parsed.hostname == 'cdn.jsdelivr.net':
            if parsed.path in ('/npm/chart.js', '/npm/chart.js@4.5.1/dist/chart.umd.min.js'):
                key = 'chart'
            elif parsed.path in ('/npm/pretendard/dist/web/static/pretendard.css',
                                  '/gh/orioncactus/pretendard/dist/web/static/pretendard.css',
                                  '/gh/orioncactus/Pretendard/dist/web/static/pretendard.css',
                                  '/npm/pretendard@1.3.9/dist/web/static/pretendard.css'):
                key = 'pretendard'
        if key in self.assets:
            body, mime = self.assets[key]
            route.fulfill(status=200, body=body, content_type=mime, headers={'Access-Control-Allow-Origin': '*'})
            return
        self.report['blocked_external'].append({'host': parsed.hostname, 'path': parsed.path, 'type': route.request.resource_type})
        route.abort('blockedbyclient')

    def response(self, response):
        path = urllib.parse.urlsplit(response.url).path
        if path.startswith('/api/'):
            self.report['api_statuses'].append({'test': self.current_test, 'method': response.request.method,
                                              'path': path, 'status': response.status})

    def goto(self, page, name):
        self.last_page = page
        page.goto(self.front + '/screen/' + name, wait_until='networkidle')

    def screenshots(self, page, name):
        assert 'token=' not in page.url and 'uid=' not in page.url, 'Never capture reset credential URLs'
        for size, viewport in [('desktop', {'width': 1440, 'height': 1000}), ('mobile', {'width': 390, 'height': 844})]:
            page.set_viewport_size(viewport)
            page.wait_for_timeout(200)
            path = self.output / 'screenshots' / f'{name}-{size}.png'
            page.screenshot(path=str(path), full_page=True)
            layout = page.evaluate('({viewport:innerWidth,document:document.documentElement.scrollWidth})')
            self.report['screenshots'].append({'name': name, 'viewport': size, 'path': str(path),
                                               'bytes': path.stat().st_size, 'sha256': digest(path), 'layout': layout})
        page.set_viewport_size({'width': 1440, 'height': 1000})

    def check(self, name, fn, requires=()):
        self.current_test = name
        missing = [dep for dep in requires if dep not in self.passed]
        if missing:
            self.report['tests'].append({'name': name, 'status': 'blocked', 'requires': missing})
            self.log(f'BLOCKED {name}: prerequisite failure')
            return
        started = time.monotonic()
        try:
            fn()
            self.passed.add(name)
            result = {'name': name, 'status': 'pass'}
            self.log('PASS ' + name)
        except Exception as exc:
            result = {'name': name, 'status': 'fail', 'error': redact(exc), 'exception': type(exc).__name__}
            self.log('FAIL ' + name + ': ' + result['error'])
            page = getattr(self, 'last_page', None)
            if page and not page.is_closed() and 'token=' not in page.url and 'uid=' not in page.url:
                try:
                    self.screenshots(page, 'failure-' + name)
                except Exception:
                    result['screenshot_capture_failed'] = True
        result['seconds'] = round(time.monotonic() - started, 3)
        self.report['tests'].append(result)
        (self.output / 'results.json').write_text(json.dumps(self.report, ensure_ascii=False, indent=2))

    def api_call(self, page, path, method='GET', body=None, auth=True):
        # Native browser fetch over real HTTP. Do not replace fetch, storage or any API.
        return page.evaluate('''async ({base,path,method,body,auth}) => {
            const headers = {'Content-Type':'application/json'};
            if(auth && localStorage.getItem('token')) headers.Authorization='Bearer '+localStorage.getItem('token');
            const response=await fetch(base+path,{method,headers,...(body===null?{}:{body:JSON.stringify(body)})});
            let data=null; try{data=await response.json()}catch{}
            return {status:response.status,data};
        }''', {'base': self.api, 'path': path, 'method': method, 'body': body, 'auth': auth})

    @staticmethod
    def status(result, expected):
        assert result['status'] == expected, f'Expected HTTP {expected}, got {result["status"]}'
        return result['data']

    def ui_response(self, page, path, method, action, expected):
        self.last_page = page
        with page.expect_response(lambda r: urllib.parse.urlsplit(r.url).path == path and r.request.method == method) as pending:
            action()
        response = pending.value
        assert response.status == expected, f'{method} {path}: expected {expected}, got {response.status}'
        return response

    def signup(self, page, username, nickname, email, password):
        self.goto(page, 'register.html')
        for field, value in [('username', username), ('nickname', nickname), ('email', email), ('password', password)]:
            page.locator('#' + field).fill(value)
        self.ui_response(page, '/api/user/signup/', 'POST', lambda: page.locator('#register-form button[type=submit]').click(), 201)
        page.wait_for_url('**/screen/index.html')

    def login(self, page, email, password):
        self.goto(page, 'index.html')
        page.locator('#username').fill(email)
        page.locator('#password').fill(password)
        self.ui_response(page, '/api/user/login/', 'POST', lambda: page.locator('#login-form button[type=submit]').click(), 200)
        page.wait_for_url('**/screen/welcome.html')
        page.wait_for_function("document.getElementById('user-name').textContent !== 'OO'")
        assert page.evaluate("Boolean(localStorage.getItem('token') && localStorage.getItem('refresh_token'))")

    def run_flows(self, browser):
        from playwright.sync_api import expect
        p, p2 = self.new_page(browser), self.new_page(browser)
        self.page = p
        email, email2 = 'smoke-owner@example.invalid', 'smoke-other@example.invalid'
        password, changed, reset = 'Synthetic-Smoke!7392A', 'Synthetic-Change!8421B', 'Synthetic-Reset!9537C'
        SECRETS.extend([password, changed, reset])

        def signup_owner():
            self.screenshots_before_signup(p)
            self.signup(p, 'smoke-owner', '스모크작성자', email, password)
        self.check('signup_browser', signup_owner)
        self.check('email_login_browser', lambda: self.login(p, email, password), ('signup_browser',))

        def network_guard():
            try:
                socket.create_connection(('192.0.2.1', 443), timeout=1)
            except OSError as exc:
                assert 'denied non-loopback' in str(exc)
            else:
                raise AssertionError('Python external network was not denied')
            before = len(self.report['blocked_external'])
            blocked = p.evaluate("async () => {try {await fetch('https://smoke-network-denied.invalid/probe');return false;}catch{return true;}}")
            assert blocked, 'Browser external fetch must be denied'
            assert any(item['host'] == 'smoke-network-denied.invalid' for item in self.report['blocked_external'][before:])
        self.check('network_outside_loopback_denied', network_guard, ('email_login_browser',))

        def empty_library():
            self.goto(p, 'library.html')
            expect(p.locator('#book-grid')).to_contain_text('아직 작성한 리뷰가 없습니다')
            self.status(self.api_call(p, '/api/review/library/'), 200)
            assert self.api_call(p, '/api/review/library/')['data'] == []
            self.screenshots(p, 'empty-library')
        self.check('empty_library', empty_library, ('email_login_browser',))

        def search_detail():
            self.goto(p, 'search.html?query=' + urllib.parse.quote('스모크'))
            expect(p.locator('.book-item')).to_have_count(2)
            expect(p.locator('.book-item h3').first).to_have_text('스모크 테스트 도서')
            self.screenshots(p, 'search')
            p.locator('.book-cover-container').first.click()
            p.wait_for_url('**/book-detail.html?isbn=' + BOOK_ISBN)
            expect(p.locator('#book-title')).to_have_text('스모크 테스트 도서')
            self.screenshots(p, 'book-detail')
        self.check('mock_upstream_search_to_detail', search_detail, ('email_login_browser',))

        def recommendations():
            expect(p.locator('#recommendation-grid .recommendation-item')).to_have_count(1)
            expect(p.locator('#recommendation-grid')).to_contain_text('연관 테스트 도서')
        self.check('recommendations_real_api_mock_upstream', recommendations, ('mock_upstream_search_to_detail',))

        def new_book_empty_reviews():
            actual = p.locator('#reviews-list').inner_text().strip()
            if '아직 리뷰가 없습니다' not in actual:
                self.report['source_findings'].append({'name': 'new_book_empty_reviews_state', 'severity': 'medium',
                    'source': 'backend/review/views.py:203-206; frontend/scripts/book-detail.js:64,86-88',
                    'expected': 'Externally searched valid ISBN with no saved Book/reviews should show empty review state.',
                    'actual': 'Real reviews endpoint returns 404; frontend logs an error and leaves reviews-list blank.',
                    'screenshot': str(self.output / 'screenshots/book-detail-desktop.png')})
            assert '아직 리뷰가 없습니다' in actual, 'Valid new book detail has blank reviews instead of explicit empty state (real API 404)'
        self.check('new_book_empty_reviews_state', new_book_empty_reviews, ('mock_upstream_search_to_detail',))

        def review_create():
            p.locator('#write-review-btn').click()
            p.wait_for_url('**/review-write.html?isbn=' + BOOK_ISBN)
            expect(p.locator('#book-title')).to_have_text('스모크 테스트 도서')
            p.locator('#review-text').fill(XSS)
            p.locator('.star').nth(4).click(position={'x': 2, 'y': 4})
            self.screenshots(p, 'review-write')
            response = self.ui_response(p, '/api/review/', 'POST', lambda: p.locator('#publish-review').click(), 201)
            review_id = response.json()['id']
            self.state['review_id'] = review_id
            p.wait_for_url('**/review-detail.html?id=' + str(review_id))
            expect(p.locator('#review-text')).to_have_text(XSS)
            data = self.status(self.api_call(p, f'/api/review/{review_id}/', auth=False), 200)
            assert data['content'] == XSS and data['rating'] == 4.5
        self.check('review_create_browser_readback', review_create, ('mock_upstream_search_to_detail',))

        def assert_inert(page, selector, text):
            expect(page.locator(selector)).to_have_text(text)
            assert page.locator(selector + ' img, ' + selector + ' script').count() == 0
            assert page.evaluate('window.__smokeXSS') == 0
        self.check('review_xss_inert', lambda: (assert_inert(p, '#review-text', XSS), self.screenshots(p, 'review-detail')), ('review_create_browser_readback',))

        def review_edit():
            rid = self.state['review_id']
            p.locator('#edit-button').click()
            p.wait_for_url('**/review-write.html?id=' + str(rid))
            expect(p.locator('#review-text')).to_have_value(XSS)
            p.locator('#review-text').fill('수정된 리뷰 ' + XSS)
            self.ui_response(p, f'/api/review/{rid}/', 'PUT', lambda: p.locator('#publish-review').click(), 200)
            p.wait_for_url('**/review-detail.html?id=' + str(rid))
            assert_inert(p, '#review-text', '수정된 리뷰 ' + XSS)
            data = self.status(self.api_call(p, f'/api/review/{rid}/', auth=False), 200)
            assert data['content'] == '수정된 리뷰 ' + XSS
        self.check('review_edit_browser_readback', review_edit, ('review_create_browser_readback',))

        def second_user():
            self.signup(p2, 'smoke-other', '스모크다른사용자', email2, password)
            self.login(p2, email2, password)
        self.check('second_user_signup_login_browser', second_user)

        def owner_denial():
            rid = self.state['review_id']
            self.goto(p2, f'review-detail.html?id={rid}')
            expect(p2.locator('#edit-button')).to_be_hidden()
            expect(p2.locator('#delete-button')).to_be_hidden()
            before = self.status(self.api_call(p2, f'/api/review/{rid}/', auth=False), 200)
            for method, body in [('PUT', {'content': 'denied', 'rating': 1}), ('PATCH', {'content': 'denied'}), ('DELETE', None)]:
                self.status(self.api_call(p2, f'/api/review/{rid}/', method, body), 403)
            after = self.status(self.api_call(p2, f'/api/review/{rid}/', auth=False), 200)
            assert after['content'] == before['content']
        self.check('two_user_review_owner_denial_real_api', owner_denial, ('second_user_signup_login_browser', 'review_create_browser_readback'))

        def likes():
            rid = self.state['review_id']
            self.goto(p2, f'review-detail.html?id={rid}')
            expect(p2.locator('#heart-icon')).to_have_attribute('src', '/assets/images/empty_heart.svg')
            self.ui_response(p2, f'/api/review/{rid}/like/', 'POST', lambda: p2.locator('#heart-icon').click(), 201)
            expect(p2.locator('#heart-icon')).to_have_attribute('src', '/assets/images/full_heart.svg')
            p2.reload(wait_until='networkidle')
            expect(p2.locator('#heart-icon')).to_have_attribute('src', '/assets/images/full_heart.svg')
            assert {'review_id': rid} in self.status(self.api_call(p2, '/api/review/liked/'), 200)
            self.ui_response(p2, f'/api/review/{rid}/like/', 'POST', lambda: p2.locator('#heart-icon').click(), 200)
            p2.reload(wait_until='networkidle')
            expect(p2.locator('#heart-icon')).to_have_attribute('src', '/assets/images/empty_heart.svg')
            assert {'review_id': rid} not in self.status(self.api_call(p2, '/api/review/liked/'), 200)
        self.check('liked_toggle_reload_persistence', likes, ('second_user_signup_login_browser', 'review_create_browser_readback'))

        def comment_add():
            rid = self.state['review_id']
            self.goto(p2, f'review-detail.html?id={rid}')
            p2.locator('#comment-input').fill(XSS)
            self.ui_response(p2, f'/api/review/{rid}/comments/', 'POST', lambda: p2.locator('#comment-input').press('Enter'), 201)
            assert_inert(p2, '.comment-text', XSS)
            comments = self.status(self.api_call(p2, f'/api/review/{rid}/comments/list/', auth=False), 200)
            assert len(comments) == 1 and comments[0]['content'] == XSS
            self.state['comment_id'] = comments[0]['id']
            self.screenshots(p2, 'comment-xss')
        self.check('comment_add_browser_xss_inert', comment_add, ('second_user_signup_login_browser', 'review_create_browser_readback'))

        def comment_denial():
            rid, cid = self.state['review_id'], self.state['comment_id']
            for method, body in [('PATCH', {'content': 'denied'}), ('DELETE', None)]:
                self.status(self.api_call(p, f'/api/review/{rid}/comments/{cid}/', method, body), 403)
            comments = self.status(self.api_call(p, f'/api/review/{rid}/comments/list/', auth=False), 200)
            assert len(comments) == 1 and comments[0]['content'] == XSS
        self.check('two_user_comment_owner_denial_real_api', comment_denial, ('comment_add_browser_xss_inert', 'email_login_browser'))

        def comment_edit():
            rid = self.state['review_id']
            self.prompt_value = '수정 댓글 ' + XSS
            try:
                self.ui_response(p2, f'/api/review/{rid}/comments/', 'PATCH', lambda: p2.locator('.edit-comment').click(), 200)
            finally:
                self.prompt_value = None
            assert_inert(p2, '.comment-text', '수정 댓글 ' + XSS)
            p2.reload(wait_until='networkidle')
            assert_inert(p2, '.comment-text', '수정 댓글 ' + XSS)
            comments = self.status(self.api_call(p2, f'/api/review/{rid}/comments/list/', auth=False), 200)
            assert comments[0]['content'] == '수정 댓글 ' + XSS
        self.check('comment_edit_browser_readback', comment_edit, ('comment_add_browser_xss_inert',))

        def comment_delete():
            rid = self.state['review_id']
            self.ui_response(p2, f'/api/review/{rid}/comments/', 'DELETE', lambda: p2.locator('.delete-comment').click(), 200)
            expect(p2.locator('.comment-item')).to_have_count(0)
            assert self.status(self.api_call(p2, f'/api/review/{rid}/comments/list/', auth=False), 200) == []
        self.check('comment_delete_browser_readback', comment_delete, ('comment_add_browser_xss_inert',))

        def goal_create_update():
            self.goto(p, 'goals.html')
            expect(p.locator('#save-annual-goal')).to_be_enabled()
            year = int(p.locator('#goal-year').input_value())
            month = int(p.locator('#goal-month').input_value())
            self.state.update(goal_year=year, goal_month=month)
            for field, button, values, query in [
                ('annual-goal-input', 'save-annual-goal', (12, 24), f'?year={year}'),
                ('monthly-goal-input', 'save-monthly-goal', (3, 5), f'?year={year}&month={month}'),
            ]:
                for i, value in enumerate(values):
                    p.locator('#' + field).fill(str(value))
                    method = 'POST' if i == 0 else 'PATCH'
                    with p.expect_response(lambda r: '/api/goal/goal/' in r.url and r.request.method == method) as pending:
                        p.locator('#' + button).click()
                    assert pending.value.status == (201 if i == 0 else 200), 'Goal save HTTP mismatch'
                    expect(p.locator('#goal-status')).to_contain_text('목표가 저장되었습니다')
                    data = self.status(self.api_call(p, '/api/goal/progress/' + query), 200)
                    assert data['goal_books'] == value and data['read_books'] == 1
            p.reload(wait_until='networkidle')
            expect(p.locator('#annual-goal-input')).to_have_value('24')
            expect(p.locator('#monthly-goal-input')).to_have_value('5')
        self.check('yearly_monthly_target_create_update_readback', goal_create_update, ('review_create_browser_readback',))

        def charts():
            assert 'chart' in self.assets, 'Real Chart.js CDN bytes unavailable; no chart mock permitted'
            chart = p.evaluate('''() => ({version:Chart.version,
                annual:Chart.getChart('goalChart').data.datasets[0].data,
                monthly:Chart.getChart('monthlyChart').data.datasets[0].data,
                annualWidth:Chart.getChart('goalChart').width,monthlyWidth:Chart.getChart('monthlyChart').width})''')
            assert chart['version'] == '4.5.1' and chart['annual'] == [24, 1]
            script = p.locator('script[src*="chart.js@"]')
            assert script.get_attribute('integrity') == CHART_SRI
            assert script.get_attribute('crossorigin') == 'anonymous'
            chart['integrity'] = script.get_attribute('integrity')
            assert len(chart['monthly']) == 12 and sum(chart['monthly']) == 1
            assert chart['monthly'][self.state['goal_month'] - 1] == 1
            assert chart['annualWidth'] > 0 and chart['monthlyWidth'] > 0
            self.report['chart_assertions'] = chart
            self.screenshots(p, 'goals')
            self.state['goal_layout'] = p.evaluate('''() => {
                const rect = selector => {const r=document.querySelector(selector).getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom};};
                return {title:rect('.goal-title'),basis:rect('#statistics-basis')};
            }''')
            self.goto(p, 'main.html')
            p.wait_for_function("typeof Chart !== 'undefined' && Chart.getChart('goalChart') && Chart.getChart('monthlyChart')")
            assert p.evaluate("Chart.getChart('goalChart').data.datasets[0].data") == [24, 1]
            self.screenshots(p, 'main')
        self.check('real_chartjs_goal_and_main_render', charts, ('yearly_monthly_target_create_update_readback',))

        def goal_layout():
            self.goto(p, 'goals.html')
            expect(p.locator('#save-annual-goal')).to_be_enabled()
            boxes = p.evaluate('''() => {
                const rect = selector => {const r=document.querySelector(selector).getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom};};
                return {title:rect('.goal-title'),basis:rect('#statistics-basis')};
            }''')
            title, basis = boxes['title'], boxes['basis']
            overlap = title['left'] < basis['right'] and title['right'] > basis['left'] and title['top'] < basis['bottom'] and title['bottom'] > basis['top']
            self.report['goal_layout'] = boxes
            if overlap:
                self.report['source_findings'].append({'name': 'goal_heading_explanation_no_overlap', 'severity': 'medium',
                    'source': 'frontend/screen/goals.html:23-29',
                    'actual': '데스크톱에서 absolute .goal-title top:100px 제목이 통계 기준 설명과 겹칩니다.',
                    'screenshot': str(self.output / 'screenshots/goals-desktop.png')})
            assert not overlap, 'Goal heading overlaps statistics-basis explanation (measured real DOM rectangles)'
        self.check('goal_heading_explanation_no_overlap', goal_layout, ('real_chartjs_goal_and_main_render',))

        def profile():
            self.goto(p, 'mypage_edit.html')
            expect(p.locator('#save-profile')).to_be_enabled()
            p.locator('#next-profile').click()
            p.locator('#next-profile').click()
            expect(p.locator('#profile-image')).to_have_attribute('src', self.front + '/assets/images/profile_image2.svg')
            p.locator('#user-nickname').fill('변경된스모크닉네임')
            self.ui_response(p, '/api/user/update_profile/', 'PUT', lambda: p.locator('#save-profile').click(), 200)
            p.wait_for_url('**/mypage.html')
            expect(p.locator('#username-display')).to_have_text('변경된스모크닉네임')
            expect(p.locator('.profile-picture img')).to_have_attribute('src', '../assets/images/profile_image2.svg')
            data = self.status(self.api_call(p, '/api/user/me/'), 200)
            assert data['nickname'] == '변경된스모크닉네임' and data['profile_image'] == 'profile_images/profile_image2.svg'
            p.reload(wait_until='networkidle')
            expect(p.locator('.profile-picture img')).to_have_attribute('src', '../assets/images/profile_image2.svg')
            self.screenshots(p, 'profile')
            self.goto(p, 'mypage_edit.html')
            expect(p.locator('#profile-image')).to_have_attribute('src', self.front + '/assets/images/profile_image2.svg')
            self.screenshots(p, 'profile-edit')
        self.check('profile_selected_image_nickname_persistence', profile, ('email_login_browser',))

        def expired_refresh():
            from rest_framework_simplejwt.tokens import AccessToken
            from django.contrib.auth import get_user_model
            # Playwright owns an async loop on the main thread. Keep ORM reads
            # in a worker instead of bypassing Django's async safety guard.
            with ThreadPoolExecutor(max_workers=1) as executor:
                user = executor.submit(lambda: get_user_model().objects.get(username='smoke-owner')).result()
            expired = AccessToken.for_user(user)
            expired.set_exp(lifetime=timedelta(seconds=-10))
            secret = str(expired)
            SECRETS.append(secret)
            p.evaluate("token => localStorage.setItem('token', token)", secret)
            start = len(self.report['api_statuses'])
            self.goto(p, 'library.html')
            expect(p.locator('.book-card')).to_have_count(1)
            events = self.report['api_statuses'][start:]
            assert any(e['path'] == '/api/review/library/' and e['status'] == 401 for e in events)
            assert any(e['path'] == '/api/auth/token/refresh/' and e['status'] == 200 for e in events)
            assert any(e['path'] == '/api/review/library/' and e['status'] == 200 for e in events)
            assert p.evaluate("token => localStorage.getItem('token') !== token", secret)
        self.check('expired_access_real_jwt_refresh_retry', expired_refresh, ('review_create_browser_readback',))

        def review_delete():
            rid = self.state['review_id']
            self.goto(p, f'review-detail.html?id={rid}')
            expect(p.locator('#delete-button')).to_be_visible()
            self.ui_response(p, f'/api/review/{rid}/', 'DELETE', lambda: p.locator('#delete-button').click(), 200)
            p.wait_for_url('**/library.html')
            self.status(self.api_call(p, f'/api/review/{rid}/', auth=False), 404)
            assert self.status(self.api_call(p, '/api/review/library/'), 200) == []
            expect(p.locator('#book-grid')).to_contain_text('아직 작성한 리뷰가 없습니다')
        self.check('review_delete_browser_readback', review_delete, ('review_create_browser_readback',))

        def password_change():
            old_refresh = p.evaluate("localStorage.getItem('refresh_token')")
            SECRETS.append(old_refresh)
            self.goto(p, 'mypage_edit.html')
            expect(p.locator('#save-profile')).to_be_enabled()
            p.locator('#current-password').fill(password)
            p.locator('#user-password').fill(changed)
            self.ui_response(p, '/api/user/update_profile/', 'PUT', lambda: p.locator('#save-profile').click(), 200)
            p.wait_for_url('**/index.html')
            assert not p.evaluate("localStorage.getItem('token') || localStorage.getItem('refresh_token')")
            self.status(self.api_call(p, '/api/auth/token/refresh/', 'POST', {'refresh': old_refresh}, False), 401)
            self.status(self.api_call(p, '/api/user/login/', 'POST', {'email': email, 'password': password}, False), 401)
            self.login(p, email, changed)
        self.check('password_change_new_login_refresh_revoked', password_change, ('email_login_browser',))

        def reset_request():
            from django.core import mail
            old_refresh = p.evaluate("localStorage.getItem('refresh_token')")
            SECRETS.append(old_refresh)
            self.state['before_reset_refresh'] = old_refresh
            before = len(getattr(mail, 'outbox', []))
            self.goto(p, 'find-account.html')
            self.screenshots(p, 'account-recovery')
            p.locator('#find-pw-email').fill(email)
            self.ui_response(p, '/api/user/reset-password/', 'POST', lambda: p.locator('#find-pw-btn').click(), 200)
            expect(p.locator('#pw-result')).to_contain_text('등록된 이메일이면')
            assert len(mail.outbox) == before + 1, 'locmem reset mail must be delivered once'
            message = mail.outbox[-1]
            assert message.to == [email]
            match = re.search(r'http://[^\s]+', message.body)
            assert match, 'locmem mail must contain a reset link'
            link = match.group()
            SECRETS.append(link)
            parsed = urllib.parse.urlsplit(link)
            assert parsed.scheme + '://' + parsed.netloc == self.front
            assert parsed.path == '/screen/find-account.html'
            query = urllib.parse.parse_qs(parsed.query)
            SECRETS.extend([query['uid'][0], query['token'][0]])
            self.state['reset_link'] = link
            self.report['locmem_reset_mail_count'] = len(mail.outbox) - before
        self.check('reset_request_browser_locmem_mail', reset_request, ('password_change_new_login_refresh_revoked',))

        def reset_confirm():
            p.goto(self.state['reset_link'], wait_until='networkidle')
            assert '?' not in p.url, 'Reset UI must remove credential query from address bar'
            p.locator('#reset-new-password').fill(reset)
            p.locator('#reset-confirm-password').fill(reset)
            self.ui_response(p, '/api/user/reset-password/', 'POST', lambda: p.locator('#reset-password-form button').click(), 200)
            expect(p.locator('#reset-result')).to_contain_text('비밀번호가 변경되었습니다')
            assert not p.evaluate("localStorage.getItem('token') || localStorage.getItem('refresh_token')")
            self.status(self.api_call(p, '/api/auth/token/refresh/', 'POST', {'refresh': self.state['before_reset_refresh']}, False), 401)
            self.status(self.api_call(p, '/api/user/login/', 'POST', {'email': email, 'password': changed}, False), 401)
            self.screenshots(p, 'reset-confirmed')
            self.login(p, email, reset)
        self.check('reset_mail_link_browser_confirm_new_login', reset_confirm, ('reset_request_browser_locmem_mail',))

        def reset_reuse():
            p.goto(self.state['reset_link'], wait_until='networkidle')
            p.locator('#reset-new-password').fill(changed)
            p.locator('#reset-confirm-password').fill(changed)
            self.ui_response(p, '/api/user/reset-password/', 'POST', lambda: p.locator('#reset-password-form button').click(), 400)
            expect(p.locator('#reset-result')).to_contain_text('링크가 올바르지 않거나 만료되었습니다')
            # Previous successful browser login remains intact. An unnecessary
            # sixth login would hit the real 5/min identity throttle.
            self.status(self.api_call(p, '/api/user/me/'), 200)
        self.check('reset_one_time_reuse_denied_browser', reset_reuse, ('reset_mail_link_browser_confirm_new_login',))

        def logout():
            refresh = p.evaluate("localStorage.getItem('refresh_token')")
            SECRETS.append(refresh)
            self.goto(p, 'library.html')
            self.ui_response(p, '/api/user/logout/', 'POST', lambda: p.locator('#logout-btn').click(), 200)
            p.wait_for_url('**/index.html')
            assert not p.evaluate("localStorage.getItem('token') || localStorage.getItem('refresh_token') || localStorage.getItem('username')")
            self.status(self.api_call(p, '/api/auth/token/refresh/', 'POST', {'refresh': refresh}, False), 401)
            from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
            with ThreadPoolExecutor(max_workers=1) as executor:
                assert executor.submit(lambda: BlacklistedToken.objects.filter(token__user__username='smoke-owner').exists()).result()
        self.check('logout_browser_refresh_blacklist', logout, ('email_login_browser',))
        def mobile_layout():
            overflow = [s for s in self.report['screenshots'] if s['viewport'] == 'mobile' and not s['name'].startswith('failure-') and s['layout']['document'] > s['layout']['viewport'] + 1]
            self.report['mobile_overflow'] = [{'name': s['name'], 'width': s['layout']['document'], 'viewport': s['layout']['viewport'], 'screenshot': s['path']} for s in overflow]
            if overflow:
                self.report['source_findings'].append({'name': 'mobile_horizontal_overflow', 'severity': 'medium',
                    'source': 'frontend/styles/index.css:10-18; frontend/styles/review-detail.css:212-235,258-268,299-303; frontend/styles/find-account.css',
                    'actual': '기존 CSS에서 390px 모바일 가로 스크롤과 리뷰/댓글 컨트롤의 화면 밖 넘침이 발생합니다.',
                    'affected': self.report['mobile_overflow']})
            assert not overflow, '390px mobile horizontal overflow: ' + ', '.join(s['name'] + '=' + str(s['layout']['document']) + 'px' for s in overflow)
        self.check('mobile_horizontal_overflow', mobile_layout)
        self.check('no_uncaught_javascript_errors', lambda: self.assert_no_js())

    def screenshots_before_signup(self, page):
        self.goto(page, 'index.html')
        self.screenshots(page, 'login')
        self.goto(page, 'register.html')
        self.screenshots(page, 'register')

    def assert_no_js(self):
        assert not self.report['js_errors'], 'Uncaught JavaScript errors captured; see redacted results'

    def shutdown(self):
        for context in self.contexts:
            with contextlib.suppress(Exception):
                context.close()
        for server in reversed(self.servers):
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join(timeout=5)
        closed = []
        for server in self.servers:
            with socket.socket() as probe:
                probe.settimeout(1)
                closed.append(probe.connect_ex(server.server_address) != 0)
        if hasattr(self, 'original_get'):
            import requests
            requests.get = self.original_get
        self.report['own_servers_shutdown'] = all(closed) and all(not thread.is_alive() for thread in self.threads)

    def finish(self, before_db, css_before):
        original_db = ROOT / 'backend/db.sqlite3'
        after_db = digest(original_db) if original_db.exists() else None
        css_after = {str(path.relative_to(ROOT)): digest(path) for path in (ROOT / 'frontend').rglob('*.css') if 'node_modules' not in path.parts}
        # Absence is preserved too: a clean clone must not create an original DB.
        self.report['original_db_sha256'] = {'before': before_db, 'after': after_db,
            'present_before': before_db is not None, 'present_after': after_db is not None,
            'unchanged': before_db == after_db}
        self.report['original_css_unchanged'] = css_before == css_after
        self.report['original_css_sha256'] = css_after
        for name, success in [('original_db_sha256_unchanged', before_db == after_db),
                              ('original_css_unchanged', css_before == css_after),
                              ('own_servers_shutdown', self.report.get('own_servers_shutdown', False))]:
            self.report['tests'].append({'name': name, 'status': 'pass' if success else 'fail'})
        tests = self.report['tests']
        counts = {status: sum(item['status'] == status for item in tests) for status in ('pass', 'fail', 'blocked')}
        self.report['counts'] = counts
        self.report['total_tests'] = len(tests)
        self.report['screenshot_count'] = len(self.report['screenshots'])
        self.report['api_response_count'] = len(self.report['api_statuses'])
        self.report['complete'] = counts['fail'] == counts['blocked'] == 0
        # State with credentials remains in memory only, never in report.
        (self.output / 'results.json').write_text(json.dumps(self.report, ensure_ascii=False, indent=2))
        lines = ['# Chromium 실제 브라우저 스모크 결과', '',
                 f'- 실제 실행: Django {self.report.get("django_version", "unknown")}, Chromium {self.report.get("chromium_version", "unknown")}',
                 f'- PASS {counts["pass"]} / FAIL {counts["fail"]} / BLOCKED {counts["blocked"]} (총 {len(tests)})',
                 f'- API 응답 {self.report["api_response_count"]}개, 스크린샷 {self.report["screenshot_count"]}개',
                 f'- 원본 SQLite SHA256/부재 보존: {before_db == after_db} (실행 전 존재: {before_db is not None}); 원본 CSS 보존: {css_before == css_after}',
                 f'- 자체 서버 종료: {self.report.get("own_servers_shutdown", False)}',
                 '- 판정: ' + ('테스트 범위 통과 (아래 미검증 한계 있음)' if self.report['complete'] else '미완료: 실제 실패/선행 차단이 남음'), '',
                 '| 흐름 | 결과 |', '|---|---|']
        lines.extend(f'| {FLOW_LABELS.get(test["name"], test["name"])} (`{test["name"]}`) | {test["status"]} |' for test in tests)
        for test in tests:
            if test['status'] == 'fail':
                lines.extend(['', '## 실패: ' + test['name'], '```text', test.get('error', ''), '```'])
        lines.extend(['', '## 소스 결함 (다른 담당 소스는 수정하지 않음)'])
        for finding in self.report['source_findings']:
            lines.extend(['- ' + finding['name'] + ' (' + finding['severity'] + '): ' + finding['actual'],
                          '  - 위치: `' + finding['source'] + '`'])
        lines.extend(['', '## 미검증 / 제한'] + ['- ' + limit for limit in self.report['limits']])
        lines.extend(['', '## 증거', f'- JSON: `{self.output / "results.json"}`', f'- 로그: `{self.output / "smoke.log"}`',
                      f'- 스크린샷: `{self.output / "screenshots"}`', '', '## 업그레이드 환경 재실행',
                      '`<upgraded-venv>/bin/python -B ' + str(ROOT / 'tests/browser_smoke.py') + ' --output-root ' + str(self.output.parent) + '`',
                      'Playwright가 설치된 새 Python 환경에서 실행. 원본 DB 마이그레이션 없이 매 실행 UUID 격리 DB를 생성합니다.'])
        (self.output / 'report.ko.md').write_text('\n'.join(lines) + '\n')
        self.log(f'SUMMARY pass={counts["pass"]} fail={counts["fail"]} blocked={counts["blocked"]} screenshots={len(self.report["screenshots"])} api_responses={len(self.report["api_statuses"])}')
        self.log('RESULTS ' + str(self.output / 'results.json'))
        (self.output.parent / 'latest-run.json').write_text(json.dumps({'results': str(self.output / 'results.json'),
            'log': str(self.output / 'smoke.log'), 'report': str(self.output / 'report.ko.md'),
            'screenshots': str(self.output / 'screenshots'), 'counts': counts, 'complete': self.report['complete']}, indent=2))
        return 0 if self.report['complete'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--obtain-cdn', action='store_true', help='Read-only obtain exact pinned Chart.js and Pretendard CSS if not cached')
    args = parser.parse_args()
    base = args.output_root.resolve()
    # Evidence must stay outside repository/backend and original SQLite.
    if base == ROOT or ROOT in base.parents:
        parser.error('Output directory must be outside the repository')
    output = base / ('run-' + uuid.uuid4().hex)
    (output / 'screenshots').mkdir(parents=True, exist_ok=False)
    original_db = ROOT / 'backend/db.sqlite3'
    before_db = digest(original_db) if original_db.exists() else None
    css_before = {str(path.relative_to(ROOT)): digest(path) for path in (ROOT / 'frontend').rglob('*.css') if 'node_modules' not in path.parts}
    assets, cdn = obtain_assets(base, args.obtain_cdn)
    harness = Harness(output, assets, cdn)
    try:
        with loopback_only():
            harness.start_servers()
            from playwright.sync_api import sync_playwright
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, args=['--disable-background-networking', '--disable-component-update', '--disable-domain-reliability', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost'])
                harness.report['chromium_version'] = browser.version
                try:
                    harness.run_flows(browser)
                finally:
                    harness.shutdown()
                    browser.close()
    except Exception as exc:
        harness.report['tests'].append({'name': 'harness_setup_or_execution', 'status': 'fail', 'error': redact(exc), 'exception': type(exc).__name__})
        harness.log('FAIL harness_setup_or_execution: ' + redact(exc))
    finally:
        if not harness.report.get('own_servers_shutdown'):
            harness.shutdown()
    return harness.finish(before_db, css_before)


if __name__ == '__main__':
    raise SystemExit(main())

"""Real Django/JWT route contract, isolated test DB and synthetic credentials only.
Run: .venv-dev/bin/python -B frontend/tests/verify_backend_contract.py
Never loads/writes the original database or invokes book providers.
"""
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ.update({
    'DJANGO_SETTINGS_MODULE': 'dadokdadok.settings',
    'DJANGO_DEBUG': '1',
    'DJANGO_ALLOWED_HOSTS': 'testserver,localhost,127.0.0.1',
    'DJANGO_SECRET_KEY': 'frontend-isolated-regression-signing-key-not-production-12345',
    'JWT_SIGNING_KEY': 'frontend-isolated-regression-signing-key-not-production-12345',
    'NAVER_CLIENT_ID': '', 'NAVER_CLIENT_SECRET': '',
    'DJANGO_DB_PATH': str(Path(os.environ.get('TMPDIR', str(ROOT))) / 'frontend-unused-base.sqlite3'),
    'EMAIL_BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
})
import django

django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.runner import DiscoverRunner
from django.urls import resolve
from rest_framework.test import APIClient

from django.db import connections
connections.settings['default']['TEST']['NAME'] = ':memory:'
assert Path(settings.DATABASES['default']['NAME']) != ROOT / 'backend/db.sqlite3'


class FrontendAuthContract(TestCase):
    def test_frontend_refresh_path_resolves_and_login_refresh_logout_work(self):
        source = (ROOT / 'frontend/scripts/api.js').read_text()
        match = re.search(r"fetch\(endpoint\('([^']*refresh/)'\)", source)
        self.assertIsNotNone(match, '공통 helper에 명시적 refresh 경로가 필요합니다.')
        assert match is not None
        refresh_path = match.group(1)
        client = APIClient()
        self.assertEqual(client.post(refresh_path, {}, format='json').status_code, 400, '프론트 refresh 경로가 실제 Django endpoint여야 합니다.')
        self.assertEqual(resolve(refresh_path).url_name, 'token_refresh')
        user = get_user_model().objects.create_user(
            username='frontend-regression-reader', email='frontend-regression@example.test',
            nickname='프론트 회귀 독자', password='isolated-fixture-password-527!',
        )
        client = APIClient()
        login = client.post('/api/user/login/', {
            'username': user.username, 'password': 'isolated-fixture-password-527!',
        }, format='json')
        self.assertEqual(login.status_code, 200)
        refreshed = client.post(refresh_path, {'refresh': login.data['refresh_token']}, format='json')
        self.assertEqual(refreshed.status_code, 200)
        self.assertIn('access', refreshed.data)
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + refreshed.data['access'])
        self.assertEqual(client.get('/api/user/me/').status_code, 200)
        refresh_token = refreshed.data.get('refresh', login.data['refresh_token'])
        self.assertEqual(client.post('/api/user/logout/', {'refresh_token': refresh_token}, format='json').status_code, 200)
        client.credentials()
        self.assertEqual(client.post(refresh_path, {'refresh': refresh_token}, format='json').status_code, 401)


if __name__ == '__main__':
    runner = DiscoverRunner(verbosity=2, interactive=False)
    sys.exit(bool(runner.run_tests(['__main__.FrontendAuthContract'])))

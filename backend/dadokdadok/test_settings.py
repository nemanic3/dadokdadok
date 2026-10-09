"""Configuration regressions; subprocesses never touch a database."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


class EnvironmentSettingsTests(unittest.TestCase):
    def load_config(self, expect_failure=False, **overrides):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(('DJANGO_', 'NAVER_', 'JWT_', 'EMAIL_', 'DATABASE_'))}
        env.update(DJANGO_DEBUG='0', DJANGO_SECRET_KEY='isolated-config-regression-key-not-production',
                   JWT_SIGNING_KEY='isolated-config-regression-key-not-production',
                   DJANGO_ALLOWED_HOSTS='example.test', DJANGO_CORS_ALLOWED_ORIGINS='https://example.test',
                   NAVER_CLIENT_ID='', NAVER_CLIENT_SECRET='',
                   EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend')
        env.update(overrides)
        env = {key: value for key, value in env.items() if value is not None}
        code = ('import json; from dadokdadok import settings as s; '
                'print(json.dumps({"debug":s.DEBUG,"hosts":s.ALLOWED_HOSTS,'
                '"cors_all":s.CORS_ALLOW_ALL_ORIGINS,"db":str(s.DATABASES["default"]["NAME"]),'
                '"ssl":getattr(s,"SECURE_SSL_REDIRECT",False),'
                '"cookies":getattr(s,"SESSION_COOKIE_SECURE",False),'
                '"email_backend":s.EMAIL_BACKEND,'
                '"secret":s.SECRET_KEY,"naver":s.NAVER_CLIENT_ID}))')
        result = subprocess.run([sys.executable, '-B', '-c', code], env=env,
                                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        if expect_failure:
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('EMAIL_BACKEND', result.stderr)
            return {}
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_production_requires_explicit_email_backend(self):
        for backend in [None, '', '   ']:
            with self.subTest(backend=backend):
                self.load_config(expect_failure=True, EMAIL_BACKEND=backend)

    def test_production_rejects_non_delivery_email_backends(self):
        for backend in ['django.core.mail.backends.console.EmailBackend',
                        'django.core.mail.backends.filebased.EmailBackend',
                        'django.core.mail.backends.dummy.EmailBackend',
                        'django.core.mail.backends.locmem.EmailBackend',
                        'django.core.mail.backends.base.BaseEmailBackend',
                        'unapproved.mail.EmailBackend']:
            with self.subTest(backend=backend):
                self.load_config(expect_failure=True, EMAIL_BACKEND=backend)

    def test_development_console_default_and_test_locmem_are_preserved(self):
        config = self.load_config(DJANGO_DEBUG='1', EMAIL_BACKEND=None)
        self.assertEqual(config['email_backend'], 'django.core.mail.backends.console.EmailBackend')
        config = self.load_config(DJANGO_DEBUG='1', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
        self.assertEqual(config['email_backend'], 'django.core.mail.backends.locmem.EmailBackend')

    def test_production_explicit_smtp_backend_loads_without_sending_mail(self):
        config = self.load_config()
        self.assertEqual(config['email_backend'], 'django.core.mail.backends.smtp.EmailBackend')

    def test_production_explicit_resend_backend_loads_without_sending_mail(self):
        config = self.load_config(EMAIL_BACKEND='user.email_backend.ResendEmailBackend')
        self.assertEqual(config['email_backend'], 'user.email_backend.ResendEmailBackend')

    def test_production_environment_disables_debug_and_wildcards(self):
        config = self.load_config()
        self.assertFalse(config['debug'])
        self.assertEqual(config['hosts'], ['example.test'])
        self.assertFalse(config['cors_all'])
        self.assertTrue(config['ssl'])
        self.assertTrue(config['cookies'])

    def test_explicit_database_and_credentials_override_local_values(self):
        config = self.load_config(DJANGO_DB_PATH='/nonexistent/isolated.sqlite3', NAVER_CLIENT_ID='test-id')
        self.assertEqual(config['db'], '/nonexistent/isolated.sqlite3')
        self.assertEqual(config['naver'], 'test-id')
        self.assertEqual(config['secret'], 'isolated-config-regression-key-not-production')

    def test_production_refuses_missing_explicit_keys(self):
        env = dict(os.environ, DJANGO_DEBUG='0', DJANGO_ALLOWED_HOSTS='example.test')
        env.pop('DJANGO_SECRET_KEY', None)
        env.pop('JWT_SIGNING_KEY', None)
        result = subprocess.run([sys.executable, '-B', '-c', 'import dadokdadok.settings'],
                                cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_SECRET_KEY must be explicitly configured', result.stderr)

    def test_source_has_no_literal_real_credentials(self):
        import ast
        tree = ast.parse((Path(__file__).parent / 'settings.py').read_text())
        for node in tree.body:
            if isinstance(node, ast.Assign):
                names = [target.id for target in node.targets if isinstance(target, ast.Name)]
                if set(names) & {'SECRET_KEY', 'NAVER_CLIENT_ID', 'NAVER_CLIENT_SECRET'}:
                    self.assertNotIsInstance(node.value, ast.Constant)

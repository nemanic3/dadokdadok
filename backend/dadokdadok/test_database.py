from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from .database import postgres_database


class PostgreSQLSettingsTests(SimpleTestCase):
    def test_pooler_compatible_config_and_escaped_password(self):
        config = postgres_database('postgresql://reader:p%40ss%3Aword@db.example/books?sslmode=require&channel_binding=require', True)
        self.assertEqual(config['PASSWORD'], 'p@ss:word')
        self.assertEqual(config['NAME'], 'books')
        self.assertEqual(config['OPTIONS']['sslmode'], 'require')
        self.assertEqual(config['CONN_MAX_AGE'], 0)
        self.assertTrue(config['DISABLE_SERVER_SIDE_CURSORS'])

    def test_production_defaults_to_tls(self):
        self.assertEqual(postgres_database('postgres://u:p@db.example/books', True)['OPTIONS']['sslmode'], 'require')

    def test_rejects_invalid_or_insecure_urls_without_exposing_url(self):
        for url in ('sqlite:///private', 'postgres://u:private@host:invalid/books',
                    'postgres://u:private@host/books?sslmode=disable', 'postgres://u:private@host/'):
            with self.subTest(url=url), self.assertRaises(ImproperlyConfigured) as error:
                postgres_database(url, True)
            self.assertNotIn('private', str(error.exception))

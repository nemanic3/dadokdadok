from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from .proxy import PagesProxyMiddleware


@override_settings(DEBUG=False, ORIGIN_PROXY_SECRET='synthetic-secret')
class PagesProxyTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = PagesProxyMiddleware(lambda r: JsonResponse({'secure': r.is_secure(), 'ip': r.META['REMOTE_ADDR']}))

    def test_direct_access_rejected(self):
        self.assertEqual(self.middleware(self.factory.get('/api/')).status_code, 403)

    def test_authenticated_metadata_sets_https_and_real_ip(self):
        request = self.factory.get('/api/', HTTP_X_DADOK_PROXY_SECRET='synthetic-secret',
                                   HTTP_X_DADOK_CLIENT_IP='192.0.2.1', HTTP_X_FORWARDED_FOR='attacker')
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(request.is_secure())
        self.assertEqual(request.META['REMOTE_ADDR'], '192.0.2.1')
        self.assertNotIn('HTTP_X_FORWARDED_FOR', request.META)
        self.assertNotIn('HTTP_X_DADOK_PROXY_SECRET', request.META)

    def test_invalid_client_ip_rejected(self):
        request = self.factory.get('/api/', HTTP_X_DADOK_PROXY_SECRET='synthetic-secret', HTTP_X_DADOK_CLIENT_IP='attacker')
        self.assertEqual(self.middleware(request).status_code, 400)

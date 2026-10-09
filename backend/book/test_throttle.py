from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase


class PublicBookThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_default_settings_publish_the_shared_book_scope(self):
        from book.throttles import BookThrottle
        rates = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
        self.assertIn(BookThrottle.scope, rates)
        self.assertEqual(BookThrottle().rate, rates[BookThrottle.scope])

    def test_legacy_books_rate_is_accepted_but_explicit_book_takes_precedence(self):
        from book.throttles import BookThrottle
        for rates, expected in [({'books': '1/min'}, '1/min'),
                                ({'book': '2/min', 'books': '1/min'}, '2/min')]:
            with self.subTest(rates=rates), override_settings(REST_FRAMEWORK={
                    **settings.REST_FRAMEWORK, 'DEFAULT_THROTTLE_RATES': rates}):
                self.assertEqual(BookThrottle().rate, expected)

    def test_search_isbn_and_recommendations_share_bounded_ip_quota(self):
        configuration = {**settings.REST_FRAMEWORK, 'DEFAULT_THROTTLE_RATES': {
            **settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {}), 'book': '2/min'}}
        with override_settings(REST_FRAMEWORK=configuration), \
                patch('book.views.search_books_from_naver', return_value=[]), \
                patch('book.views.get_book_by_isbn_from_naver', return_value=None), \
                patch('recommendation.services.search_books_from_naver', return_value=[]) as upstream:
            self.assertEqual(self.client.get('/api/book/search/?query=fixture').status_code, 200)
            self.assertEqual(self.client.get('/api/book/isbn/9780000000019/').status_code, 404)
            response = self.client.get('/api/recommendation/naver/?query=fixture', HTTP_X_FORWARDED_FOR='192.0.2.100')
            self.assertEqual(response.status_code, 429)
            self.assertIn('Retry-After', response)
            upstream.assert_not_called()

from unittest.mock import Mock, patch
from django.test import SimpleTestCase, override_settings
from .services import search_books_from_naver, get_book_by_isbn_from_naver, NaverAPIError


@override_settings(BOOK_SEARCH_PROVIDER='kakao', KAKAO_REST_API_KEY='synthetic-kakao-key')
class KakaoBookTests(SimpleTestCase):
    def document(self, n):
        return {'title': f'책 {n}', 'authors': ['저자', '공저자'], 'publisher': '출판사',
                'isbn': '0132350882 9780132350884', 'datetime': '2008-08-01T00:00:00.000+09:00',
                'thumbnail': 'https://example.com/cover.jpg', 'url': 'https://example.com/book'}

    def response(self, docs, end=False):
        return Mock(status_code=200, json=Mock(return_value={'documents': docs,
                    'meta': {'total_count': 123, 'is_end': end}}))

    @patch('book.services.requests.get')
    def test_offset_crosses_provider_page_without_dropping_or_repeating_books(self, get):
        get.side_effect = [self.response([self.document(i) for i in range(50)]),
                           self.response([self.document(i) for i in range(50, 100)])]
        result = search_books_from_naver('책', display=20, start=41)
        self.assertEqual([item['title'] for item in result], [f'책 {i}' for i in range(40, 60)])
        self.assertEqual(result.total, 123)
        self.assertEqual(result[0]['author'], '저자^공저자')
        self.assertEqual(result[0]['pubdate'], '20080801')
        self.assertEqual(result[0]['image'], 'https://example.com/cover.jpg')
        self.assertEqual([call.kwargs['params']['page'] for call in get.call_args_list], [1, 2])
        self.assertEqual(get.call_args.kwargs['headers'], {'Authorization': 'KakaoAK synthetic-kakao-key'})
        self.assertFalse(get.call_args.kwargs['allow_redirects'])

    @patch('book.services.requests.get')
    def test_isbn_search_is_restricted_and_preserves_requested_identity(self, get):
        get.return_value = self.response([self.document(0)], end=True)
        self.assertEqual(get_book_by_isbn_from_naver('9780132350884')['isbn'], '9780132350884')
        self.assertEqual(get.call_args.kwargs['params']['target'], 'isbn')

    @patch('book.services.requests.get')
    def test_redirect_and_malformed_payload_fail_without_leaking_credentials(self, get):
        for response in [Mock(status_code=302), Mock(status_code=200, json=Mock(return_value={'documents': [{}]}))]:
            get.return_value = response
            with self.assertRaises(NaverAPIError) as failure:
                search_books_from_naver('책')
            self.assertNotIn('synthetic-kakao-key', str(failure.exception))

    @patch('book.services.requests.get')
    def test_empty_results_stop_after_one_request(self, get):
        get.return_value = self.response([], end=True)
        self.assertEqual(search_books_from_naver('없음', display=100), [])
        self.assertEqual(get.call_count, 1)

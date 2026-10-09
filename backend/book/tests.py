from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


@override_settings(NAVER_CLIENT_ID='fixture-client-id', NAVER_CLIENT_SECRET='fixture-client-secret')
class BookSearchTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('book.services.requests.get')
    def test_empty_search_is_a_successful_empty_array(self, get):
        get.return_value = Mock(json=Mock(return_value={'items': [], 'total': 0}))
        result = self.client.get('/api/book/search/', {'query': 'empty-fixture'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), [])

    @patch('book.services.requests.get')
    def test_timeout_has_a_distinct_safe_error_and_bounded_request(self, get):
        import requests
        get.side_effect = requests.Timeout('private upstream diagnostic')
        result = self.client.get('/api/book/search/', {'query': 'fixture'})
        self.assertEqual(result.status_code, 504)
        self.assertNotIn('private upstream', str(result.json()))
        self.assertEqual(get.call_args.kwargs['timeout'], (3.05, 10))

    @patch('book.services.requests.get')
    def test_empty_isbn_is_not_found_instead_of_server_error(self, get):
        get.return_value = Mock(json=Mock(return_value={'items': []}))
        self.assertEqual(self.client.get('/api/book/isbn/9780132350884/').status_code, 404)

    @patch('book.services.requests.get')
    def test_isbn_search_cannot_return_a_different_book(self, get):
        get.return_value = Mock(json=Mock(return_value={'items': [{'isbn': '9780201633610', 'title': 'wrong'}]}))
        result = self.client.get('/api/book/isbn/9780132350884/')
        self.assertEqual(result.status_code, 404)

    @patch('book.services.requests.get')
    def test_invalid_isbn_is_rejected_without_external_request(self, get):
        for token in ['9780132350885', '123', '9780132350884-extra', '9780132350884%20']:
            with self.subTest(token=token):
                self.assertEqual(self.client.get(f'/api/book/isbn/{token}/').status_code, 400)
        get.assert_not_called()

    @patch('book.services.requests.get')
    def test_q_alias_and_bounded_pagination_reach_upstream(self, get):
        get.return_value = Mock(json=Mock(return_value={'items': [], 'total': 42}))
        result = self.client.get('/api/book/search/', {'q': 'alias-fixture', 'display': 20, 'start': 21})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(get.call_args.kwargs['params'], {'query': 'alias-fixture', 'display': 20, 'start': 21})
        self.assertEqual(result['X-Total-Count'], '42')

    @patch('book.services.requests.get')
    def test_invalid_search_pagination_is_400_without_external_calls(self, get):
        for params in [{'display': 'abc'}, {'display': 0}, {'display': 101}, {'start': 1001}, {'start': '-1'}]:
            self.assertEqual(self.client.get('/api/book/search/', {'query': 'fixture', **params}).status_code, 400)
        self.assertEqual(get.call_count, 0)


class RecentDistinctBooksTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from book.models import Book
        from review.models import Review
        self.client = APIClient()
        self.books = [Book.objects.create(title=f'book {n}', isbn=f'fixture-{n}') for n in range(12)]
        users = [get_user_model().objects.create_user(username=f'recent-{n}', nickname=f'recent-{n}') for n in range(12)]
        for book in self.books:
            Review.objects.create(book=book, user=users[0], rating=4, content='review')
        for user in users[1:]:
            Review.objects.create(book=self.books[0], user=user, rating=5, content='newest repeated book')
        Review.objects.all().update(created_at=timezone.now())

    def test_recent_is_stable_review_order_with_distinct_isbn_before_limit(self):
        response = self.client.get('/api/book/recent-reviews/')
        self.assertEqual(response.status_code, 200)
        expected = [self.books[0], *reversed(self.books[1:])][:10]
        self.assertEqual([book['isbn'] for book in response.json()], [book.isbn for book in expected])
        self.assertEqual(response.json(), self.client.get('/api/book/recent-reviews/').json())

    def test_recent_deduplicates_newest_repeated_book_before_slicing(self):
        from datetime import timedelta
        from django.utils import timezone
        from review.models import Review
        Review.objects.exclude(book=self.books[0]).update(created_at=timezone.now() - timedelta(days=1))
        response = self.client.get('/api/book/recent-reviews/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 10)
        self.assertEqual(response.json()[0]['isbn'], self.books[0].isbn)
        self.assertEqual(len({book['isbn'] for book in response.json()}), 10)

    def test_recent_reviews_are_prefetched_in_constant_queries_with_stable_latest_five(self):
        from review.models import Review
        with self.assertNumQueries(3):
            response = self.client.get('/api/book/recent-reviews/')
        self.assertEqual(response.status_code, 200)
        first = response.json()[0]
        expected = list(Review.objects.filter(book=self.books[0]).order_by('-created_at', '-pk').values_list('pk', flat=True)[:5])
        self.assertEqual([review['id'] for review in first['reviews']], expected)
        self.assertEqual(len(first['reviews']), 5)

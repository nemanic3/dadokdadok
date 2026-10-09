from unittest.mock import Mock, patch

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


@override_settings(NAVER_CLIENT_ID='fixture-id', NAVER_CLIENT_SECRET='fixture-secret')
class NaverRecommendationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    @patch('book.services.requests.get')
    def test_timeout_is_safe_504_and_shared_bounded_request(self, get):
        get.side_effect = requests.Timeout('fixture-secret private diagnostic')
        response = self.client.get('/api/recommendation/naver/', {'query': 'fixture'})
        self.assertEqual(response.status_code, 504)
        self.assertNotIn('fixture-secret', str(response.json()))
        self.assertNotIn('private diagnostic', str(response.json()))
        self.assertEqual(get.call_args.kwargs['timeout'], (3.05, 10))

    @patch('book.services.requests.get')
    def test_invalid_inputs_never_reach_naver(self, get):
        inputs = [
            {'query': 'fixture', 'display': value} for value in ['abc', '0', '101', '-1', '1.5', '９']
        ] + [{'query': 'x' * 201}] + [
            {'isbn': value, 'query': 'fallback'} for value in ['123', '9780132350885', '9780132350884 extra', ' 9780132350884', '']
        ] + [{'query': '   '}, {}]
        for params in inputs:
            with self.subTest(params=params):
                self.assertEqual(self.client.get('/api/recommendation/naver/', params).status_code, 400)
        get.assert_not_called()

    @patch('book.services.requests.get')
    def test_current_alias_duplicates_and_invalid_candidates_are_excluded(self, get):
        from book.models import Book
        Book.objects.create(isbn='9780132350884', title='current', author='Author', publisher='Publisher')
        get.return_value = Mock(json=Mock(return_value={'items': [
            {'isbn': '0132350882 9780132350884', 'title': 'current'},
            {'isbn': '0201633612 9780201633610', 'title': 'first', 'author': 'A', 'publisher': 'P', 'image': 'https://example.test/cover', 'link': 'https://example.test/book'},
            {'isbn': '9780201633610', 'title': 'duplicate'},
            {'isbn': '0201633612', 'title': 'duplicate alias'},
            {'isbn': '9780132350885', 'title': 'invalid'},
        ]}))
        response = self.client.get('/api/recommendation/naver/', {'isbn': '9780132350884', 'display': 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{'isbn': '9780201633610', 'title': 'first', 'author': 'A', 'publisher': 'P', 'image': 'https://example.test/cover', 'link': 'https://example.test/book'}])
        self.assertEqual(get.call_count, 1, 'stored metadata should avoid an extra Naver lookup')
        self.assertEqual(get.call_args.kwargs['params']['query'], 'Publisher Author')
        self.assertEqual(get.call_args.kwargs['params']['display'], 1)

    @patch('book.services.requests.get')
    def test_metadata_absent_uses_explicit_query_fallback(self, get):
        get.side_effect = [Mock(json=Mock(return_value={'items': []})), Mock(json=Mock(return_value={'items': [{'isbn': '9780201633610', 'title': 'fallback'}]}))]
        result = self.client.get('/api/recommendation/naver/', {'isbn': '9780132350884', 'query': 'explicit'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()[0]['title'], 'fallback')
        self.assertEqual(get.call_args_list[0].kwargs['params']['query'], '9780132350884')
        self.assertNotIn('d_isbn', get.call_args_list[0].kwargs['params'])
        self.assertEqual(get.call_args_list[1].kwargs['params']['query'], 'explicit')

    @patch('book.services.requests.get')
    def test_missing_metadata_without_fallback_is_empty_not_broad_search(self, get):
        get.return_value = Mock(json=Mock(return_value={'items': []}))
        response = self.client.get('/api/recommendation/naver/', {'isbn': '9780132350884'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        self.assertEqual(get.call_count, 1)

    @patch('book.services.requests.get')
    def test_empty_success_upstream_failure_and_malformed_response_are_distinct(self, get):
        for data, expected in [({'items': []}, 200), ({'items': 'bad'}, 502), ({'items': [None]}, 502)]:
            get.return_value = Mock(json=Mock(return_value=data))
            response = self.client.get('/api/recommendation/naver/', {'query': 'fixture'})
            self.assertEqual(response.status_code, expected)
            if expected == 200:
                self.assertEqual(response.json(), [])
        get.side_effect = requests.RequestException('fixture-secret private diagnostic')
        response = self.client.get('/api/recommendation/naver/', {'query': 'fixture'})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('fixture-secret', str(response.json()))

    @patch('book.services.requests.get')
    def test_metadata_lookup_failure_is_not_silently_treated_as_empty_fallback(self, get):
        get.side_effect = requests.Timeout('fixture-secret private metadata diagnostic')
        response = self.client.get('/api/recommendation/naver/', {'isbn': '9780132350884', 'query': 'fallback'})
        self.assertEqual(response.status_code, 504)
        self.assertEqual(get.call_count, 1)
        self.assertNotIn('fixture-secret', str(response.json()))

    @patch('book.services.requests.get')
    def test_isbn_metadata_must_match_and_missing_author_publisher_uses_explicit_fallback(self, get):
        for metadata in [{'isbn': '9780201633610', 'author': 'Wrong'}, {'isbn': '9780132350884', 'author': None, 'publisher': None}]:
            get.side_effect = [Mock(json=Mock(return_value={'items': [metadata]})), Mock(json=Mock(return_value={'items': []}))]
            self.assertEqual(self.client.get('/api/recommendation/naver/', {'isbn': '9780132350884', 'query': 'explicit'}).json(), [])
            self.assertEqual(get.call_args.kwargs['params']['query'], 'explicit')

    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'book': '2/min'}})
    @patch('book.services.requests.get')
    def test_book_throttle_blocks_upstream_even_with_spoofed_forwarded_address(self, get):
        get.return_value = Mock(json=Mock(return_value={'items': []}))
        for address in ['first', 'second']:
            self.assertEqual(self.client.get('/api/recommendation/naver/', {'query': 'fixture'}, HTTP_X_FORWARDED_FOR=address).status_code, 200)
        self.assertEqual(self.client.get('/api/recommendation/naver/', {'query': 'fixture'}, HTTP_X_FORWARDED_FOR='third').status_code, 429)
        self.assertEqual(get.call_count, 2)


def fixture_isbn(number):
    prefix = f'978{number:09d}'
    check = (10 - sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(prefix)) % 10) % 10
    return prefix + str(check)


class PersonalizedRecommendationTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        cache.clear()
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username='reader', nickname='reader', email='private@example.test')
        self.other = get_user_model().objects.create_user(username='community')
        self.client.force_authenticate(self.user)

    def book(self, number, **fields):
        from book.models import Book
        return Book.objects.create(isbn=fixture_isbn(number), title=f'book {number}', **fields)

    def review(self, book, rating, user=None):
        from review.models import Review
        return Review.objects.create(book=book, user=user or self.other, rating=rating, content='private review content')

    def test_authenticated_cold_start_uses_community_rating_then_count_then_stable_isbn(self):
        first = self.book(1)
        popular = self.book(2)
        lesser = self.book(3)
        unknown = self.book(4)
        self.review(first, 5)
        self.review(popular, 5)
        self.review(lesser, 2)
        self.review(popular, 5, self.user)
        # A separate cold-start reader must see no personal history.
        from django.contrib.auth import get_user_model
        cold = get_user_model().objects.create_user(username='cold', nickname='cold')
        self.client.force_authenticate(cold)
        response = self.client.get('/api/recommendation/personalized/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['isbn'] for item in response.json()], [popular.isbn, first.isbn, lesser.isbn, unknown.isbn])
        self.assertEqual(response.json(), self.client.get('/api/recommendation/personalized/').json())
        for item in response.json():
            self.assertEqual(set(item), {'isbn', 'title', 'author', 'publisher', 'image', 'link'})
        self.assertNotIn('private', str(response.json()))

    def test_anonymous_is_not_authorized(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/recommendation/personalized/').status_code, 401)

    def test_display_and_current_isbn_are_bounded_without_external_requests(self):
        with patch('book.services.requests.get') as get:
            for params in [{'display': value} for value in ['abc', '0', '101', '-1', '９']] + [{'isbn': '9780132350885'}, {'isbn': ''}]:
                with self.subTest(params=params):
                    self.assertEqual(self.client.get('/api/recommendation/personalized/', params).status_code, 400)
            for number in range(1, 8):
                self.book(number)
            self.assertEqual(len(self.client.get('/api/recommendation/personalized/', {'display': 2}).json()), 2)
            get.assert_not_called()

    def test_high_ratings_weight_author_and_publisher_above_community_rank(self):
        favorite = self.book(1, author='Favorite Author', publisher='Favorite Publisher')
        self.review(favorite, 5, self.user)
        both = self.book(8, author='Favorite Author', publisher='Favorite Publisher')
        author = self.book(7, author='Favorite Author')
        publisher = self.book(6, publisher='Favorite Publisher')
        popular = self.book(5, author='Other', publisher='Other')
        self.review(popular, 5)
        response = self.client.get('/api/recommendation/personalized/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['isbn'] for item in response.json()], [both.isbn, author.isbn, publisher.isbn, popular.isbn])

    def test_low_null_and_out_of_range_ratings_never_create_positive_preferences(self):
        for number, rating in enumerate([1, None, 100], 1):
            self.review(self.book(number, author='Disliked', publisher='Disliked'), rating, self.user)
        disliked = self.book(4, author='Disliked', publisher='Disliked')
        popular = self.book(5, author='Other')
        self.review(popular, 4)
        self.review(disliked, 100)
        self.assertEqual([item['isbn'] for item in self.client.get('/api/recommendation/personalized/').json()], [popular.isbn, disliked.isbn])

    def test_read_current_invalid_and_duplicate_isbn_aliases_are_excluded_before_limit(self):
        from book.models import Book
        from review.models import Review
        read = Book.objects.create(isbn='9780132350884', title='read')
        Book.objects.create(isbn='0132350882', title='read alias')
        self.review(read, None, self.user)
        current = self.book(1)
        Book.objects.create(isbn='9780201633610', title='candidate')
        Book.objects.create(isbn='0201633612', title='candidate alias')
        Book.objects.create(isbn=None, title='missing identifier')
        Book.objects.create(isbn='invalid', title='invalid identifier')
        other = self.book(3)
        before = (list(Book.objects.values()), list(Review.objects.values()))
        with self.assertNumQueries(2):
            response = self.client.get('/api/recommendation/personalized/', {'isbn': current.isbn, 'display': 2})
        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertEqual(len(items), 2)
        from .services import isbn_identity
        self.assertEqual({isbn_identity(item['isbn']) for item in items}, {'9780201633610', other.isbn})
        self.assertEqual(before, (list(Book.objects.values()), list(Review.objects.values())))

    def test_no_unread_candidates_is_successful_empty_array(self):
        self.review(self.book(1), 5, self.user)
        self.assertEqual(self.client.get('/api/recommendation/personalized/').json(), [])

    def test_rating_strength_and_preferences_are_bound_to_authenticated_user_only(self):
        strong = self.book(1, author='Strong')
        weak = self.book(2, author='Weak')
        self.review(strong, 5, self.user)
        self.review(weak, 4, self.user)
        strong_candidate = self.book(9, author='Strong')
        weak_candidate = self.book(3, author='Weak')
        self.review(strong_candidate, 5, self.other)
        self.assertEqual([item['isbn'] for item in self.client.get('/api/recommendation/personalized/', {'user': self.other.pk}).json()], [strong_candidate.isbn, weak_candidate.isbn])
        self.client.force_authenticate(self.other)
        other_items = self.client.get('/api/recommendation/personalized/').json()
        self.assertNotIn(strong_candidate.isbn, [item['isbn'] for item in other_items])
        self.assertEqual(other_items[0]['isbn'], strong.isbn)

    def test_real_jwt_request_and_current_isbn10_alias_resolve_without_sensitive_data(self):
        from book.models import Book
        from rest_framework_simplejwt.tokens import RefreshToken
        Book.objects.create(isbn='9780132350884', title='current')
        candidate = self.book(1)
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(self.user).access_token))
        response = self.client.get('/api/recommendation/personalized/', {'isbn': '0132350882'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['isbn'] for item in response.json()], [candidate.isbn])
        self.assertNotIn('private', str(response.json()))

    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'book': '1/min'}})
    @patch('book.services.requests.get')
    def test_personalized_and_naver_share_book_throttle(self, get):
        self.assertEqual(self.client.get('/api/recommendation/personalized/').status_code, 200)
        self.assertEqual(self.client.get('/api/recommendation/naver/', {'query': 'fixture'}).status_code, 429)
        get.assert_not_called()

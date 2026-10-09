"""Real API/ORM regressions; deterministic interleaving, not threaded load.

Only the provider and scheduling seam are replaced. Winning inserts execute
outside the losing write's savepoint, so rollback cannot erase the winner.
"""
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, connection
from django.db.models.query import QuerySet
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from book.models import Book
from review.models import Review

ISBN = '9780132350884'
PASSWORD = 'Synthetic-Cloud!9837'
REVIEW_KEYS = {'id', 'user_nickname', 'profile_image', 'isbn', 'content', 'rating',
               'created_at', 'updated_at', 'likes_count', 'comments_count'}


class ReviewImportQuotaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = get_user_model().objects.create_user(
            username='quota-reader', nickname='quota-reader',
            email='quota@example.test', password=PASSWORD)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def post_review(self, **headers):
        return self.client.post('/api/review/', {
            'isbn': ISBN, 'content': 'Synthetic review', 'rating': 4,
        }, format='json', **headers)

    def test_all_upstream_consumers_share_quota_and_xff_cannot_reset_it(self):
        configuration = {**settings.REST_FRAMEWORK, 'DEFAULT_THROTTLE_RATES': {
            **settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'], 'book': '1/min'}}
        consumers = [('/api/book/search/?query=fixture', 200),
                     ('/api/book/isbn/'+ISBN+'/', 404),
                     ('/api/recommendation/naver/?query=fixture', 200),
                     (None, 400)]
        with override_settings(REST_FRAMEWORK=configuration):
            for first_path, first_status in consumers:
                with self.subTest(first=first_path):
                    cache.clear()
                    provider_result = Mock(json=Mock(return_value={'items': []}))
                    with patch('book.services.requests.get', return_value=provider_result) as provider:
                        first = self.client.get(first_path) if first_path else self.post_review()
                        self.assertEqual(first.status_code, first_status)
                        self.assertEqual(provider.call_count, 1)
                        for spoof in ['192.0.2.1', '198.51.100.2', '203.0.113.3']:
                            denied = self.post_review(HTTP_X_FORWARDED_FOR=spoof)
                            self.assertEqual(denied.status_code, 429)
                            self.assertIn('Retry-After', denied)
                        for path, _ in consumers:
                            if path:
                                denied = self.client.get(path, HTTP_X_FORWARDED_FOR='192.0.2.9')
                                self.assertEqual(denied.status_code, 429)
                        self.assertEqual(provider.call_count, 1)
                        self.assertEqual(Book.objects.count(), 0)
                        self.assertEqual(Review.objects.count(), 0)

    def test_cached_book_review_reads_and_edits_do_not_consume_upstream_budget(self):
        Book.objects.create(isbn=ISBN, title='Cached winner')
        configuration = {**settings.REST_FRAMEWORK, 'DEFAULT_THROTTLE_RATES': {
            **settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'], 'book': '1/min'}}
        with override_settings(REST_FRAMEWORK=configuration), patch(
                'book.services.requests.get', return_value=Mock(json=Mock(return_value={'items': []}))) as provider:
            created = self.post_review()
            self.assertEqual(created.status_code, 201)
            self.assertEqual(set(created.data), REVIEW_KEYS)
            route = '/api/review/'+str(created.data['id'])+'/'
            self.assertEqual(self.client.get('/api/book/search/?q=fixture').status_code, 200)
            self.assertEqual(self.client.get(route).status_code, 200)
            self.assertEqual(self.client.get('/api/review/').status_code, 200)
            self.assertEqual(self.client.patch(route, {'content': 'Edited'}, format='json').status_code, 200)
            self.assertEqual(self.client.put(route, {'content': 'Replaced', 'rating': 3}, format='json').status_code, 200)
            other = get_user_model().objects.create_user(username='quota-other', nickname='quota-other')
            self.client.force_authenticate(other)
            second = self.post_review()
            self.assertEqual(second.status_code, 201)
            self.assertEqual(set(second.data), REVIEW_KEYS)
            self.assertEqual(provider.call_count, 1)


class BookImportRaceTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = get_user_model().objects.create_user(
            username='race-reader', nickname='race-reader')
        self.other = get_user_model().objects.create_user(
            username='race-other', nickname='race-other')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.client.raise_request_exception = False

    def post_review(self):
        return self.client.post('/api/review/', {
            'isbn': ISBN, 'content': 'Losing request review', 'rating': 4,
        }, format='json')

    def insert_winning_book(self, isbn):
        self.winner = Book.objects.create(isbn=isbn, title='Winning metadata', author='Winner')
        self.winning_review = Review.objects.create(
            user=self.other, book=self.winner, content='Winning other review', rating=5)
        return {'title': 'Losing metadata', 'author': 'Loser'}

    def test_competing_isbn_insert_reuses_winner_and_both_users_reviews_survive(self):
        with patch('review.views.get_book_by_isbn_from_naver', side_effect=self.insert_winning_book):
            response = self.post_review()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), REVIEW_KEYS)
        self.assertEqual(Book.objects.filter(isbn=ISBN).count(), 1)
        self.winner.refresh_from_db()
        self.assertEqual((self.winner.title, self.winner.author), ('Winning metadata', 'Winner'))
        self.winning_review.refresh_from_db()
        self.assertEqual(self.winning_review.content, 'Winning other review')
        self.assertEqual(Review.objects.filter(book=self.winner).count(), 2)
        self.assertEqual(Review.objects.get(user=self.user).book_id, self.winner.pk)

    def test_unrelated_book_integrity_error_is_not_reclassified_even_with_winner(self):
        original_create = Book.objects.create

        def invalid_create(**kwargs):
            return original_create(**{**kwargs, 'title': None})

        def provider(isbn):
            metadata = self.insert_winning_book(isbn)
            self.creation_patch = patch.object(Book.objects, 'create', side_effect=invalid_create)
            self.creation_patch.start()
            self.addCleanup(self.creation_patch.stop)
            return metadata

        with patch('review.views.get_book_by_isbn_from_naver', side_effect=provider):
            response = self.post_review()
        self.assertEqual(response.status_code, 500)
        self.assertIs(response.exc_info[0], IntegrityError)
        error = response.exc_info[1]
        if connection.vendor == 'postgresql':
            self.assertEqual(error.__cause__.sqlstate, '23502')
            self.assertEqual(error.__cause__.diag.column_name, 'title')
        else:
            self.assertIn('NOT NULL', str(error))
        self.assertEqual(Book.objects.filter(isbn=ISBN).count(), 1)
        self.winner.refresh_from_db()
        self.assertEqual(self.winner.title, 'Winning metadata')

    def competing_review_after_exists(self, unrelated=False):
        original_exists = QuerySet.exists
        original_create = Review.objects.create
        self.injected = False

        def exists(queryset):
            found = original_exists(queryset)
            if queryset.model is Review and not found and not self.injected:
                self.injected = True
                self.review_winner = original_create(
                    user=self.user, book=self.book, content='Winning content', rating=5)
                if unrelated:
                    self.creation_patch = patch.object(Review.objects, 'create', side_effect=
                        lambda **kwargs: original_create(id=self.review_winner.pk, **kwargs))
                    self.creation_patch.start()
                    self.addCleanup(self.creation_patch.stop)
            return found

        return patch.object(QuerySet, 'exists', exists)

    def test_competing_review_unique_insert_returns_explicit_400_preserving_winner(self):
        self.book = Book.objects.create(isbn=ISBN, title='Cached book')
        with self.competing_review_after_exists():
            response = self.post_review()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data['detail']), '이미 해당 책에 대한 리뷰를 작성하셨습니다.')
        self.assertTrue(self.injected)
        self.assertEqual(Review.objects.filter(user=self.user, book=self.book).count(), 1)
        self.review_winner.refresh_from_db()
        self.assertEqual((self.review_winner.content, self.review_winner.rating), ('Winning content', 5))

    def test_unrelated_review_primary_key_integrity_error_is_not_swallowed_with_winner(self):
        self.book = Book.objects.create(isbn=ISBN, title='Cached book')
        with self.competing_review_after_exists(unrelated=True):
            response = self.post_review()
        self.assertEqual(response.status_code, 500)
        self.assertIs(response.exc_info[0], IntegrityError)
        error = response.exc_info[1]
        if connection.vendor == 'postgresql':
            self.assertEqual(error.__cause__.sqlstate, '23505')
            with connection.cursor() as cursor:
                constraint = connection.introspection.get_constraints(cursor, 'review')[error.__cause__.diag.constraint_name]
            self.assertTrue(constraint['primary_key'])
            self.assertEqual(constraint['columns'], ['id'])
        else:
            self.assertIn('review.id', str(error))
        self.assertTrue(self.injected)
        self.review_winner.refresh_from_db()
        self.assertEqual(self.review_winner.content, 'Winning content')

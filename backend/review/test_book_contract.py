from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from book.models import Book


class BookReviewContractTests(APITestCase):
    def test_unregistered_book_has_a_successful_empty_public_review_list(self):
        response = self.client.get('/api/review/library/9780000000019/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        self.assertFalse(Book.objects.exists())

    def test_new_review_preserves_upstream_book_link(self):
        user = get_user_model().objects.create_user(username='isolated-link-reader', nickname='링크검증')
        self.client.force_authenticate(user)
        metadata = {'isbn': '9780000000019', 'title': '격리 도서', 'author': '격리 저자',
                    'publisher': '격리 출판사', 'pubdate': '20260101',
                    'image': '', 'link': 'https://example.test/book/9780000000019'}
        with patch('review.views.get_book_by_isbn_from_naver', return_value=metadata):
            response = self.client.post('/api/review/', {'isbn': metadata['isbn'], 'content': '격리 기록', 'rating': 4}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Book.objects.get(isbn=metadata['isbn']).link, metadata['link'])

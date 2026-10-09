from datetime import datetime, timedelta, timezone

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from book.models import Book
from .models import Comment, Like, Review


class ReviewAPIFixture(APITestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='review-owner', nickname='작성자')
        self.other = get_user_model().objects.create_user(username='review-other', nickname='타인')
        self.book = Book.objects.create(title='격리 도서', isbn='9780000000001')
        self.review = Review.objects.create(user=self.owner, book=self.book, content='원문', rating=4)
        self.detail = f'/api/review/{self.review.pk}/'


class ReviewOwnershipTests(ReviewAPIFixture):
    def test_other_user_cannot_put_patch_or_delete_review(self):
        self.client.force_authenticate(self.other)
        for method in ('put', 'patch', 'delete'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.detail, {'content': '변조', 'rating': 1}, format='json')
                self.assertEqual(response.status_code, 403)
                self.review.refresh_from_db()
                self.assertEqual((self.review.user_id, self.review.content, self.review.rating), (self.owner.pk, '원문', 4))

    def test_owner_can_put_patch_and_delete_with_compatible_response(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.put(self.detail, {'content': '수정', 'rating': 3}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(self.detail, {'rating': 0}, format='json').status_code, 200)
        self.review.refresh_from_db()
        self.assertEqual((self.review.content, self.review.rating), ('수정', 0))
        response = self.client.delete(self.detail)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'message': 'Review successfully deleted.'})
        self.assertFalse(Review.objects.filter(pk=self.review.pk).exists())

    def test_anonymous_can_read_but_cannot_mutate(self):
        self.assertEqual(self.client.get(self.detail).status_code, 200)
        self.assertEqual(self.client.get('/api/review/').status_code, 200)
        for method in ('put', 'patch', 'delete'):
            response = getattr(self.client, method)(self.detail, {'content': '변조', 'rating': 1}, format='json')
            self.assertIn(response.status_code, (401, 403))
        self.review.refresh_from_db()
        self.assertEqual(self.review.content, '원문')

    def test_missing_review_returns_404(self):
        self.client.force_authenticate(self.owner)
        for method in ('put', 'patch', 'delete'):
            response = getattr(self.client, method)('/api/review/999999/', {'content': '수정', 'rating': 3}, format='json')
            self.assertEqual(response.status_code, 404)


class ReviewValidationTests(ReviewAPIFixture):
    def test_create_requires_valid_content_and_finite_rating(self):
        self.client.force_authenticate(self.other)
        invalid_fields = (
            ('content', None), ('content', ''), ('content', '  '),
            ('content', 123), ('content', []), ('content', {}),
            ('rating', None), ('rating', -1), ('rating', 5.1),
            ('rating', 'NaN'), ('rating', 'Infinity'), ('rating', '-Infinity'),
            ('rating', True), ('rating', 'not-a-rating'),
        )
        for field, value in invalid_fields:
            with self.subTest(field=field, value=value), transaction.atomic():
                data = {'isbn': self.book.isbn, 'content': '독서 기록', 'rating': 4}
                data[field] = value
                response = self.client.post('/api/review/', data, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
                self.assertFalse(Review.objects.filter(user=self.other).exists())
        for field in ('content', 'rating'):
            with self.subTest(missing=field), transaction.atomic():
                data = {'isbn': self.book.isbn, 'content': '독서 기록', 'rating': 4}
                data.pop(field)
                response = self.client.post('/api/review/', data, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
                self.assertFalse(Review.objects.filter(user=self.other).exists())

    def test_patch_rejects_invalid_input_without_changing_review(self):
        self.client.force_authenticate(self.owner)
        for data in ({'content': None}, {'content': 123}, {'content': '  '},
                     {'rating': None}, {'rating': -1}, {'rating': 6},
                     {'rating': 'NaN'}, {'rating': True}):
            with self.subTest(data=data), transaction.atomic():
                response = self.client.patch(self.detail, data, format='json')
                self.assertEqual(response.status_code, 400)
                self.review.refresh_from_db()
                self.assertEqual((self.review.content, self.review.rating), ('원문', 4))

    def test_create_accepts_rating_boundaries_and_server_owns_identity(self):
        self.client.force_authenticate(self.other)
        response = self.client.post('/api/review/', {
            'isbn': self.book.isbn, 'content': '  독서 기록  ', 'rating': 0,
            'user': self.owner.pk, 'book': 999999,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        created = Review.objects.get(pk=response.data['id'])
        self.assertEqual((created.user_id, created.book_id, created.content, created.rating),
                         (self.other.pk, self.book.pk, '독서 기록', 0))
        self.assertEqual(self.client.patch(f'/api/review/{created.pk}/', {'rating': 5}, format='json').status_code, 200)
        duplicate = self.client.post('/api/review/', {'isbn': self.book.isbn, 'content': '중복', 'rating': 3}, format='json')
        self.assertEqual(duplicate.status_code, 400)


class ReviewProfileImageTests(ReviewAPIFixture):
    def test_public_review_exposes_selected_allowlisted_image_without_email(self):
        self.owner.profile_image = 'profile_images/profile_image3.svg'
        self.owner.email = 'private-review@example.test'
        self.owner.save(update_fields=['profile_image', 'email'])
        for url in [self.detail, '/api/review/']:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                row = response.data if isinstance(response.data, dict) else response.data[0]
                self.assertEqual(row.get('profile_image'), '/media/profile_images/profile_image3.svg')
                self.assertNotIn('email', row)
                self.assertNotIn(self.owner.email, str(row))
        self.client.force_authenticate(self.other)
        self.other.profile_image = 'profile_images/profile_image4.svg'
        self.other.save(update_fields=['profile_image'])
        response = self.client.post('/api/review/', {'isbn': self.book.isbn, 'content': '내 기록', 'rating': 3,
                                                    'profile_image': 'https://untrusted.example/image.svg'},
                                    format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data.get('profile_image'), '/media/profile_images/profile_image4.svg')
        self.other.refresh_from_db()
        self.assertEqual(self.other.profile_image, 'profile_images/profile_image4.svg')

    def test_public_review_legacy_invalid_image_uses_safe_fallback_without_database_rewrite(self):
        self.owner.profile_image = 'https://untrusted.example/image.svg'
        self.owner.save(update_fields=['profile_image'])
        response = self.client.get(self.detail)
        self.assertEqual(response.data.get('profile_image'), '/media/profile_images/profile_image.svg')
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.profile_image, 'https://untrusted.example/image.svg')


class ReviewReadContractTests(ReviewAPIFixture):
    def test_empty_library_is_an_array(self):
        self.client.force_authenticate(self.other)
        response = self.client.get('/api/review/library/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_legacy_null_review_reads_are_safe_without_rewriting_data(self):
        Review.objects.filter(pk=self.review.pk).update(content=None, rating=None)
        for url in (self.detail, '/api/review/', f'/api/review/library/{self.book.isbn}/'):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                row = response.data if isinstance(response.data, dict) else response.data[0]
                self.assertEqual((row['content'], row['rating']), ('', 0))
        self.client.force_authenticate(self.owner)
        response = self.client.get('/api/review/library/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.data[0]['short_review'], response.data[0]['rating']), ('', 0))
        self.review.refresh_from_db()
        self.assertIsNone(self.review.content)
        self.assertIsNone(self.review.rating)

    def test_library_is_private_and_normal_fields_remain_compatible(self):
        self.assertIn(self.client.get('/api/review/library/').status_code, (401, 403))
        self.client.force_authenticate(self.owner)
        response = self.client.get('/api/review/library/')
        self.assertEqual(response.data[0]['isbn'], self.book.isbn)
        self.assertEqual((response.data[0]['short_review'], response.data[0]['rating']), ('원문', 4))
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get('/api/review/library/').data, [])


class LikedReviewsTests(ReviewAPIFixture):
    def test_liked_initial_state_is_private_and_empty_for_new_user(self):
        self.assertIn(self.client.get('/api/review/liked/').status_code, (401, 403))
        self.client.force_authenticate(self.other)
        response = self.client.get('/api/review/liked/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_liked_state_matches_toggle_and_does_not_leak_other_users(self):
        Like.objects.create(user=self.owner, review=self.review)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get('/api/review/liked/').data, [])
        response = self.client.post(f'/api/review/{self.review.pk}/like/')
        self.assertEqual((response.status_code, response.data['message'], response.data['likes_count']),
                         (201, 'Like added', 2))
        response = self.client.get('/api/review/liked/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [{'review_id': self.review.pk}])
        response = self.client.post(f'/api/review/{self.review.pk}/like/')
        self.assertEqual((response.status_code, response.data['message'], response.data['likes_count']),
                         (200, 'Like removed', 1))
        self.assertEqual(self.client.get('/api/review/liked/').data, [])
        self.assertTrue(Like.objects.filter(user=self.owner, review=self.review).exists())


class CommentProfileImageTests(ReviewAPIFixture):
    def test_public_comment_exposes_selected_allowlisted_image_without_email(self):
        self.other.profile_image = 'profile_images/profile_image3.svg'
        self.other.email = 'private-comment@example.test'
        self.other.save(update_fields=['profile_image', 'email'])
        self.client.force_authenticate(self.other)
        response = self.client.post(f'/api/review/{self.review.pk}/comments/', {
            'content': '내 댓글', 'profile_image': 'https://untrusted.example/image.svg',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data.get('profile_image'), '/media/profile_images/profile_image3.svg')
        self.assertNotIn('email', response.data)
        self.client.force_authenticate(None)
        response = self.client.get(f'/api/review/{self.review.pk}/comments/list/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0].get('profile_image'), '/media/profile_images/profile_image3.svg')
        self.assertNotIn('email', response.data[0])
        self.assertNotIn(self.other.email, str(response.data))
        self.other.refresh_from_db()
        self.assertEqual(self.other.profile_image, 'profile_images/profile_image3.svg')

    def test_public_comment_legacy_invalid_image_uses_safe_fallback_without_database_rewrite(self):
        self.other.profile_image = '../../private/image.svg'
        self.other.save(update_fields=['profile_image'])
        Comment.objects.create(user=self.other, review=self.review, content='기존 댓글')
        response = self.client.get(f'/api/review/{self.review.pk}/comments/list/')
        self.assertEqual(response.data[0].get('profile_image'), '/media/profile_images/profile_image.svg')
        self.other.refresh_from_db()
        self.assertEqual(self.other.profile_image, '../../private/image.svg')


class CommentValidationTests(ReviewAPIFixture):
    def test_comment_endpoints_reject_non_object_request_bodies(self):
        self.client.force_authenticate(self.other)
        url = f'/api/review/{self.review.pk}/comments/'
        for method in ('post', 'put', 'patch', 'delete'):
            for body in ([], [1], 'not-an-object'):
                with self.subTest(method=method, body=body):
                    response = getattr(self.client, method)(url, body, format='json')
                    self.assertEqual(response.status_code, 400)

    def test_comment_post_rejects_non_string_null_and_blank_content(self):
        self.client.force_authenticate(self.other)
        url = f'/api/review/{self.review.pk}/comments/'
        for value in (None, '', '  ', 123, True, [], {}):
            with self.subTest(value=value), transaction.atomic():
                response = self.client.post(url, {'content': value}, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertFalse(Comment.objects.exists())
        self.assertEqual(self.client.post(url, {}, format='json').status_code, 400)

    def test_comment_post_server_sets_user_and_review_and_public_list_stays_open(self):
        self.client.force_authenticate(self.other)
        response = self.client.post(f'/api/review/{self.review.pk}/comments/', {
            'content': '  댓글 내용  ', 'user': self.owner.pk, 'review': 999999,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        comment = Comment.objects.get(pk=response.data['id'])
        self.assertEqual((comment.user_id, comment.review_id, comment.content),
                         (self.other.pk, self.review.pk, '댓글 내용'))
        self.client.force_authenticate(None)
        response = self.client.get(f'/api/review/{self.review.pk}/comments/list/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['user_nickname'], self.other.nickname)
        self.assertIn(self.client.post(f'/api/review/{self.review.pk}/comments/', {'content': '익명'}, format='json').status_code, (401, 403))


class CommentOwnershipTests(ReviewAPIFixture):
    def setUp(self):
        super().setUp()
        self.comment = Comment.objects.create(user=self.other, review=self.review, content='댓글 원문')
        self.legacy_url = f'/api/review/{self.review.pk}/comments/'
        self.nested_url = f'{self.legacy_url}{self.comment.pk}/'

    def test_review_owner_cannot_change_another_users_comment(self):
        self.client.force_authenticate(self.owner)
        for url in (self.legacy_url, self.nested_url):
            for method in ('put', 'patch', 'delete'):
                with self.subTest(url=url, method=method), transaction.atomic():
                    response = getattr(self.client, method)(url, {'comment_id': self.comment.pk, 'content': '변조'}, format='json')
                    self.assertEqual(response.status_code, 403)
                    self.comment.refresh_from_db()
                    self.assertEqual(self.comment.content, '댓글 원문')

    def test_comment_owner_can_edit_without_reassigning_identity(self):
        self.client.force_authenticate(self.other)
        for url in (self.legacy_url, self.nested_url):
            for method in ('put', 'patch'):
                with self.subTest(url=url, method=method):
                    response = getattr(self.client, method)(url, {
                        'comment_id': self.comment.pk, 'content': '  수정 댓글  ',
                        'user': self.owner.pk, 'review': 999999,
                    }, format='json')
                    self.assertEqual(response.status_code, 200)
                    self.comment.refresh_from_db()
                    self.assertEqual((self.comment.user_id, self.comment.review_id, self.comment.content),
                                     (self.other.pk, self.review.pk, '수정 댓글'))

    def test_comment_owner_can_delete_using_existing_body_or_nested_alias(self):
        self.client.force_authenticate(self.other)
        response = self.client.delete(self.legacy_url, {'comment_id': self.comment.pk}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())
        second = Comment.objects.create(user=self.other, review=self.review, content='두 번째')
        response = self.client.delete(f'{self.legacy_url}{second.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Comment.objects.filter(pk=second.pk).exists())

    def test_mutations_are_bound_to_parent_review_and_missing_comments_are_404(self):
        self.client.force_authenticate(self.other)
        another_book = Book.objects.create(title='다른 책', isbn='9780000000002')
        another_review = Review.objects.create(user=self.owner, book=another_book, content='다른 리뷰', rating=3)
        for comment_id in (self.comment.pk, 999999):
            for url in (f'/api/review/{another_review.pk}/comments/',
                        f'/api/review/{another_review.pk}/comments/{comment_id}/'):
                for method in ('put', 'patch', 'delete'):
                    with self.subTest(url=url, method=method):
                        response = getattr(self.client, method)(url, {'comment_id': comment_id, 'content': '수정'}, format='json')
                        self.assertEqual(response.status_code, 404)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, '댓글 원문')

    def test_comment_mutation_validates_content_and_identifiers(self):
        self.client.force_authenticate(self.other)
        for url in (self.legacy_url, self.nested_url):
            for method in ('put', 'patch'):
                for content in (None, '', '  ', 123, True, [], {}):
                    with self.subTest(url=url, method=method, content=content):
                        response = getattr(self.client, method)(url, {'comment_id': self.comment.pk, 'content': content}, format='json')
                        self.assertEqual(response.status_code, 400)
                self.assertEqual(getattr(self.client, method)(url, {'comment_id': self.comment.pk}, format='json').status_code, 400)
        for comment_id in (None, True, 1.0, '1.0', 'bad', [], {}, 0, -1, '9' * 100):
            for method in ('put', 'patch', 'delete'):
                with self.subTest(comment_id=comment_id, method=method):
                    response = getattr(self.client, method)(self.legacy_url, {'comment_id': comment_id, 'content': '수정'}, format='json')
                    self.assertEqual(response.status_code, 400)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, '댓글 원문')

    def test_anonymous_cannot_mutate_comments(self):
        for url in (self.legacy_url, self.nested_url):
            for method in ('put', 'patch', 'delete'):
                response = getattr(self.client, method)(url, {'comment_id': self.comment.pk, 'content': '변조'}, format='json')
                self.assertIn(response.status_code, (401, 403))
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, '댓글 원문')


class RecentReviewTests(ReviewAPIFixture):
    def test_recent_books_are_ordered_unique_and_limit_after_dedup(self):
        books = [self.book]
        timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        Review.objects.filter(pk=self.review.pk).update(created_at=timestamp + timedelta(days=8))
        for index in range(1, 7):
            book = Book.objects.create(title=f'도서 {index}', isbn=f'97800000000{index + 1:02d}')
            books.append(book)
            review = Review.objects.create(user=self.owner, book=book, content='기록', rating=3)
            Review.objects.filter(pk=review.pk).update(created_at=timestamp + timedelta(days=index))
        duplicate = Review.objects.create(user=self.other, book=self.book, content='최신 중복', rating=4)
        Review.objects.filter(pk=duplicate.pk).update(created_at=timestamp + timedelta(days=9))
        with self.assertNumQueries(1):
            response = self.client.get('/api/review/recent-reviews/')
        self.assertEqual(response.status_code, 200)
        expected = [books[0].isbn] + [book.isbn for book in reversed(books[2:])]
        self.assertEqual([row['isbn'] for row in response.data], expected)
        # 같은 시각이면 최신 리뷰 pk를 안정적인 tie-breaker로 사용한다.
        Review.objects.update(created_at=timestamp)
        self.assertEqual([row['isbn'] for row in self.client.get('/api/review/recent-reviews/').data], expected)

    def test_empty_recent_books_is_public_array(self):
        Review.objects.all().delete()
        response = self.client.get('/api/review/recent-reviews/')
        self.assertEqual((response.status_code, response.data), (200, []))


class ReviewQueryTests(ReviewAPIFixture):
    def setUp(self):
        super().setUp()
        Like.objects.create(user=self.owner, review=self.review)
        Like.objects.create(user=self.other, review=self.review)
        for index in range(3):
            Comment.objects.create(user=self.other, review=self.review, content=f'댓글 {index}')
            user = get_user_model().objects.create_user(username=f'query-user-{index}', nickname=f'쿼리 사용자 {index}')
            Review.objects.create(user=user, book=self.book, content='다른 독자 기록', rating=3)
            book = Book.objects.create(title=f'내 도서 {index}', isbn=f'97800000001{index:02d}')
            Review.objects.create(user=self.owner, book=book, content='내 독서 기록', rating=0)

    def test_review_list_has_constant_query_count_and_correct_counts(self):
        with self.assertNumQueries(1):
            response = self.client.get('/api/review/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 7)
        row = next(row for row in response.data if row['id'] == self.review.pk)
        self.assertEqual((row['likes_count'], row['comments_count']), (2, 3))

    def test_review_detail_has_constant_query_count_and_correct_counts(self):
        with self.assertNumQueries(1):
            response = self.client.get(self.detail)
        self.assertEqual((response.data['likes_count'], response.data['comments_count']), (2, 3))

    def test_my_library_reads_existing_review_data_in_one_query(self):
        self.client.force_authenticate(self.owner)
        with self.assertNumQueries(1):
            response = self.client.get('/api/review/library/')
        self.assertEqual(len(response.data), 4)
        row = next(row for row in response.data if row['isbn'] == self.book.isbn)
        self.assertEqual((row['rating'], row['short_review']), (4, '원문'))
        self.assertEqual(sum(row['rating'] == 0 for row in response.data), 3)

    def test_book_reviews_do_not_query_user_for_every_review(self):
        with self.assertNumQueries(2):
            response = self.client.get(f'/api/review/library/{self.book.isbn}/')
        self.assertEqual(len(response.data), 4)
        self.assertTrue(all(isinstance(row['user'], str) for row in response.data))

    def test_comment_list_does_not_query_user_for_every_comment(self):
        with self.assertNumQueries(1):
            response = self.client.get(f'/api/review/{self.review.pk}/comments/list/')
        self.assertEqual(len(response.data), 3)
        self.assertTrue(all(row['user_nickname'] == self.other.nickname for row in response.data))

    def test_database_still_enforces_one_review_per_user_and_book(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(user=self.owner, book=self.book, content='중복', rating=3)
        self.assertEqual(Review.objects.filter(user=self.owner, book=self.book).count(), 1)


class ReviewMigrationStateTests(SimpleTestCase):
    def test_state_alignment_migration_has_no_database_operations(self):
        migration = MigrationLoader(None).disk_migrations[('review', '0003_align_review_model_state')]
        self.assertEqual(len(migration.operations), 1)
        self.assertEqual(migration.operations[0].database_operations, [])

    def test_review_migration_state_matches_models_without_database_access(self):
        loader = MigrationLoader(None)
        changes = MigrationAutodetector(loader.project_state(), ProjectState.from_apps(apps)).changes(graph=loader.graph)
        self.assertNotIn('review', changes)

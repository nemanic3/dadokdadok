"""Public calendar contract: all declared years and explicit Seoul boundaries."""
from datetime import datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from book.models import Book
from review.models import Review
from .models import Goal


class GoalCalendarBoundaryTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(username='calendar-owner', nickname='calendar-owner')
        self.client.force_authenticate(self.user)

    def record(self, at):
        book = Book.objects.create(title='Synthetic calendar boundary')
        record = Review.objects.create(user=self.user, book=book, content='Synthetic record')
        Review.objects.filter(pk=record.pk).update(created_at=at)

    def test_year_one_empty_progress_and_monthly_are_valid(self):
        for query in ['year=1', 'year=1&month=1', 'year=1&month=12']:
            for route in ['progress', 'monthly-progress']:
                with self.subTest(query=query, route=route):
                    response = self.client.get(f'/api/goal/{route}/?{query}')
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.data['read_books'], 0)
                    self.assertIsNone(response.data['goal_id'])
        months = self.client.get('/api/goal/monthly-progress/?year=1').data['monthly_reading']
        self.assertEqual(months, {f'0001-{m:02d}': 0 for m in range(1, 13)})

    def test_year_one_create_responds_successfully_and_lists_remain_readable(self):
        ids = []
        for scope in [{'year': 1}, {'year': 1, 'month': 1}]:
            response = self.client.post('/api/goal/goal/', {'total_books': 2, **scope}, format='json')
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.data['read_books'], 0)
            ids.append(response.data['id'])
        self.assertEqual(Goal.objects.filter(user=self.user).count(), len(ids))
        for query in ['', '?year=1', '?year=1&month=1']:
            response = self.client.get('/api/goal/goal/' + query)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data), len(ids) if not query else 1)
        response = self.client.patch(f'/api/goal/goal/{ids[0]}/', {'total_books': 3}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_books'], 3)

    def test_year_one_real_historical_records_are_counted_not_silently_zeroed(self):
        self.record(datetime(1, 1, 2, tzinfo=dt_timezone.utc))
        self.record(datetime(1, 7, 2, tzinfo=dt_timezone.utc))
        self.record(datetime(2, 1, 2, tzinfo=dt_timezone.utc))
        progress = self.client.get('/api/goal/progress/?year=1')
        self.assertEqual(progress.status_code, 200)
        self.assertEqual(progress.data['read_books'], 2)
        self.assertEqual(progress.data['goal_books'], 0)
        monthly = self.client.get('/api/goal/monthly-progress/?year=1').data
        self.assertEqual(monthly['monthly_reading']['0001-01'], 1)
        self.assertEqual(monthly['monthly_reading']['0001-07'], 1)
        self.assertEqual(sum(monthly['monthly_reading'].values()), monthly['read_books'])

    def test_explicit_seoul_year_is_independent_of_active_timezone(self):
        self.record(datetime(2025, 12, 31, 16, tzinfo=dt_timezone.utc))
        with timezone.override('UTC'):
            progress = self.client.get('/api/goal/progress/?year=2026')
            self.assertEqual(progress.status_code, 200)
            self.assertEqual(progress.data['timezone'], 'Asia/Seoul')
            self.assertEqual(progress.data['read_books'], 1)
            monthly = self.client.get('/api/goal/monthly-progress/?year=2026&month=1').data
            self.assertEqual(monthly['monthly_reading'], {'2026-01': 1})
            self.assertEqual(monthly['read_books'], 1)

    def test_other_declared_year_boundaries_remain_supported(self):
        for year in [2, 999, 9999]:
            response = self.client.get(f'/api/goal/monthly-progress/?year={year}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data['monthly_reading']), 12)
            self.assertEqual(response.data['read_books'], 0)

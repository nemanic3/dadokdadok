from datetime import datetime, timezone as dt_timezone
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient
from book.models import Book
from review.models import Review
from .models import Goal


class GoalAPITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(username='goal-owner', nickname='goal-owner')
        self.other = get_user_model().objects.create(username='goal-other', nickname='goal-other')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.year = timezone.localtime().year

    def record(self, date=None, user=None):
        book = Book.objects.create(title='Goal regression')
        record = Review.objects.create(user=user or self.user, book=book, content='record')
        if date:
            Review.objects.filter(pk=record.pk).update(created_at=date)
        return record

    def test_counter_is_dynamic_read_only_and_storage_is_untouched(self):
        self.record()
        goal = Goal.objects.create(user=self.user, total_books=10, read_books=123)
        response = self.client.patch(f'/api/goal/goal/{goal.pk}/',
                                     {'read_books': 999}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['read_books'], 1)
        goal.refresh_from_db()
        self.assertEqual(goal.read_books, 123)

    def test_explicit_period_creation_keeps_legacy_unscoped(self):
        old = Goal.objects.create(user=self.user, total_books=0, read_books=5)
        response = self.client.post('/api/goal/goal/',
                                    {'total_books': 12, 'year': self.year}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data.get('year'), self.year)
        self.assertIsNone(response.data['month'])
        self.assertEqual(response.data['scope'], 'annual')
        old.refresh_from_db()
        self.assertIsNone(old.year)
        self.assertIsNone(old.month)
        self.assertEqual((old.total_books, old.read_books), (0, 5))
        monthly = self.client.post('/api/goal/goal/',
                                  {'total_books': 2, 'year': self.year, 'month': 4}, format='json')
        self.assertEqual(monthly.status_code, 201)
        self.assertEqual(monthly.data['scope'], 'monthly')
        listed = self.client.get(f'/api/goal/goal/?year={self.year}').data
        self.assertEqual([row['id'] for row in listed], [response.data['id']])
        listed_month = self.client.get(f'/api/goal/goal/?year={self.year}&month=4').data
        self.assertEqual([row['id'] for row in listed_month], [monthly.data['id']])

    def test_goal_writes_validate_positive_target_unique_period_and_no_reassignment(self):
        for value in [0, -1, 1.5, True, 'garbage']:
            with self.subTest(value=value):
                response = self.client.post('/api/goal/goal/', {'total_books': value}, format='json')
                self.assertEqual(response.status_code, 400)
        for payload in [{'total_books': 2, 'month': 1},
                        {'total_books': 2, 'year': 0},
                        {'total_books': 2, 'year': self.year, 'month': 13},
                        {'year': self.year}]:
            self.assertEqual(self.client.post('/api/goal/goal/', payload, format='json').status_code, 400)
        created = self.client.post('/api/goal/goal/', {'year': self.year, 'total_books': 10}, format='json')
        self.assertEqual(created.status_code, 201)
        duplicate = self.client.post('/api/goal/goal/', {'year': self.year, 'total_books': 15}, format='json')
        self.assertEqual(duplicate.status_code, 400)
        monthly_payload = {'year': self.year, 'month': 3, 'total_books': 2}
        monthly = self.client.post('/api/goal/goal/', monthly_payload, format='json')
        self.assertEqual(monthly.status_code, 201)
        self.assertEqual(self.client.post('/api/goal/goal/', monthly_payload, format='json').status_code, 400)
        legacy = Goal.objects.create(user=self.user, total_books=-5)
        for pk, payload in [(legacy.pk, {'year': self.year}),
                            (created.data['id'], {'year': self.year + 1}),
                            (monthly.data['id'], {'month': None})]:
            self.assertEqual(self.client.patch(f'/api/goal/goal/{pk}/', payload, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f"/api/goal/goal/{created.data['id']}/",
                                         {'total_books': 20}, format='json').status_code, 200)

    def test_post_query_period_is_explicit_and_conflicts_are_rejected(self):
        result = self.client.post(f'/api/goal/goal/?year={self.year}&month=6',
                                  {'total_books': 3}, format='json')
        self.assertEqual(result.status_code, 201)
        self.assertEqual((result.data['year'], result.data['month']), (self.year, 6))
        conflict = self.client.post(f'/api/goal/goal/?year={self.year}',
                                    {'total_books': 3, 'year': self.year - 1}, format='json')
        self.assertEqual(conflict.status_code, 400)

    def test_database_uniqueness_only_applies_to_explicit_periods(self):
        for month in [None, 5]:
            Goal.objects.create(user=self.user, total_books=1, year=self.year, month=month)
            with self.assertRaises(IntegrityError), transaction.atomic():
                Goal.objects.create(user=self.user, total_books=1, year=self.year, month=month)
        for _ in range(2):
            Goal.objects.create(user=self.user, total_books=-4)
        self.assertEqual(Goal.objects.filter(year__isnull=True).count(), 2)

    def test_scoped_statistics_share_record_date_counts_in_seoul_timezone(self):
        Goal.objects.create(user=self.user, total_books=99, read_books=999)
        annual = Goal.objects.create(user=self.user, total_books=10, year=self.year)
        january = Goal.objects.create(user=self.user, total_books=4, year=self.year, month=1)
        self.record(datetime(self.year - 1, 1, 1, tzinfo=dt_timezone.utc))
        self.record(datetime(self.year - 1, 12, 31, 16, tzinfo=dt_timezone.utc))  # Jan KST
        self.record(datetime(self.year, 1, 20, tzinfo=dt_timezone.utc))
        self.record(datetime(self.year, 1, 31, 16, tzinfo=dt_timezone.utc))  # Feb KST
        self.record(datetime(self.year, 1, 20, tzinfo=dt_timezone.utc), user=self.other)
        for month, goal, count, progress in [(None, annual, 3, 30), (1, january, 2, 50)]:
            query = f'year={self.year}' + (f'&month={month}' if month else '')
            listed = self.client.get('/api/goal/goal/?' + query)
            self.assertEqual(listed.data[0]['read_books'], count)
            response = self.client.get('/api/goal/progress/?' + query)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['goal_id'], goal.pk)
            self.assertEqual(response.data['read_books'], count)
            self.assertEqual(response.data['progress'], progress)
            self.assertEqual(response.data['date_basis'], 'REVIEW_RECORD_DATE')
            self.assertEqual(response.data['timezone'], 'Asia/Seoul')
            monthly = self.client.get('/api/goal/monthly-progress/?' + query)
            self.assertEqual(monthly.status_code, 200)
            self.assertEqual(monthly.data['read_books'], count)
            self.assertEqual(monthly.data['goal_id'], goal.pk)
            self.assertEqual(sum(monthly.data['monthly_reading'].values()), count)
            self.assertEqual(len(monthly.data['monthly_reading']), 1 if month else 12)
        february = self.client.get(f'/api/goal/monthly-progress/?year={self.year}&month=2').data
        self.assertEqual(february['monthly_reading'], {f'{self.year}-02': 1})
        self.assertIsNone(february['goal_id'])

    def test_goal_free_zero_statistics_and_legacy_progress_compatibility(self):
        self.assertEqual(self.client.get('/api/goal/progress/').status_code, 404)
        for endpoint in ['progress', 'monthly-progress']:
            response = self.client.get(f'/api/goal/{endpoint}/?year={self.year}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['goal_books'], 0)
            self.assertEqual(response.data['read_books'], 0)
            self.assertIsNone(response.data['goal_id'])
            self.assertEqual(response.data['year'], self.year)
        monthly = self.client.get('/api/goal/monthly-progress/')
        self.assertEqual(monthly.status_code, 200)
        self.assertEqual(len(monthly.data['monthly_reading']), 12)
        self.assertEqual(set(monthly.data['monthly_reading'].values()), {0})
        legacy = Goal.objects.create(user=self.user, total_books=0, read_books=77)
        self.record(datetime(self.year - 1, 2, 1, tzinfo=dt_timezone.utc))
        progress = self.client.get('/api/goal/progress/').data
        self.assertEqual(progress['goal_id'], legacy.pk)
        self.assertEqual(progress['read_books'], 1)
        self.assertEqual(progress['progress'], 0)
        self.assertEqual(progress['scope'], 'legacy')
        self.assertIsNone(progress['year'])

    def test_owner_and_query_validation(self):
        private = Goal.objects.create(user=self.other, total_books=2, year=self.year)
        for method in ['get', 'patch', 'delete']:
            kwargs = {'data': {'total_books': 3}, 'format': 'json'} if method == 'patch' else {}
            self.assertEqual(getattr(self.client, method)(f'/api/goal/goal/{private.pk}/', **kwargs).status_code, 404)
        for endpoint in ['goal', 'progress', 'monthly-progress']:
            for query in ['month=1', 'year=0', 'year=no', f'year={self.year}&month=0', 'year=10000']:
                self.assertEqual(self.client.get(f'/api/goal/{endpoint}/?{query}').status_code, 400)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/goal/goal/').status_code, 401)

    def test_review_create_update_delete_never_mutates_stored_goal_counters(self):
        import goal.signals  # Even an explicit import must not register legacy mutations.
        old = Goal.objects.create(user=self.user, total_books=0, read_books=17)
        scoped = Goal.objects.create(user=self.user, total_books=3, year=self.year, read_books=23)
        record = self.record()
        for goal, stored in [(old, 17), (scoped, 23)]:
            goal.refresh_from_db()
            self.assertEqual(goal.read_books, stored)
        record.content = 'edited'
        record.save()
        self.assertEqual(self.client.get(f'/api/goal/progress/?year={self.year}').data['read_books'], 1)
        record.delete()
        self.assertEqual(self.client.get(f'/api/goal/progress/?year={self.year}').data['read_books'], 0)
        for goal, stored in [(old, 17), (scoped, 23)]:
            goal.refresh_from_db()
            self.assertEqual(goal.read_books, stored)

    def test_counter_create_and_legacy_lists_preserve_raw_targets_and_owner(self):
        result = self.client.post('/api/goal/goal/',
                                  {'total_books': 3, 'read_books': 444, 'user': self.other.pk}, format='json')
        self.assertEqual(result.status_code, 201)
        created = Goal.objects.get(pk=result.data['id'])
        self.assertEqual(created.user_id, self.user.pk)
        self.assertEqual(created.read_books, 0)
        self.assertIsNone(created.year)
        self.assertIsNone(created.month)
        for value in [-4, 0, 0]:
            Goal.objects.create(user=self.user, total_books=value, read_books=777)
        data = self.client.get('/api/goal/goal/').data
        self.assertEqual([row['total_books'] for row in data], [3, -4, 0, 0])
        self.assertTrue(all(row['scope'] == 'legacy' for row in data))
        self.assertTrue(all(row['read_books'] == 0 for row in data))

    def test_supported_short_year_month_keys_preserve_counts(self):
        self.record(datetime(999, 7, 2, tzinfo=dt_timezone.utc))
        data = self.client.get('/api/goal/monthly-progress/?year=999').data
        self.assertEqual(data['monthly_reading']['0999-07'], 1)
        self.assertEqual(sum(data['monthly_reading'].values()), data['read_books'])

    def test_target_has_portable_integer_storage_limit(self):
        result = self.client.post('/api/goal/goal/', {'total_books': 2147483648}, format='json')
        self.assertEqual(result.status_code, 400)


    def test_legacy_target_period_is_distinct_from_current_monthly_statistics(self):
        old = Goal.objects.create(user=self.user, total_books=18)
        data = self.client.get('/api/goal/monthly-progress/').data
        self.assertEqual(data['goal_id'], old.pk)
        self.assertEqual(data['year'], self.year)
        self.assertEqual(data.get('goal_period'), {'year': None, 'month': None, 'scope': 'legacy'})
        explicit = self.client.get(f'/api/goal/monthly-progress/?year={self.year}').data
        self.assertIsNone(explicit['goal_id'])
        self.assertIsNone(explicit['goal_period'])


class GoalMigrationPreservationTests(TransactionTestCase):
    def test_nullable_period_migrations_preserve_unknown_legacy_rows(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        user = get_user_model().objects.create(username='migration-owner', nickname='migration-owner')
        executor = MigrationExecutor(connection)
        old_target = [('goal', '0002_initial')]
        new_target = [('goal', '0004_scoped_uniqueness')]
        executor.migrate(old_target)
        old_apps = executor.loader.project_state(old_target).apps
        OldGoal = old_apps.get_model('goal', 'Goal')
        for total, counter in [(0, 8), (-4, 99), (0, -9), (12, 4)]:
            OldGoal.objects.create(user_id=user.pk, total_books=total, read_books=counter)
        columns = ['id', 'user_id', 'total_books', 'read_books', 'is_completed']
        before = list(OldGoal.objects.order_by('id').values(*columns))
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(new_target)
            NewGoal = executor.loader.project_state(new_target).apps.get_model('goal', 'Goal')
            self.assertEqual(list(NewGoal.objects.order_by('id').values(*columns)), before)
            self.assertEqual(NewGoal.objects.filter(year__isnull=True, month__isnull=True).count(), 4)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())

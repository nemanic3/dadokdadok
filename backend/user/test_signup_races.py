"""Real signup unique conflicts after validation; scheduling is deterministic.

Competing create_user runs outside the losing insert savepoint. No threads,
real credentials, original DB, email uniqueness migration, or SMTP are used.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from user.serializers import SignupSerializer

PASSWORD = 'Synthetic-Cloud!9837'


class SignupInsertRaceTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.payload = {'username': 'new-synthetic', 'nickname': 'new-nickname',
                        'email': 'loser@example.test', 'password': PASSWORD}

    def compete_after_validation(self, field, unrelated=False):
        original_is_valid = SignupSerializer.is_valid
        manager = get_user_model().objects
        original_create = manager.create_user

        def validated(serializer, *args, **kwargs):
            result = original_is_valid(serializer, *args, **kwargs)
            self.assertTrue(result)
            winner_fields = {'username': 'winning-username', 'nickname': 'winning-nickname',
                             'email': 'winner@example.test', 'password': 'Winner-Cloud!67923'}
            winner_fields[field] = serializer.validated_data[field]
            self.winner = original_create(**winner_fields)
            self.winner_snapshot = {key: getattr(self.winner, key) for key in
                                    ('username', 'nickname', 'email', 'password', 'profile_image')}
            if unrelated:
                self.creation_patch = patch.object(manager, 'create_user', side_effect=
                    lambda **data: original_create(**{**data, 'profile_image': None}))
                self.creation_patch.start()
                self.addCleanup(self.creation_patch.stop)
            return result

        return patch.object(SignupSerializer, 'is_valid', validated)

    def assert_safe_race(self, field):
        with self.compete_after_validation(field):
            response = self.client.post('/api/user/signup/', self.payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(field, response.data)
        normal_duplicate = SignupSerializer(data=self.payload)
        self.assertFalse(normal_duplicate.is_valid())
        self.assertEqual(response.data[field], normal_duplicate.errors[field])
        self.assertEqual(get_user_model().objects.count(), 1)
        self.winner.refresh_from_db()
        self.assertEqual({key: getattr(self.winner, key) for key in self.winner_snapshot}, self.winner_snapshot)

    def test_username_insert_race_returns_existing_field_validation_400(self):
        # Normalization must still precede uniqueness validators and persistence.
        self.payload['username'] = 'ｎｅｗ-synthetic'
        self.assert_safe_race('username')
        self.assertEqual(self.winner.username, 'new-synthetic')

    def test_nickname_insert_race_returns_existing_field_validation_400(self):
        self.assert_safe_race('nickname')

    def test_unrelated_signup_not_null_conflict_is_not_swallowed_with_unique_winner(self):
        with self.compete_after_validation('username', unrelated=True):
            response = self.client.post('/api/user/signup/', self.payload, format='json')
        self.assertEqual(response.status_code, 500)
        self.assertIs(response.exc_info[0], IntegrityError)
        self.assertIn('NOT NULL constraint failed: user.profile_image', str(response.exc_info[1]))
        self.assertEqual(get_user_model().objects.count(), 1)
        self.winner.refresh_from_db()
        self.assertEqual({key: getattr(self.winner, key) for key in self.winner_snapshot}, self.winner_snapshot)

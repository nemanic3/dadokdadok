from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from datetime import datetime, timedelta
from unittest.mock import patch
from smtplib import SMTPException
from urllib.parse import urlsplit, parse_qs
from django.core.cache import cache
from django.core import mail
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

User = get_user_model()


@override_settings(
    DEBUG=False,
    PASSWORD_RESET_URL='https://testfrontend.example/screen/find-account.html',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class UserSecurityTests(APITestCase):
    password = 'Sailing-Pine!4829'

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='reader', nickname='독서인', email='reader@example.com',
            password=self.password,
        )

    def test_public_profile_never_discloses_email_or_password(self):
        response = self.client.get('/api/user/profile/독서인/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {'id', 'nickname', 'profile_image'})
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/user/me/').data['email'], self.user.email)

    def signup(self, **overrides):
        data = {'username': 'newreader', 'nickname': '새독서인',
                'email': 'new@example.com', 'password': self.password}
        data.update(overrides)
        return self.client.post('/api/user/signup/', data, format='json')

    def test_signup_enforces_configured_password_policy(self):
        for password in ['x', '1234567890', 'password', 'newreader']:
            with self.subTest(password=password):
                response = self.signup(password=password)
                self.assertEqual(response.status_code, 400)
                self.assertIn('password', response.data)
        response = self.signup()
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username='newreader')
        self.assertTrue(user.check_password(self.password))
        self.assertNotIn('password', response.data['user'])

    def test_signup_rejects_nfkc_equivalent_username_before_database_write(self):
        # Valid fullwidth letters normalize to the already registered ASCII username.
        raw_username = 'ｒｅａｄｅｒ'
        self.assertEqual(User.normalize_username(raw_username), self.user.username)
        from .serializers import SignupSerializer
        serializer = SignupSerializer(data={'username': raw_username, 'nickname': '새독서인',
                                            'email': 'new@example.com', 'password': self.password})
        self.assertFalse(serializer.is_valid())
        self.assertIn('username', serializer.errors)
        response = self.signup(username=raw_username)
        self.assertEqual(response.status_code, 400)
        self.assertIn('username', response.data)
        self.assertEqual(User.objects.count(), 1)

    def test_signup_username_logs_in_with_same_unicode_input_on_both_endpoints(self):
        raw_username = 'ｎｅｗｒｅａｄｅｒ'
        response = self.signup(username=raw_username)
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email='new@example.com')
        self.assertEqual(user.username, User.normalize_username(raw_username))
        for endpoint in ['/api/user/login/', '/api/auth/token/']:
            for username in [raw_username, user.username]:
                with self.subTest(endpoint=endpoint, username=username):
                    response = self.client.post(endpoint, {'username': username, 'password': self.password},
                                                format='json')
                    self.assertEqual(response.status_code, 200)

    def test_normalized_login_identifier_still_rejects_cross_account_collision(self):
        User.objects.create_user(username='reader@example.com', nickname='충돌',
                                 email='unique@example.com', password=self.password)
        for endpoint in ['/api/user/login/', '/api/auth/token/']:
            with self.subTest(endpoint=endpoint):
                response = self.client.post(endpoint, {'username': 'ｒｅａｄｅｒ@example.com',
                                                       'password': self.password}, format='json')
                self.assertEqual(response.status_code, 401)

    def update_profile(self, data):
        self.client.force_authenticate(self.user)
        return self.client.put('/api/user/update_profile/', data, format='json')

    def test_password_change_requires_current_password_and_is_atomic(self):
        for current in [None, 'wrong']:
            data = {'password': 'Cloud-Ocean!9837', 'nickname': '변경금지'}
            if current is not None:
                data['current_password'] = current
            response = self.update_profile(data)
            self.assertEqual(response.status_code, 400)
            self.user.refresh_from_db()
            self.assertEqual(self.user.nickname, '독서인')
            self.assertTrue(self.user.check_password(self.password))
        self.assertEqual(self.update_profile({'password': 'x', 'current_password': self.password}).status_code, 400)
        refresh = str(RefreshToken.for_user(self.user))
        response = self.update_profile({'password': 'Cloud-Ocean!9837', 'current_password': self.password})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Cloud-Ocean!9837'))
        self.assertNotIn('password', response.data['user'])
        self.assertNotIn('current_password', response.data['user'])
        with self.assertRaises(TokenError):
            RefreshToken(refresh)

    def test_signup_and_profile_email_are_required_and_case_insensitive(self):
        self.assertEqual(self.signup(email='').status_code, 400)
        self.assertEqual(self.signup(email='READER@example.com').status_code, 400)
        other = User.objects.create_user(username='other', nickname='다른이', email='other@example.com')
        self.assertEqual(self.update_profile({'email': 'OTHER@example.com'}).status_code, 400)
        self.assertEqual(self.update_profile({'email': ''}).status_code, 400)
        response = self.update_profile({'email': 'READER@example.com'})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'reader@example.com')
        response = self.signup(email=' New@Example.COM ')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.get(username='newreader').email, 'new@example.com')

    def login(self, **data):
        return self.client.post('/api/user/login/', data, format='json')

    def test_login_accepts_username_and_case_insensitive_email(self):
        for data in [{'username': 'reader'}, {'username': 'READER@example.com'}, {'email': 'reader@example.com'}]:
            response = self.login(**data, password=self.password)
            self.assertEqual(response.status_code, 200)
            self.assertIn('access_token', response.data)
            self.assertIn('refresh_token', response.data)
        self.assertEqual(self.login(username='reader', password='wrong').status_code, 401)
        self.assertEqual(self.login(username='reader').status_code, 400)
        self.assertEqual(self.login(username=['reader'], password=self.password).status_code, 400)
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.login(username='reader', password=self.password).status_code, 401)

    @override_settings(USER_AUTH_THROTTLE_RATES={'login_ip': '2/min', 'login_identity': '100/min'})
    def test_legacy_token_endpoint_shares_login_ip_limit(self):
        for endpoints in [('/api/auth/token/',) * 3,
                          ('/api/user/login/', '/api/auth/token/', '/api/user/login/')]:
            with self.subTest(endpoints=endpoints):
                cache.clear()
                responses = [self.client.post(endpoint, {'username': 'reader', 'password': 'wrong'},
                                              format='json') for endpoint in endpoints]
                self.assertEqual([response.status_code for response in responses], [401, 401, 429])
                self.assertIn('Retry-After', responses[-1])

    @override_settings(USER_AUTH_THROTTLE_RATES={'login_ip': '100/min', 'login_identity': '2/min'})
    def test_legacy_token_endpoint_shares_identity_limit_across_ips(self):
        endpoints = ['/api/auth/token/', '/api/user/login/', '/api/auth/token/']
        responses = [self.client.post(endpoint, {'username': 'reader', 'password': 'wrong'},
                                      format='json', REMOTE_ADDR=f'192.0.2.{index}')
                     for index, endpoint in enumerate(endpoints)]
        self.assertEqual([response.status_code for response in responses], [401, 401, 429])
        self.assertIn('Retry-After', responses[-1])

    @override_settings(USER_AUTH_THROTTLE_RATES={'login_ip': '100/min', 'login_identity': '2/min'})
    def test_equivalent_unicode_login_identifiers_share_limit_across_endpoints_and_ips(self):
        for endpoints in [('/api/user/login/',) * 3,
                          ('/api/auth/token/',) * 3,
                          ('/api/user/login/', '/api/auth/token/', '/api/user/login/')]:
            with self.subTest(endpoints=endpoints):
                cache.clear()
                usernames = ['reader', 'ｒｅａｄｅｒ', 'reader']
                responses = [self.client.post(endpoint, {'username': username, 'password': 'wrong'},
                                              format='json', REMOTE_ADDR=f'192.0.2.{index}')
                             for index, (endpoint, username) in enumerate(zip(endpoints, usernames))]
                self.assertEqual([response.status_code for response in responses], [401, 401, 429])

    def test_legacy_token_endpoint_rejects_username_email_collision(self):
        User.objects.create_user(username='reader@example.com', nickname='충돌',
                                 email='unique@example.com', password=self.password)
        for endpoint in ['/api/user/login/', '/api/auth/token/']:
            with self.subTest(endpoint=endpoint):
                response = self.client.post(endpoint, {'username': 'reader@example.com',
                                                       'password': self.password}, format='json')
                self.assertEqual(response.status_code, 401)
                self.assertNotIn('access', response.data)
                self.assertNotIn('access_token', response.data)

    def test_legacy_token_endpoint_uses_login_contract_with_simplejwt_keys(self):
        for identifier in [{'username': 'reader'}, {'username': 'READER@example.com'},
                           {'email': 'reader@example.com'}]:
            with self.subTest(identifier=identifier):
                response = self.client.post('/api/auth/token/', {**identifier, 'password': self.password},
                                            format='json')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(set(response.data), {'access', 'refresh'})
                refresh = RefreshToken(response.data['refresh'])
                self.assertEqual(str(refresh['user_id']), str(self.user.pk))
                self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['access'])
                self.assertEqual(self.client.get('/api/user/me/').status_code, 200)
                self.client.credentials()
                renewed = self.client.post('/api/auth/token/refresh/', {'refresh': response.data['refresh']},
                                           format='json')
                self.assertEqual(renewed.status_code, 200)
                self.assertIn('access', renewed.data)
        self.assertEqual(self.client.post('/api/auth/token/', {'username': 'reader'}, format='json').status_code, 400)
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertEqual(self.client.post('/api/auth/token/', {'username': 'reader', 'password': self.password},
                                          format='json').status_code, 401)

    def test_login_rejects_ambiguous_email_and_username_email_collision(self):
        User.objects.create_user(username='duplicate', nickname='중복', email='READER@example.com', password=self.password)
        self.assertEqual(self.login(username='reader@example.com', password=self.password).status_code, 401)
        User.objects.create_user(username='reader@example.com', nickname='충돌', email='unique@example.com', password=self.password)
        self.assertEqual(self.login(username='reader@example.com', password=self.password).status_code, 401)

    def test_logout_validates_refresh_subject_before_blacklisting(self):
        self.client.force_authenticate(self.user)
        other = User.objects.create_user(username='other', nickname='다른이')
        other_refresh = str(RefreshToken.for_user(other))
        response = self.client.post('/api/user/logout/', {'refresh_token': other_refresh}, format='json')
        self.assertEqual(response.status_code, 403)
        RefreshToken(other_refresh)
        for value in [None, '', [], {}, 'invalid']:
            response = self.client.post('/api/user/logout/', {'refresh_token': value}, format='json')
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post('/api/user/logout/', {}, format='json').status_code, 400)
        own_refresh = str(RefreshToken.for_user(self.user))
        self.assertEqual(self.client.post('/api/user/logout/', {'refresh_token': own_refresh}, format='json').status_code, 200)
        with self.assertRaises(TokenError):
            RefreshToken(own_refresh)
        self.assertEqual(self.client.post('/api/user/logout/', {'refresh_token': own_refresh}, format='json').status_code, 400)

    def test_profile_image_list_can_be_round_tripped_and_is_allowlisted(self):
        images = self.client.get('/api/user/profile-images/').data['profile_images']
        self.assertEqual(len(images), len(User.PROFILE_IMAGE_CHOICES))
        self.assertEqual(images, ['/media/' + value for value, _ in User.PROFILE_IMAGE_CHOICES])
        self.client.force_authenticate(self.user)
        for image in images:
            response = self.client.post('/api/user/update-profile-image/', {'profile_image': image}, format='json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['profile_image'], image)
            self.user.refresh_from_db()
            self.assertIn(self.user.profile_image, dict(User.PROFILE_IMAGE_CHOICES))
        for image in ['../../etc/passwd', 'https://evil.test/profile_image.svg', '', None]:
            self.assertEqual(self.update_profile({'profile_image': image}).status_code, 400)
        self.assertEqual(self.update_profile({'profile_image': User.PROFILE_IMAGE_CHOICES[0][0]}).status_code, 200)
        response = self.signup(profile_image=images[2])
        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.get(username='newreader').profile_image, User.PROFILE_IMAGE_CHOICES[2][0])

    def test_find_id_sends_email_but_never_discloses_account_in_response(self):
        response = self.client.post('/api/user/find-id/', {'email': 'READER@example.com'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {'message'})
        self.assertNotIn('reader', str(response.data))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['reader@example.com'])
        self.assertIn('reader', mail.outbox[0].body)
        unknown = self.client.post('/api/user/find-id/', {'email': 'unknown@example.com'}, format='json')
        self.assertEqual(unknown.data, response.data)
        User.objects.create_user(username='duplicate', nickname='중복', email='READER@example.com')
        ambiguous = self.client.post('/api/user/find-id/', {'email': 'reader@example.com'}, format='json')
        self.assertEqual(ambiguous.data, response.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.post('/api/user/find-id/', {'email': 'invalid'}, format='json').status_code, 400)

    @override_settings(PASSWORD_RESET_URL='https://frontend.example/screen/find-account.html', ALLOWED_HOSTS=['attacker.example', 'testserver'])
    def test_reset_request_emails_only_token_link_and_preserves_password(self):
        response = self.client.post('/api/user/reset-password/', {'email': 'reader@example.com'}, format='json', HTTP_HOST='attacker.example')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {'message'})
        self.assertEqual(len(mail.outbox), 1)
        link = next(line for line in mail.outbox[0].body.splitlines() if line.startswith(('http://', 'https://')))
        self.assertEqual(urlsplit(link).netloc, 'frontend.example')
        data = parse_qs(urlsplit(link).query)
        self.assertEqual(urlsafe_base64_decode(data['uid'][0]).decode(), str(self.user.pk))
        self.assertTrue(default_token_generator.check_token(self.user, data['token'][0]))
        self.assertNotIn(self.password, mail.outbox[0].body)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))
        unknown = self.client.post('/api/user/reset-password/', {'email': 'unknown@example.com'}, format='json')
        self.assertEqual(unknown.data, response.data)
        User.objects.create_user(username='duplicate', nickname='중복', email='READER@example.com')
        self.assertEqual(self.client.post('/api/user/reset-password/', {'email': 'reader@example.com'}, format='json').data, response.data)
        self.assertEqual(len(mail.outbox), 1)

    def reset_payload(self, **overrides):
        data = {'uid': urlsafe_base64_encode(force_bytes(self.user.pk)),
                'token': default_token_generator.make_token(self.user),
                'new_password': 'Cloud-Ocean!9837'}
        data.update(overrides)
        return data

    def confirm_reset(self, **overrides):
        return self.client.post('/api/user/reset-password/', self.reset_payload(**overrides), format='json')

    def test_reset_confirmation_changes_password_once_and_revokes_refresh(self):
        refresh = str(RefreshToken.for_user(self.user))
        payload = self.reset_payload()
        response = self.client.post('/api/user/reset-password/', payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(payload['new_password']))
        with self.assertRaises(TokenError):
            RefreshToken(refresh)
        self.assertEqual(self.client.post('/api/user/reset-password/', payload, format='json').status_code, 400)

    @override_settings(PASSWORD_RESET_TIMEOUT=60)
    def test_reset_rejects_expired_tampered_invalid_and_inactive_tokens(self):
        past = datetime(2020, 1, 1)
        with patch.object(default_token_generator, '_now', return_value=past):
            expired = default_token_generator.make_token(self.user)
        with patch.object(default_token_generator, '_now', return_value=past + timedelta(seconds=61)):
            self.assertEqual(self.confirm_reset(token=expired).status_code, 400)
        for overrides in [{'token': 'invalid'}, {'uid': 'invalid'}, {'new_password': 'x'}, {'new_password': self.password}]:
            self.assertEqual(self.confirm_reset(**overrides).status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))
        payload = self.reset_payload()
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.client.post('/api/user/reset-password/', payload, format='json').status_code, 400)

    @override_settings(USER_AUTH_THROTTLE_RATES={'login_ip': '2/min', 'signup_ip': '2/min', 'recovery_ip': '2/min', 'reset_ip': '2/min', 'user_mutation': '2/min'})
    def test_auth_endpoints_have_explicit_ip_and_user_request_limits(self):
        calls = [
            lambda: self.login(username='missing', password=self.password),
            lambda: self.signup(username='reader'),
            lambda: self.client.post('/api/user/find-id/', {'email': 'unknown@example.com'}, format='json'),
            lambda: self.client.post('/api/user/reset-password/', {'email': 'unknown@example.com'}, format='json'),
            lambda: self.confirm_reset(token='invalid'),
            lambda: self.update_profile({'nickname': '독서인'}),
        ]
        for call in calls:
            cache.clear()
            self.client.force_authenticate(None)
            self.assertNotEqual(call().status_code, 429)
            self.assertNotEqual(call().status_code, 429)
            response = call()
            self.assertEqual(response.status_code, 429)
            self.assertIn('Retry-After', response)

    @override_settings(USER_AUTH_THROTTLE_RATES={'login_identity': '2/min', 'recovery_identity': '2/min', 'reset_identity': '2/min'})
    def test_identifier_limits_survive_ip_rotation_and_recovery_endpoint_switch(self):
        for index in range(3):
            response = self.client.post('/api/user/login/', {'username': 'READER@example.com', 'password': 'wrong'}, format='json', REMOTE_ADDR=f'192.0.2.{index}')
        self.assertEqual(response.status_code, 429)
        cache.clear()
        for index, endpoint in enumerate(['find-id', 'reset-password', 'find-id']):
            response = self.client.post(f'/api/user/{endpoint}/', {'email': 'READER@example.com'}, format='json', REMOTE_ADDR=f'192.0.2.{index}')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(len(mail.outbox), 2)
        cache.clear()
        for index in range(3):
            response = self.client.post('/api/user/reset-password/', self.reset_payload(token='invalid'), format='json', REMOTE_ADDR=f'192.0.2.{index}')
        self.assertEqual(response.status_code, 429)

    @override_settings(DEBUG=False, PASSWORD_RESET_URL='http://frontend.example/screen/find-account.html')
    def test_production_reset_links_require_https_without_enumeration(self):
        with self.assertLogs('user.recovery', level='WARNING'):
            responses = [self.client.post('/api/user/reset-password/', {'email': email}, format='json') for email in ['reader@example.com', 'unknown@example.com']]
        self.assertEqual(responses[0].status_code, 503)
        self.assertEqual(responses[1].status_code, 503)
        self.assertEqual(responses[0].data, responses[1].data)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(USER_AUTH_THROTTLE_RATES={'login_ip': '2/min'})
    def test_spoofed_forwarded_header_cannot_bypass_ip_limit(self):
        for index in range(3):
            response = self.client.post('/api/user/login/', {'username': f'missing{index}', 'password': 'wrong'}, format='json', HTTP_X_FORWARDED_FOR=f'192.0.2.{index}')
        self.assertEqual(response.status_code, 429)

    @override_settings(DEBUG=True, PASSWORD_RESET_URL='http://127.0.0.1:5500/screen/find-account.html')
    def test_development_reset_link_uses_configured_loopback_origin(self):
        response = self.client.post('/api/user/reset-password/', {'email': 'reader@example.com'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('http://127.0.0.1:5500/screen/find-account.html?uid=', mail.outbox[0].body)

    def test_recovery_does_not_send_for_inactive_or_unusable_accounts(self):
        self.user.is_active = False
        self.user.save()
        for endpoint in ['find-id', 'reset-password']:
            response = self.client.post(f'/api/user/{endpoint}/', {'email': self.user.email}, format='json')
            self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.user.is_active = True
        self.user.set_unusable_password()
        self.user.save()
        cache.clear()
        self.assertEqual(self.client.post('/api/user/reset-password/', {'email': self.user.email}, format='json').status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_malformed_reset_requests_do_not_mutate_password(self):
        payloads = [[], {}, {'email': ''}, {'uid': 'MA'}, {'token': 'invalid'}, {'new_password': 'safe'},
                    self.reset_payload(uid=urlsafe_base64_encode(b'9999999999999999999999999999999999')),
                    self.reset_payload(uid=urlsafe_base64_encode(b'999999')),
                    self.reset_payload(uid=urlsafe_base64_encode(b'\xff'))]
        for payload in payloads:
            cache.clear()
            response = self.client.post('/api/user/reset-password/', payload, format='json')
            self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_reset_token_is_bound_to_current_email_and_password(self):
        payload = self.reset_payload()
        self.user.email = 'changed@example.com'
        self.user.save()
        self.assertEqual(self.client.post('/api/user/reset-password/', payload, format='json').status_code, 400)

    def test_logout_rejects_expired_or_access_tokens_and_requires_authentication(self):
        refresh = RefreshToken.for_user(self.user)
        self.assertEqual(self.client.post('/api/user/logout/', {'refresh_token': str(refresh)}, format='json').status_code, 401)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post('/api/user/logout/', {'refresh_token': str(refresh.access_token)}, format='json').status_code, 400)
        refresh.set_exp(lifetime=timedelta(seconds=-1))
        self.assertEqual(self.client.post('/api/user/logout/', {'refresh_token': str(refresh)}, format='json').status_code, 400)

    def test_public_profile_requires_no_authentication_but_me_does(self):
        self.assertEqual(self.client.get('/api/user/me/').status_code, 401)
        self.assertEqual(self.client.get('/api/user/profile/missing/').status_code, 404)

    def test_password_change_policy_uses_updated_profile_attributes(self):
        response = self.update_profile({'email': 'cleverlongidentity@books.test', 'password': 'cleverlongidentity', 'current_password': self.password})
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'reader@example.com')
        self.assertTrue(self.user.check_password(self.password))

    def test_smtp_failure_has_generic_response_and_sanitized_log(self):
        for endpoint in ['find-id', 'reset-password']:
            cache.clear()
            with patch('user.recovery.send_mail', side_effect=SMTPException('private-mailbox-and-token')):
                with self.assertLogs('user.recovery', level='WARNING') as captured:
                    response = self.client.post(f'/api/user/{endpoint}/', {'email': self.user.email}, format='json')
            self.assertEqual(response.status_code, 200)
            unknown = self.client.post(f'/api/user/{endpoint}/', {'email': 'unknown@example.com'}, format='json')
            self.assertEqual(response.data, unknown.data)
            self.assertNotIn('private-mailbox-and-token', ''.join(captured.output))
            self.assertNotIn(self.user.email, ''.join(captured.output))
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.PBKDF2PasswordHasher'])
    def test_signup_authentication_with_real_default_password_hasher(self):
        self.assertEqual(self.signup().status_code, 201)
        user = User.objects.get(username='newreader')
        self.assertTrue(user.password.startswith('pbkdf2_sha256$'))
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(self.login(username='newreader', password=self.password).status_code, 200)

from smtplib import SMTPException
from unittest.mock import patch, Mock
import requests
from django.core.mail import EmailMessage
from django.test import SimpleTestCase, override_settings
from .email_backend import ResendEmailBackend


@override_settings(RESEND_API_KEY='synthetic-not-a-real-key')
class ResendBackendTests(SimpleTestCase):
    def message(self):
        return EmailMessage('Recovery', 'private-reset-link', 'noreply@mail.example', ['reader@example.com'])

    @patch('user.email_backend.requests.post')
    def test_https_delivery_preserves_recovery_body(self, post):
        post.return_value = Mock(status_code=200)
        self.assertEqual(ResendEmailBackend().send_messages([self.message()]), 1)
        args, kwargs = post.call_args
        self.assertEqual(args[0], 'https://api.resend.com/emails')
        self.assertEqual(kwargs['json']['text'], 'private-reset-link')
        self.assertFalse(kwargs['allow_redirects'])
        self.assertIn('Idempotency-Key', kwargs['headers'])

    @patch('user.email_backend.requests.post')
    def test_http_error_and_timeout_are_redacted(self, post):
        for status in (302, 429, 500):
            post.side_effect = None
            post.return_value = Mock(status_code=status)
            with self.assertRaises(SMTPException) as error:
                ResendEmailBackend().send_messages([self.message()])
            self.assertEqual(str(error.exception), 'Mail delivery failed.')
        post.side_effect = requests.Timeout('synthetic-not-a-real-key private-reset-link')
        with self.assertRaises(SMTPException) as error:
            ResendEmailBackend().send_messages([self.message()])
        self.assertEqual(str(error.exception), 'Mail delivery failed.')
        self.assertEqual(ResendEmailBackend(fail_silently=True).send_messages([self.message()]), 0)

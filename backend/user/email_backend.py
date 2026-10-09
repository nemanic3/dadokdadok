"""HTTPS delivery for platforms that block SMTP; never log mail bodies or keys."""
from smtplib import SMTPException
from uuid import uuid4
import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages or []:
            if not message.recipients():
                continue
            try:
                if not settings.RESEND_API_KEY:
                    raise SMTPException('Mail delivery failed.')
                # Recovery is plain text. Do not silently drop unsupported mail parts.
                if message.attachments or getattr(message, 'alternatives', None):
                    raise SMTPException('Unsupported mail format.')
                response = requests.post('https://api.resend.com/emails', headers={
                    'Authorization': f'Bearer {settings.RESEND_API_KEY}',
                    'Idempotency-Key': str(uuid4()),
                }, json={
                    'from': message.from_email, 'to': message.to, 'cc': message.cc,
                    'bcc': message.bcc, 'subject': message.subject, 'text': message.body,
                    'reply_to': message.reply_to,
                }, timeout=(5, 15), allow_redirects=False)
                if response.status_code not in (200, 201):
                    raise SMTPException('Mail delivery failed.')
                sent += 1
            except (requests.RequestException, SMTPException):
                if not self.fail_silently:
                    raise SMTPException('Mail delivery failed.') from None
        return sent

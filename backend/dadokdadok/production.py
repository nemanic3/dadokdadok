"""Cloud production: PostgreSQL, authenticated Pages origin, HTTP email."""
from .settings import *

if DEBUG:
    raise ImproperlyConfigured('Production settings require DJANGO_DEBUG=0.')
if len(ORIGIN_PROXY_SECRET) < 32:
    raise ImproperlyConfigured('ORIGIN_PROXY_SECRET must contain at least 32 characters.')
if not os.environ.get('DATABASE_URL') or DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
    raise ImproperlyConfigured('Production requires PostgreSQL DATABASE_URL; ephemeral SQLite is refused.')
if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
    raise ImproperlyConfigured('Production requires NAVER_CLIENT_ID and NAVER_CLIENT_SECRET.')
if EMAIL_BACKEND != 'user.email_backend.ResendEmailBackend' or not RESEND_API_KEY:
    raise ImproperlyConfigured('Free Render production requires Resend EMAIL_BACKEND and RESEND_API_KEY.')
if DEFAULT_FROM_EMAIL == 'noreply@localhost' or not DEFAULT_FROM_EMAIL:
    raise ImproperlyConfigured('Production requires a verified DEFAULT_FROM_EMAIL.')
if PASSWORD_RESET_URL != 'https://dadok.nemanic.dev/screen/find-account.html':
    raise ImproperlyConfigured('Production recovery must use dadok.nemanic.dev HTTPS.')
CSRF_TRUSTED_ORIGINS = ['https://dadok.nemanic.dev']
# This service does not opt unrelated sibling subdomains into HSTS preload.
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
# Intentional host-only HSTS: do not opt sibling services into preload policies.
SILENCED_SYSTEM_CHECKS = ['security.W005', 'security.W021']
# DB-backed throttle state survives worker restarts and is shared across processes.
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.db.DatabaseCache', 'LOCATION': 'dadok_cache'}}

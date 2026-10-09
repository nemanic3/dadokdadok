import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

import json
from django.core.exceptions import ImproperlyConfigured
DEBUG = os.environ.get('DJANGO_DEBUG', '1').lower() in ('1', 'true', 'yes')
_local = {}
if DEBUG and (BASE_DIR / 'local_credentials.json').exists():
    _local = json.loads((BASE_DIR / 'local_credentials.json').read_text())
def credential(name, required=False):
    value = os.environ.get(name, _local.get(name, ''))
    if required and not value:
        raise ImproperlyConfigured(f'{name} must be explicitly configured.')
    return value
def csv_setting(name, default):
    return [part.strip() for part in os.environ.get(name, default).split(',') if part.strip()]


# ✅ 보안 설정 (SECRET_KEY는 배포 시 반드시 변경)
SECRET_KEY = credential('DJANGO_SECRET_KEY', required=True)

# ✅ 개발 환경 설정 (배포 시 반드시 False)


# ✅ 모든 호스트에서 접근 가능 (배포 시 특정 도메인만 허용)
ALLOWED_HOSTS = csv_setting('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost,[::1]' if DEBUG else '')
if not DEBUG and (not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS):
    raise ImproperlyConfigured('Production requires explicit non-wildcard DJANGO_ALLOWED_HOSTS.')

# ✅ INSTALLED_APPS 설정
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'user',
    'book',
    'review',
    'goal',
    'recommendation',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist'
]

MIDDLEWARE = [
    'dadokdadok.proxy.PagesProxyMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ✅ CORS 설정 (배포 시 특정 도메인만 허용)
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = csv_setting('DJANGO_CORS_ALLOWED_ORIGINS', 'http://127.0.0.1:5500,http://localhost:5500' if DEBUG else '')

ROOT_URLCONF = 'dadokdadok.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'dadokdadok.wsgi.application'

# ✅ 데이터베이스 설정 (기본 SQLite 사용)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DJANGO_DB_PATH', str(BASE_DIR / 'db.sqlite3')),
    }
}
if os.environ.get('DATABASE_URL'):
    from .database import postgres_database
    DATABASES = {'default': postgres_database(os.environ['DATABASE_URL'], require_tls=not DEBUG)}

# ✅ 비밀번호 검증 설정
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ✅ 언어 및 시간대 설정
LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_I18N = True
USE_TZ = True

# ✅ Static & Media 파일 설정
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").is_dir() else []
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ✅ 사용자 모델 설정
AUTH_USER_MODEL = 'user.CustomUser'

# ✅ REST Framework 기본 설정
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',  # ✅ 기본 권한 변경
    ],
    'DEFAULT_THROTTLE_RATES': {'auth': '20/minute', 'recovery': '5/hour', 'book': '60/minute'},
}

# ✅ JWT 설정 (토큰 만료 시간 조절 가능)
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),  # 🚨 필요에 따라 조정 가능 (예: 30분으로 변경)
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": credential('JWT_SIGNING_KEY', required=not DEBUG) or SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ✅ 로그인 및 로그아웃 리디렉션 설정
LOGIN_URL = '/user/login/'
LOGOUT_REDIRECT_URL = '/'

# 네이버 자격정보: 환경변수 / 비추적 개발 로컬 파일
NAVER_CLIENT_ID = credential('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = credential('NAVER_CLIENT_SECRET')
NAVER_BOOKS_API_URL = "https://openapi.naver.com/v1/search/book.json"
BOOK_SEARCH_PROVIDER = os.environ.get('BOOK_SEARCH_PROVIDER', 'naver').strip()
KAKAO_REST_API_KEY = credential('KAKAO_REST_API_KEY')
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend' if DEBUG else '').strip()
# Explicit production delivery backends only; free Render uses HTTPS Resend.
# Console/file/dummy/locmem must never receive live recovery credentials.
if not DEBUG and EMAIL_BACKEND not in ('django.core.mail.backends.smtp.EmailBackend', 'user.email_backend.ResendEmailBackend'):
    raise ImproperlyConfigured('Production requires explicit SMTP or Resend delivery EMAIL_BACKEND.')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', '1').lower() in ('1', 'true', 'yes')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@localhost')
PASSWORD_RESET_URL = os.environ.get('PASSWORD_RESET_URL', 'http://127.0.0.1:5500/screen/find-account.html')
PASSWORD_RESET_TIMEOUT = 3600
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
ORIGIN_PROXY_SECRET = os.environ.get('ORIGIN_PROXY_SECRET', '')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')

import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# ✅ 보안 설정 (SECRET_KEY는 배포 시 반드시 변경)
SECRET_KEY = 'django-insecure-8pv46p(-rc3hi%-7k21p-^x(k!5s2f6wen-lip92(4ei4o7$f('  # 🚨 배포 시 변경 필수

# ✅ 개발 환경 설정 (배포 시 반드시 False)
DEBUG = True  # 🚨 배포 시 False로 변경

# ✅ 모든 호스트에서 접근 가능 (배포 시 특정 도메인만 허용)
ALLOWED_HOSTS = ['*']  # 🚨 배포 시 ["yourdomain.com"]으로 변경

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
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ✅ CORS 설정 (배포 시 특정 도메인만 허용)
CORS_ALLOW_ALL_ORIGINS = True  # 🚨 배포 시 False로 변경
CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:5500",
]

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
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

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
STATICFILES_DIRS = [BASE_DIR / "static"]
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
    ]
}

# ✅ JWT 설정 (토큰 만료 시간 조절 가능)
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),  # 🚨 필요에 따라 조정 가능 (예: 30분으로 변경)
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ✅ 로그인 및 로그아웃 리디렉션 설정
LOGIN_URL = '/user/login/'
LOGOUT_REDIRECT_URL = '/'

# ✅ 네이버 API 설정 (하드코딩된 값 유지)
NAVER_CLIENT_ID = "XuZkPyhdBVtFtXAvM4x9"
NAVER_CLIENT_SECRET = "qc9LqfIhrj"
NAVER_BOOKS_API_URL = "https://openapi.naver.com/v1/search/book.json"
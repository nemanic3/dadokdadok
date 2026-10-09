from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from review.views import LikeReviewView
from user.views import home, LegacyTokenLoginView
from .health import health

urlpatterns = [
    path('api/health/', health, name='health'),
    path('admin/', admin.site.urls),

    # ✅ JWT 로그인 (토큰 발급 및 갱신)
    path('api/auth/token/', LegacyTokenLoginView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # ✅ API 엔드포인트 통일
    path('api/user/', include('user.urls')),
    path('api/book/', include('book.urls')),
    path('api/review/', include('review.urls')),
    path('api/goal/', include('goal.urls')),
    path('api/recommendation/', include('recommendation.urls')),

    # ✅ 리뷰 좋아요 기능 추가
    path('api/review/<int:review_id>/like/', LikeReviewView.as_view(), name='like_review'),

    # ✅ API 상태 확인 엔드포인트 (이 뷰 함수가 실제로 존재하는지 확인 필요)
    path('', home, name='home'),
]

# Existing stored profile_images/ values map to the singular on-disk folder.
# Development only; production must serve media separately.
from django.conf import settings
from django.conf.urls.static import static
from pathlib import Path
urlpatterns += static('/media/profile_images/', document_root=Path(settings.MEDIA_ROOT) / 'profile_image')
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


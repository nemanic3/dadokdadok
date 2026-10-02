from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from review.views import LikeReviewView
from user.views import home  # ⚠️ `home` 뷰 함수가 `user/views.py`에 있는지 확인 필요

urlpatterns = [
    path('admin/', admin.site.urls),

    # ✅ JWT 로그인 (토큰 발급 및 갱신)
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
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


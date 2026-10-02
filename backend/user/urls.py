from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, SignupView, LoginView, LogoutView, ProfileImageListView, UpdateProfileImageView, UserProfileView

# ✅ ViewSet을 라우터에 등록 (Prefix 제거)
router = DefaultRouter()
router.register('', UserViewSet, basename='user')

urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),  # ✅ 회원가입 (POST)
    path('login/', LoginView.as_view(), name='login'),  # ✅ 로그인 (POST, JWT 발급)
    path('logout/', LogoutView.as_view(), name='logout'),  # ✅ 로그아웃 (POST)
    path('', include(router.urls)),  # ✅ ViewSet 포함 (me/, update_profile/, delete/ 포함됨)
    path('profile-images/', ProfileImageListView.as_view(), name='profile_images'),
    path('update-profile-image/', UpdateProfileImageView.as_view(), name='update_profile_image'),
    path('profile/<str:nickname>/', UserProfileView.as_view(), name='user_profile')
]

# access token 갱신: api/auth/token/refresh/
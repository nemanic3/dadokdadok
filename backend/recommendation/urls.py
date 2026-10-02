from django.urls import path
from .views import NaverRecommendationView

urlpatterns = [
    path('naver/', NaverRecommendationView.as_view(), name='naver_recommendation'),  # ✅ 네이버 API 기반 추천 기능
]
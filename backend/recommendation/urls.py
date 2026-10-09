from django.urls import path
from .views import NaverRecommendationView, PersonalizedRecommendationView

urlpatterns = [
    path('personalized/', PersonalizedRecommendationView.as_view(), name='personalized_recommendation'),
    path('naver/', NaverRecommendationView.as_view(), name='naver_recommendation'),  # ✅ 네이버 API 기반 추천 기능
]
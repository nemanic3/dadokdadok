from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GoalViewSet, GoalProgressView, MonthlyReadingProgressView

router = DefaultRouter()
router.register('', GoalViewSet, basename='goal')  # ✅ '/api/goal/'로 등록

urlpatterns = [
    path('goal/', include(router.urls)),  # ✅ `/api/goal/`에서 GoalViewSet 사용 가능
    path('progress/', GoalProgressView.as_view(), name='goal_progress'),  # ✅ 목표 진행률 조회 (그래프용)
    path('monthly-progress/', MonthlyReadingProgressView.as_view(), name='monthly_goal_progress'),  # ✅ 월별 독서량 조회 (그래프용)
]
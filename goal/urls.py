from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GoalViewSet

router = DefaultRouter()
router.register('', GoalViewSet, basename='goal')

urlpatterns = [
    path('', include(router.urls)),  # /goal/에서 동작
]
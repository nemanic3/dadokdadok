from django.contrib import admin
from django.urls import path, include
from .views import home  # home 뷰 가져오기

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),  # 빈 경로에 대한 URL 연결
    path('goal/', include('goal.urls')),  # Goal 앱 URL
    path('recommendation/', include('recommendation.urls')),  # Recommendation 앱 URL
]
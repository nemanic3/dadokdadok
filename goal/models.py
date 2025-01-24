from django.conf import settings  # 사용자 모델 가져오기
from django.db import models

class Goal(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='goals')  # 수정된 부분
    goal_count = models.IntegerField()
    progress = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Goal: {self.goal_count} books"
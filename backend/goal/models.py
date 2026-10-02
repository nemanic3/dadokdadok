from django.db import models
from django.conf import settings

class Goal(models.Model):
    """ 연간 독서 목표 모델 (텍스트 정보 제거) """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    total_books = models.IntegerField(default=0)  # ✅ 목표 책 수
    read_books = models.IntegerField(default=0)  # ✅ 현재까지 읽은 책 개수
    is_completed = models.BooleanField(default=False)

    class Meta:
        db_table = 'goal'

    def __str__(self):
        return f"{self.user.nickname} - 목표 {self.total_books}권"
import datetime
from django.db import models
from django.conf import settings

class Goal(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateField(default=datetime.date.today)  # 기본값: 오늘 날짜
    end_date = models.DateField(default=datetime.date.today)  # 기본값: 오늘 날짜
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return self.title
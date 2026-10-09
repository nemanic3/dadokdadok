from django.db import models
from django.conf import settings

class Goal(models.Model):
    """Explicit annual/monthly targets; NULL periods preserve legacy ambiguity."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    total_books = models.IntegerField(default=0)  # ✅ 목표 책 수
    read_books = models.IntegerField(default=0)  # Retained legacy storage, not API progress.
    is_completed = models.BooleanField(default=False)
    # Unknown legacy periods remain NULL; never backfill them to the current year.
    year = models.IntegerField(null=True, blank=True)
    month = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'goal'
        constraints = [
            models.UniqueConstraint(fields=['user', 'year'],
                                    condition=models.Q(year__isnull=False, month__isnull=True),
                                    name='unique_goal_annual_period'),
            models.UniqueConstraint(fields=['user', 'year', 'month'],
                                    condition=models.Q(year__isnull=False, month__isnull=False),
                                    name='unique_goal_monthly_period'),
        ]

    def __str__(self):
        return f"{self.user.nickname} - 목표 {self.total_books}권"
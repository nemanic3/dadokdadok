from django.db import models
from django.conf import settings

class Recommendation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    book_title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, default="Unknown Author")
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
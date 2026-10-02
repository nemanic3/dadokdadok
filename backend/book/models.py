from django.db import models

class Book(models.Model):
    """ 책 모델 """
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, null=True, blank=True)
    published_date = models.CharField(max_length=20, null=True, blank=True)
    isbn = models.CharField(max_length=13, unique=True, null=True, blank=True)
    publisher = models.CharField(max_length=255, null=True, blank=True)
    image_url = models.URLField(null=True, blank=True)
    link = models.URLField(null=True, blank=True)  # ✅ 링크 필드 추가
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "book"

    def __str__(self):
        return f"{self.title} ({self.author})"
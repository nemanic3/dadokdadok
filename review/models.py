from django.conf import settings  # 사용자 모델 가져오기
from django.db import models

class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')  # 수정된 부분
    book_id = models.IntegerField()  # 책 ID
    content = models.TextField()  # 리뷰 내용
    rating = models.FloatField()  # 평점
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.user.username} on Book {self.book_id}"
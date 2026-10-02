from rest_framework import serializers
from .models import Book
from review.models import Review

class BookSerializer(serializers.ModelSerializer):
    """ DB에 저장된 책 정보를 직렬화 """
    class Meta:
        model = Book
        fields = ['id', 'title', 'author', 'published_date', 'isbn', 'publisher', 'image_url', 'link', 'created_at']

class NaverBookSerializer(serializers.Serializer):
    """ 네이버 API 검색 결과 직렬화 """
    title = serializers.CharField(required=False)
    author = serializers.CharField(required=False)
    publisher = serializers.CharField(required=False)
    pubdate = serializers.CharField(required=False)
    isbn = serializers.CharField(required=False)
    image_url = serializers.URLField(required=False, source="image")
    link = serializers.URLField(required=False)

    def to_representation(self, instance):
        """ 네이버 API의 응답 필드를 프로젝트의 필드명과 맞추어 변환 """
        return {
            "title": instance.get("title", "제목 없음"),
            "author": instance.get("author", "저자 미상"),
            "publisher": instance.get("publisher", "출판사 정보 없음"),
            "published_date": instance.get("pubdate", "출판일 정보 없음"),
            "isbn": instance.get("isbn", "ISBN 정보 없음"),
            "image_url": instance.get("image", ""),
            "link": instance.get("link", ""),
        }

class BookWithReviewSerializer(serializers.ModelSerializer):
    """ 최신 리뷰 포함된 책 정보 직렬화 """
    reviews = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = ['id', 'title', 'author', 'published_date', 'isbn', 'publisher', 'image_url', 'created_at', 'reviews']

    def get_reviews(self, obj):
        """ 최신 5개의 리뷰를 가져와 정리 """
        reviews = Review.objects.filter(book=obj).order_by('-created_at')[:5]
        return [
            {
                "id": review.id,
                "user": review.user.username,
                "rating": review.rating,
                "content": review.content,
                "created_at": review.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
            for review in reviews
        ]
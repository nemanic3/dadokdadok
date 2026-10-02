from rest_framework import serializers
from .models import Review, Like, Comment
from book.models import Book


class ReviewSerializer(serializers.ModelSerializer):
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    user_nickname = serializers.CharField(source="user.nickname", read_only=True)
    isbn = serializers.SerializerMethodField()  # ✅ 입력값에서 제거하고 응답에 포함

    class Meta:
        model = Review
        fields = [
            'id',
            'user_nickname',
            'isbn',
            'content',
            'rating',
            'created_at',
            'updated_at',
            'likes_count',
            'comments_count'
        ]

    def get_isbn(self, obj):
        """ 해당 리뷰가 속한 책의 ISBN을 반환 """
        return obj.book.isbn if obj.book else None

    def create(self, validated_data):
        """ 리뷰 생성 시 중복 확인 후 저장 """
        user = validated_data.pop("user")
        book = validated_data.pop("book")

        # ✅ 같은 유저가 같은 책에 대한 리뷰가 있는지 확인
        if Review.objects.filter(user=user, book=book).exists():
            raise serializers.ValidationError({"detail": "이미 해당 책에 대한 리뷰를 작성하셨습니다."})

        review = Review.objects.create(user=user, book=book, **validated_data)
        return review

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_comments_count(self, obj):
        return obj.comments.count()


class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Like
        fields = ['id', 'user', 'review']


class CommentSerializer(serializers.ModelSerializer):
    user_nickname = serializers.CharField(source="user.nickname", read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'user', 'user_nickname', 'review', 'content', 'created_at', 'updated_at']
        extra_kwargs = {'user': {'required': False}}  # ✅ 요청에서 `user` 입력을 요구하지 않도록 설정

    def create(self, validated_data):
        """ 댓글 생성 시 유저 정보를 자동으로 설정 """
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["user"] = request.user  # ✅ `user` 자동 설정
        else:
            raise serializers.ValidationError({"user": "인증된 사용자가 필요합니다."})

        return super().create(validated_data)



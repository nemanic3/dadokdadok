import math

from django.db import IntegrityError, transaction
from dadokdadok.constraints import is_unique_conflict
from rest_framework import serializers
from .models import Review, Like, Comment
from book.models import Book
from user.profile_images import PublicProfileImageField


class ContentField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


class RatingField(serializers.FloatField):
    def to_internal_value(self, data):
        if isinstance(data, bool):
            self.fail('invalid')
        value = super().to_internal_value(data)
        if not math.isfinite(value):
            self.fail('invalid')
        return value


class ReviewSerializer(serializers.ModelSerializer):
    content = ContentField()
    rating = RatingField(min_value=0, max_value=5)
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    user_nickname = serializers.CharField(source="user.nickname", read_only=True)
    profile_image = PublicProfileImageField(source='user.profile_image')
    isbn = serializers.SerializerMethodField()  # ✅ 입력값에서 제거하고 응답에 포함

    class Meta:
        model = Review
        fields = [
            'id',
            'user_nickname',
            'profile_image',
            'isbn',
            'content',
            'rating',
            'created_at',
            'updated_at',
            'likes_count',
            'comments_count'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # 과거 nullable 레코드는 응답만 보정하고 저장 데이터는 변경하지 않는다.
        if data['content'] is None:
            data['content'] = ''
        if data['rating'] is None:
            data['rating'] = 0.0
        return data

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

        try:
            with transaction.atomic():
                return Review.objects.create(user=user, book=book, **validated_data)
        except IntegrityError as exc:
            if (not is_unique_conflict(exc, 'review', ('user_id', 'book_id'))
                    or not Review.objects.filter(user=user, book=book).exists()):
                raise
            raise serializers.ValidationError({"detail": "이미 해당 책에 대한 리뷰를 작성하셨습니다."}) from exc

    def get_likes_count(self, obj):
        if hasattr(obj, 'like_total'):
            return obj.like_total
        return obj.likes.count()

    def get_comments_count(self, obj):
        if hasattr(obj, 'comment_total'):
            return obj.comment_total
        return obj.comments.count()


class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Like
        fields = ['id', 'user', 'review']


class CommentSerializer(serializers.ModelSerializer):
    content = ContentField()
    user_nickname = serializers.CharField(source="user.nickname", read_only=True)
    profile_image = PublicProfileImageField(source='user.profile_image')

    class Meta:
        model = Comment
        fields = ['id', 'user', 'user_nickname', 'profile_image', 'review', 'content', 'created_at', 'updated_at']
        read_only_fields = ['user', 'review']

    def create(self, validated_data):
        """ 댓글 생성 시 유저 정보를 자동으로 설정 """
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["user"] = request.user  # ✅ `user` 자동 설정
        else:
            raise serializers.ValidationError({"user": "인증된 사용자가 필요합니다."})

        return super().create(validated_data)



from collections.abc import Mapping

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db import IntegrityError, transaction
from django.db.models import Count, OuterRef, Subquery
from .models import Review, Like, Comment
from .permissions import IsReviewOwner
from book.models import Book
from .serializers import ReviewSerializer, LikeSerializer, CommentSerializer
from book.services import get_book_by_isbn_from_naver
from book.throttles import BookThrottle
from django.conf import settings


class ReviewViewSet(viewsets.ModelViewSet):
    """ 리뷰 CRUD 기능 제공 """
    queryset = Review.objects.select_related('user', 'book').annotate(
        like_total=Count('likes', distinct=True), comment_total=Count('comments', distinct=True)
    )
    serializer_class = ReviewSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated(), IsReviewOwner()]

    def perform_create(self, serializer):
        """ 리뷰 작성 시 `isbn`을 받아서 책을 조회/생성 후 리뷰 저장 """
        isbn = self.request.data.get("isbn")
        if not isbn:
            raise ValidationError({"isbn": "ISBN이 필요합니다."})

        book = Book.objects.filter(isbn=isbn).first()

        if not book:
            # Charge only the upstream import, not local review CRUD.
            throttle = BookThrottle()
            if not throttle.allow_request(self.request, self):
                self.throttled(self.request, throttle.wait())
            book_data = get_book_by_isbn_from_naver(isbn)
            if not book_data:
                raise ValidationError({"isbn": "해당 ISBN으로 책 정보를 찾을 수 없습니다."})

            try:
                with transaction.atomic():
                    book = Book.objects.create(
                        isbn=isbn,
                        title=book_data.get("title", "Unknown Title"),
                        author=book_data.get("author", "Unknown Author"),
                        publisher=book_data.get("publisher", "Unknown Publisher"),
                        published_date=book_data.get("pubdate", ""),
                        image_url=book_data.get("image", ""),
                        link=book_data.get("link", ""),
                    )
            except IntegrityError as exc:
                # Only the existing SQLite ISBN constraint is recoverable.
                if str(exc) != 'UNIQUE constraint failed: book.isbn':
                    raise
                book = Book.objects.filter(isbn=isbn).first()
                if book is None:
                    raise

        serializer.save(user=self.request.user, book=book)

    def destroy(self, request, *args, **kwargs):
        """ 리뷰 삭제 후 메시지 반환 """
        review = self.get_object()

        # ✅ 삭제 실행
        self.perform_destroy(review)

        # ✅ 삭제 성공 메시지 반환
        return Response({"message": "Review successfully deleted."}, status=status.HTTP_200_OK)


class LikeReviewView(APIView):
    """ 리뷰 좋아요 기능 """
    permission_classes = [IsAuthenticated]

    def post(self, request, review_id):
        review = get_object_or_404(Review, id=review_id)

        like, created = Like.objects.get_or_create(user=request.user, review=review)

        if not created:
            like.delete()
            return Response({"message": "Like removed", "likes_count": review.likes.count()}, status=status.HTTP_200_OK)

        return Response({"message": "Like added", "likes_count": review.likes.count()}, status=status.HTTP_201_CREATED)


class LikedReviewsView(APIView):
    """현재 사용자의 좋아요 초기 상태 조회."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        likes = Like.objects.filter(user=request.user).order_by('id').values('review_id')
        return Response(list(likes), status=status.HTTP_200_OK)


class CommentView(APIView):
    """ 댓글 작성 기능 """
    permission_classes = [IsAuthenticated]

    def post(self, request, review_id):
        review = get_object_or_404(Review, id=review_id)  # ✅ `get_object_or_404()` 사용하여 자동 404 반환

        if not isinstance(request.data, Mapping):
            raise ValidationError({'detail': 'JSON 객체가 필요합니다.'})
        content = request.data.get("content")
        if content is None or (isinstance(content, str) and not content.strip()):
            return Response({"error": "댓글 내용을 입력해주세요."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CommentSerializer(data={"review": review.id, "content": content}, context={"request": request})
        if serializer.is_valid():
            serializer.save(review=review)  # user/review는 서버에서만 지정
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get_owned_comment(self, request, review_id, comment_id=None):
        if comment_id is None:
            if not isinstance(request.data, Mapping):
                raise ValidationError({'detail': 'JSON 객체가 필요합니다.'})
            comment_id = request.data.get('comment_id')
            if not (type(comment_id) is int or
                    (isinstance(comment_id, str) and comment_id.isascii() and comment_id.isdecimal())):
                raise ValidationError({'comment_id': '양의 정수 댓글 ID가 필요합니다.'})
            if len(str(comment_id)) > 19 or not 0 < int(comment_id) <= 9223372036854775807:
                raise ValidationError({'comment_id': '유효한 댓글 ID가 필요합니다.'})
        comment = get_object_or_404(Comment, pk=comment_id, review_id=review_id)
        if comment.user_id != request.user.pk:
            raise PermissionDenied('댓글 작성자만 수정하거나 삭제할 수 있습니다.')
        return comment

    def put(self, request, review_id, comment_id=None):
        comment = self.get_owned_comment(request, review_id, comment_id)
        serializer = CommentSerializer(comment, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, review_id, comment_id=None):
        return self.put(request, review_id, comment_id)

    def delete(self, request, review_id, comment_id=None):
        comment = self.get_owned_comment(request, review_id, comment_id)
        comment.delete()
        return Response({'message': 'Comment successfully deleted.'}, status=status.HTTP_200_OK)


class CommentDetailView(CommentView):
    """기존 body 기반 API와 같은 권한 검사를 사용하는 중첩 별칭."""
    http_method_names = ['put', 'patch', 'delete', 'options']


class CommentListView(APIView):
    """ 특정 리뷰의 댓글 목록 조회 기능 """
    permission_classes = [AllowAny]

    def get(self, request, review_id):
        comments = Comment.objects.filter(review_id=review_id).select_related('user').order_by('-created_at', '-pk')
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RecentReviewView(APIView):
    """ 최신 리뷰 도서 목록 조회 (메인 페이지) """
    permission_classes = [AllowAny]

    def get(self, request):
        latest_for_book = Review.objects.filter(book_id=OuterRef('book_id')).order_by('-created_at', '-pk')
        recent_reviews = (Review.objects.filter(pk=Subquery(latest_for_book.values('pk')[:1]))
                          .select_related('book').order_by('-created_at', '-pk')[:6])
        unique_books = [review.book for review in recent_reviews]

        data = [
            {
                "title": book.title,
                "isbn": book.isbn,  # ✅ `isbn` 추가
                "image_url": book.image_url
            }
            for book in unique_books
        ]
        return Response(data, status=status.HTTP_200_OK)



class MyLibraryView(APIView):
    """ 내가 작성한 리뷰 목록 조회 (내 서재) """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # user+book 유일성이 보장되므로 이미 조회한 본인 리뷰를 그대로 사용한다.
        user_reviews = Review.objects.filter(user=request.user).select_related('book').order_by('-created_at', '-pk')
        data = [
            {
                "title": review.book.title,
                "isbn": review.book.isbn,
                "author": review.book.author,
                "image_url": review.book.image_url,
                "rating": round(review.rating if review.rating is not None else 0.0, 2),
                "short_review": (review.content or '')[:50],
            }
            for review in user_reviews
        ]
        return Response(data, status=status.HTTP_200_OK)



class BookReviewsView(APIView):
    """ 특정 책의 최신 리뷰 목록 조회 """
    permission_classes = [AllowAny]

    def get(self, request, isbn):
        book = Book.objects.filter(isbn=isbn).first()  # ✅ ISBN으로 책 조회
        if not book:
            # 네이버에서 조회한 새 도서는 아직 로컬 DB에 없어도 정상 빈 목록이다.
            return Response([], status=status.HTTP_200_OK)

        reviews = Review.objects.filter(book=book).select_related('user').order_by('-created_at', '-pk')
        data = [
            {
                "review_id": review.id,  # ✅ 추가된 부분
                "user": review.user.nickname,
                "rating": review.rating if review.rating is not None else 0.0,
                "content": (review.content or "")[:50],
                "created_at": review.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
            for review in reviews
        ]
        return Response(data, status=status.HTTP_200_OK)


class StarIconsView(APIView):
    """별 이미지 URL 반환"""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "empty": f"{settings.MEDIA_URL}icons/star_empty.svg",
            "half": f"{settings.MEDIA_URL}icons/star_half.svg",
            "full": f"{settings.MEDIA_URL}icons/star_full.svg",
            "review": f"{settings.MEDIA_URL}icons/review_star.svg"
        })


class HeartIconsView(APIView):
    """ 좋아요(하트) 이미지 URL 반환 """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "empty": f"{settings.MEDIA_URL}icons/heart_empty.svg",
            "full": f"{settings.MEDIA_URL}icons/heart_full.svg"
        })


class IconsView(APIView):
    """공통 아이콘 이미지 URL 반환"""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "arrow": f"{settings.MEDIA_URL}icons/arrow_seeall.svg",
            "edit": f"{settings.MEDIA_URL}icons/edit_emoji.svg"
        })

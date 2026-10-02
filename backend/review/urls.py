from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    ReviewViewSet, LikeReviewView, CommentView, CommentListView,
    RecentReviewView, MyLibraryView, BookReviewsView, StarIconsView, HeartIconsView, IconsView
)

router = DefaultRouter()
router.register('', ReviewViewSet, basename='review')

urlpatterns = [
    path('<int:review_id>/like/', LikeReviewView.as_view(), name='like_review'),
    path('<int:review_id>/comments/', CommentView.as_view(), name='comment_review'),
    path('<int:review_id>/comments/list/', CommentListView.as_view(), name='list_comments'),

    # ✅ 메인 페이지 - 최신 리뷰 도서 목록
    path('recent-reviews/', RecentReviewView.as_view(), name='recent_reviews'),

    # ✅ 내 서재 - 내가 쓴 리뷰 목록
    path('library/', MyLibraryView.as_view(), name='my_library'),

    # ✅ 특정 책의 최신 리뷰 목록
    path('library/<str:isbn>/', BookReviewsView.as_view(), name='book_reviews'),

    # ✅ 별점 이미지 URL 제공
    path('stars/', StarIconsView.as_view(), name='star_icons'),

    path('hearts/', HeartIconsView.as_view(), name='heart_icons'),  # ❤️ 좋아요(하트) 아이콘

    path('icons/', IconsView.as_view(), name='icons')
]

urlpatterns += router.urls

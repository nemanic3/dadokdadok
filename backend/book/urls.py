from django.urls import path
from .views import SearchBookView, GetBookByISBNView, RecentReviewView

urlpatterns = [
    path('search/', SearchBookView.as_view(), name='search_book'),
    path('isbn/<str:isbn>/', GetBookByISBNView.as_view(), name='get_book_by_isbn'),
    path('recent-reviews/', RecentReviewView.as_view(), name='recent_reviews'),
]
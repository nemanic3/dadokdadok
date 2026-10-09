from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from book.services import NaverAPIError
from book.identifiers import validate_isbn
from book.parameters import bounded_integer
from .services import get_book_recommendations, get_personalized_recommendations
from .throttles import BookThrottle


class NaverRecommendationView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [BookThrottle]

    def get(self, request):
        isbn = request.GET.get('isbn')
        query = request.GET.get('query')
        display = bounded_integer(request.GET.get('display', 5), 'display', 1, 100)
        if isbn is not None:
            validate_isbn(isbn)
        query = (query or '').strip()
        if len(query) > 200:
            return Response({'error': '검색어는 200자 이하여야 합니다.'}, status=400)
        if not isbn and not query:
            return Response({'error': 'ISBN 또는 검색어를 입력하세요.'}, status=400)
        try:
            return Response(get_book_recommendations(isbn=isbn, query=query, display=display))
        except NaverAPIError as error:
            return Response({'error': str(error.detail)}, status=error.status_code)


class PersonalizedRecommendationView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [BookThrottle]

    def get(self, request):
        display = bounded_integer(request.GET.get('display', 5), 'display', 1, 100)
        isbn = request.GET.get('isbn')
        if isbn is not None:
            validate_isbn(isbn)
        return Response(get_personalized_recommendations(request.user, isbn=isbn, display=display))

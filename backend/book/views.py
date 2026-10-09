from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import BookSerializer, NaverBookSerializer, BookWithReviewSerializer
from .models import Book
from review.models import Review
from .identifiers import validate_isbn
from .services import search_books_from_naver, get_book_by_isbn_from_naver, NaverAPIError
from .throttles import BookThrottle

class SearchBookView(APIView):
    """ 네이버 API를 이용한 도서 검색 API """
    permission_classes = [AllowAny]
    throttle_classes = [BookThrottle]

    def get(self, request):
        from .parameters import bounded_integer
        query = request.GET.get('query') or request.GET.get('q', '')
        query = query.strip()
        display = bounded_integer(request.GET.get('display', 10), 'display', 1, 100)
        start = bounded_integer(request.GET.get('start', 1), 'start', 1, 1000)
        if len(query) > 200:
            return Response({'error': '검색어는 200자 이하여야 합니다.'}, status=400)
        if not query:
            return Response({"error": "검색어를 입력하세요."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = search_books_from_naver(query, display=display, start=start)
            if isinstance(data, list):
                serialized_data = NaverBookSerializer(data, many=True).data
                return Response(serialized_data, status=status.HTTP_200_OK, headers={
                    "X-Total-Count": str(getattr(data, "total", len(data))),
                    "X-Page-Start": str(start), "X-Page-Size": str(display),
                })
            return Response({"error": "네이버 API에서 데이터를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        except NaverAPIError as error:
            return Response({'error': str(error.detail)}, status=error.status_code)
        except Exception:
            return Response({'error': '도서 정보를 처리하지 못했습니다.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetBookByISBNView(APIView):
    """ ISBN을 이용한 개별 도서 조회 API """
    permission_classes = [AllowAny]
    throttle_classes = [BookThrottle]

    def get(self, request, isbn):
        validate_isbn(isbn)
        try:
            book = Book.objects.filter(isbn=isbn).first()
            if book:
                return Response(BookSerializer(book).data, status=status.HTTP_200_OK)

            data = get_book_by_isbn_from_naver(isbn)
            if data:
                serialized_data = NaverBookSerializer(data).data
                return Response(serialized_data, status=status.HTTP_200_OK)

            # ❌ 기존 코드: data가 None일 경우 예외 발생 가능
            # return Response(NaverBookSerializer(data).data, status=status.HTTP_200_OK)

            return Response({"error": "책을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)  # ✅ 예외 방지
        except NaverAPIError as error:
            return Response({'error': str(error.detail)}, status=error.status_code)
        except Exception:
            return Response({'error': '도서 정보를 처리하지 못했습니다.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RecentReviewView(APIView):
    """ 최근 리뷰된 도서 목록 조회 API """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            from django.db.models import Prefetch
            recent_reviews = Review.objects.order_by('-created_at', '-pk').values_list('book_id', 'book__isbn')
            book_ids, seen = [], set()
            for book_id, isbn in recent_reviews.iterator(chunk_size=200):
                identity = isbn or ('book', book_id)
                if identity in seen:
                    continue
                seen.add(identity)
                book_ids.append(book_id)
                if len(book_ids) == 10:
                    break
            latest_reviews = Review.objects.select_related('user').order_by('-created_at', '-pk')[:5]
            by_id = {book.pk: book for book in Book.objects.filter(pk__in=book_ids).prefetch_related(
                Prefetch('reviews', queryset=latest_reviews, to_attr='recent_reviews')
            )}
            books = [by_id[book_id] for book_id in book_ids]
            serialized_books = BookWithReviewSerializer(books, many=True).data
            return Response(serialized_books, status=status.HTTP_200_OK)
        except NaverAPIError as error:
            return Response({'error': str(error.detail)}, status=error.status_code)
        except Exception:
            return Response({'error': '도서 정보를 처리하지 못했습니다.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
import requests
from django.conf import settings
from rest_framework.exceptions import APIException


class NaverAPIError(APIException):
    status_code = 502
    default_detail = '도서 제공 서비스와 통신하지 못했습니다.'
    default_code = 'book_upstream_error'

    def __init__(self, detail=None, status_code=502):
        super().__init__(detail)
        self.status_code = status_code


class SearchResults(list):
    def __init__(self, items, total):
        super().__init__(items)
        self.total = total if type(total) is int and total >= 0 else len(items)


def search_books_from_naver(query, display=10, start=1):
    """Preserve the list contract; propagate safe, bounded upstream failures."""
    headers = {'X-Naver-Client-Id': settings.NAVER_CLIENT_ID,
               'X-Naver-Client-Secret': settings.NAVER_CLIENT_SECRET}
    try:
        response = requests.get(settings.NAVER_BOOKS_API_URL, headers=headers,
                                params={'query': query, 'display': display, 'start': start}, timeout=(3.05, 10))
        response.raise_for_status()
        data = response.json()
    except requests.Timeout as error:
        raise NaverAPIError('도서 검색 응답 시간이 초과되었습니다.', status_code=504) from error
    except (requests.RequestException, ValueError) as error:
        raise NaverAPIError() from error
    if not isinstance(data, dict) or not isinstance(data.get('items'), list):
        raise NaverAPIError('도서 제공 서비스의 응답 형식이 올바르지 않습니다.')
    if not all(isinstance(item, dict) for item in data['items']):
        raise NaverAPIError('도서 제공 서비스의 항목 형식이 올바르지 않습니다.')
    return SearchResults(data['items'], data.get('total'))


def get_book_by_isbn_from_naver(isbn):
    from .identifiers import validate_isbn
    validate_isbn(isbn)
    items = search_books_from_naver(isbn, display=10)
    for item in items:
        if isinstance(item, dict) and isinstance(item.get('isbn'), str) and isbn in item['isbn'].split():
            return {**item, 'isbn': isbn}
    return None

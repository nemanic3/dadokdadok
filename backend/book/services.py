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
    """Legacy entry point retained for callers; production uses Kakao."""
    if settings.BOOK_SEARCH_PROVIDER == 'kakao':
        return search_books_from_kakao(query, display, start)
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


def search_books_from_kakao(query, display=10, start=1, target=None):
    """Translate offset pagination and metadata without changing public API fields."""
    offset = start - 1
    page, skip = divmod(offset, 50)
    items, total = [], 0
    while len(items) < display:
        params = {'query': query, 'page': page + 1, 'size': 50}
        if target:
            params['target'] = target
        try:
            response = requests.get('https://dapi.kakao.com/v3/search/book',
                headers={'Authorization': f'KakaoAK {settings.KAKAO_REST_API_KEY}'},
                params=params, timeout=(3.05, 8), allow_redirects=False)
            if 300 <= response.status_code < 400:
                raise NaverAPIError()
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as error:
            raise NaverAPIError('도서 검색 응답 시간이 초과되었습니다.', status_code=504) from error
        except (requests.RequestException, ValueError) as error:
            raise NaverAPIError() from error
        if not isinstance(data, dict) or not isinstance(data.get('documents'), list) or not isinstance(data.get('meta'), dict):
            raise NaverAPIError('도서 제공 서비스의 응답 형식이 올바르지 않습니다.')
        documents, meta = data['documents'], data['meta']
        if len(documents) > 50 or not all(isinstance(item, dict) for item in documents):
            raise NaverAPIError('도서 제공 서비스의 항목 형식이 올바르지 않습니다.')
        total = meta.get('total_count', total)
        for item in documents[skip:]:
            authors = item.get('authors') or []
            if not isinstance(authors, list) or not all(isinstance(author, str) for author in authors):
                raise NaverAPIError('도서 제공 서비스의 저자 형식이 올바르지 않습니다.')
            items.append({'title': item.get('title') or '', 'author': '^'.join(authors),
                'publisher': item.get('publisher') or '', 'isbn': item.get('isbn') or '',
                'image': item.get('thumbnail') or '', 'link': item.get('url') or '',
                'pubdate': (item.get('datetime') or '')[:10].replace('-', '')})
            if len(items) == display:
                break
        if meta.get('is_end') or len(documents) < 50 or page >= 49:
            break
        page, skip = page + 1, 0
    return SearchResults(items, total)


def get_book_by_isbn_from_naver(isbn):
    from .identifiers import validate_isbn
    validate_isbn(isbn)
    items = (search_books_from_kakao(isbn, display=10, target='isbn')
             if settings.BOOK_SEARCH_PROVIDER == 'kakao' else search_books_from_naver(isbn, display=10))
    for item in items:
        if isinstance(item, dict) and isinstance(item.get('isbn'), str) and isbn in item['isbn'].split():
            return {**item, 'isbn': isbn}
    return None

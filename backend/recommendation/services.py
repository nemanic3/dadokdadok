import requests
from django.conf import settings


def get_book_recommendations(isbn=None, query=None, display=5):
    """
    네이버 API를 사용하여 입력된 ISBN 또는 키워드와 관련된 도서를 추천.
    """
    url = settings.NAVER_BOOKS_API_URL
    headers = {
        "X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": settings.NAVER_CLIENT_SECRET,
    }

    params = {"display": display}

    if isbn:
        clean_isbn = isbn.split(" ")[0]  # ✅ ISBN이 여러 개 포함된 경우 첫 번째 값만 사용
        book_info = get_book_info_by_isbn(clean_isbn, headers)
        if book_info:
            # ✅ ISBN 검색이 실패하면 "출판사 + 저자"로 검색
            search_query = f"{book_info.get('publisher', '')} {book_info.get('author', '')}".strip()
            if search_query:
                params["query"] = search_query
            else:
                return {"error": f"ISBN {clean_isbn}으로 검색된 책이 없습니다."}
        else:
            return {"error": f"ISBN {clean_isbn}으로 검색된 책이 없습니다."}
    elif query:
        params["query"] = query
    else:
        return {"error": "검색어 또는 ISBN을 입력하세요."}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # 네트워크 오류 발생 시 예외 발생

        data = response.json().get("items", [])

        formatted_data = [
            {
                "isbn": book.get("isbn", "ISBN 없음").split(" ")[0],  # ✅ ISBN이 여러 개일 경우 첫 번째 값만 사용
                "title": book["title"],
                "author": book.get("author", "Unknown Author"),
                "publisher": book.get("publisher", "Unknown Publisher"),
                "image": book.get("image", ""),
                "link": book.get("link", ""),
            }
            for book in data
        ]
        return formatted_data
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def get_book_info_by_isbn(isbn, headers):
    """
    ISBN으로 검색하여 책 정보를 가져옴.
    """
    NAVER_BOOKS_API_URL = settings.NAVER_BOOKS_API_URL
    params = {"d_isbn": isbn, "display": 1}

    try:
        response = requests.get(NAVER_BOOKS_API_URL, headers=headers, params=params)
        response.raise_for_status()
        items = response.json().get("items", [])

        if items:
            return {
                "title": items[0].get("title"),
                "author": items[0].get("author"),
                "publisher": items[0].get("publisher")
            }

        return None
    except requests.exceptions.RequestException:
        return None

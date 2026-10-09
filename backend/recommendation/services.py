from book.identifiers import external_isbn, validate_isbn
from book.models import Book
from book.services import search_books_from_naver, get_book_by_isbn_from_naver


def isbn_identity(isbn):
    """Compare valid ISBN-10/13 aliases without repairing request tokens."""
    if len(isbn) == 10:
        prefix = '978' + isbn[:9]
        checksum = (10 - sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(prefix)) % 10) % 10
        return prefix + str(checksum)
    return isbn


def get_book_recommendations(isbn=None, query=None, display=5):
    if isbn is not None:
        validate_isbn(isbn)
        info = Book.objects.filter(isbn__in=[isbn, isbn_identity(isbn)]).values('author', 'publisher').first()
        if info is None:
            info = get_book_by_isbn_from_naver(isbn)
        # Only an explicitly supplied query is used if metadata is unavailable.
        query = f"{(info or {}).get('publisher') or ''} {(info or {}).get('author') or ''}".strip()[:200] or query
    if not query:
        return []
    results, seen = [], set()
    current = isbn_identity(isbn) if isbn else None
    for item in search_books_from_naver(query, display=display):
        candidate = external_isbn(item.get('isbn'))
        if not candidate:
            continue
        identity = isbn_identity(candidate)
        if identity == current or identity in seen:
            continue
        seen.add(identity)
        results.append({**{key: item.get(key) or '' for key in ('title', 'author', 'publisher', 'image', 'link')}, 'isbn': candidate})
        if len(results) >= display:
            break
    return results


def get_personalized_recommendations(user, isbn=None, display=5):
    """Local, read-only rules: positive preferences, then community evidence."""
    from collections import Counter
    from django.db.models import Avg, Count, Q
    from book.identifiers import valid_isbn
    from review.models import Review

    author_weights, publisher_weights = Counter(), Counter()
    read_ids, read_isbns = set(), set()
    for review in Review.objects.filter(user=user).select_related('book'):
        book = review.book
        read_ids.add(book.pk)
        if valid_isbn(book.isbn):
            read_isbns.add(isbn_identity(book.isbn))
        if review.rating is None or not 4 <= review.rating <= 5:
            continue
        weight = review.rating - 3
        if book.author:
            author_weights[book.author.strip().casefold()] += weight
        if book.publisher:
            publisher_weights[book.publisher.strip().casefold()] += weight

    valid_rating = Q(reviews__rating__gte=0, reviews__rating__lte=5)
    candidates = Book.objects.exclude(pk__in=read_ids).annotate(
        community_rating=Avg('reviews__rating', filter=valid_rating),
        rating_count=Count('reviews__rating', filter=valid_rating),
    )
    current = isbn_identity(isbn) if isbn else None
    ranked = []
    for book in candidates:
        if not valid_isbn(book.isbn):
            continue
        identity = isbn_identity(book.isbn)
        if identity == current or identity in read_isbns:
            continue
        preference = 2 * author_weights[(book.author or '').strip().casefold()] + publisher_weights[(book.publisher or '').strip().casefold()]
        ranked.append(((-preference, -(book.community_rating or 0), -book.rating_count, identity, book.isbn, book.pk), book))
    results, seen = [], set()
    for _, book in sorted(ranked, key=lambda entry: entry[0]):
        identity = isbn_identity(book.isbn)
        if identity in seen:
            continue
        seen.add(identity)
        results.append({'isbn': book.isbn, 'title': book.title, 'author': book.author or '', 'publisher': book.publisher or '', 'image': book.image_url or '', 'link': book.link or ''})
        if len(results) >= display:
            break
    return results

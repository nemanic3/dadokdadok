"""Counts of distinct books with reviews, dated by review.created_at (not completion)."""
from django.conf import settings
from django.db.models import Count
from django.db.models.functions import ExtractMonth, ExtractYear, TruncMonth
from django.utils import timezone
from review.models import Review
from .periods import scope_name

DATE_BASIS = 'REVIEW_RECORD_DATE'
DATE_BASIS_LABEL = '리뷰 기록일 기준 도서 수 (실제 완독일이 아님)'


def period_metadata(year, month):
    return {'year': year, 'month': month, 'scope': scope_name(year, month),
            'date_basis': DATE_BASIS, 'date_field': 'review.created_at',
            'date_basis_label': DATE_BASIS_LABEL, 'timezone': settings.TIME_ZONE}


def period_records(user, year=None, month=None):
    records = Review.objects.filter(user=user)
    tz = timezone.get_default_timezone()
    if year is not None:
        # Exact year lookups become UTC bounds using the active timezone, even
        # with explicit tzinfo, and underflow at Seoul's year 1 boundary.
        # IN keeps the explicit calendar extraction for the full 1..9999 contract.
        records = records.annotate(record_year=ExtractYear('created_at', tzinfo=tz)).filter(record_year__in=[year])
    if month is not None:
        records = records.annotate(record_month=ExtractMonth('created_at', tzinfo=tz)).filter(record_month=month)
    return records


def count_books(user, year=None, month=None):
    return period_records(user, year, month).values('book_id').distinct().count()


def monthly_counts(user, year, month=None):
    rows = (period_records(user, year, month)
            .annotate(period=TruncMonth('created_at', tzinfo=timezone.get_default_timezone()))
            .values('period').annotate(count=Count('book_id', distinct=True)).order_by('period'))
    counts = {row['period'].strftime('%Y-%m'): row['count'] for row in rows}
    months = [month] if month is not None else range(1, 13)
    return {f'{year:04d}-{m:02d}': counts.get(f'{year:04d}-{m:02d}', 0) for m in months}

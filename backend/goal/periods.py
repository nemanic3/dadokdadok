"""Explicit calendar scopes; historical reviews use record date, not completion."""
from rest_framework.exceptions import ValidationError


def parse_period(params):
    if 'month' in params and 'year' not in params:
        raise ValidationError({'month': '월 조회에는 연도가 필요합니다.'})
    if 'year' not in params:
        return None, None
    try:
        year = int(params['year'])
        month = int(params['month']) if 'month' in params else None
    except (TypeError, ValueError):
        raise ValidationError({'period': '연도와 월은 정수여야 합니다.'})
    if not 1 <= year <= 9999 or (month is not None and not 1 <= month <= 12):
        raise ValidationError({'period': '연도는 1~9999, 월은 1~12여야 합니다.'})
    return year, month


def scope_name(year, month):
    return 'legacy' if year is None else ('annual' if month is None else 'monthly')

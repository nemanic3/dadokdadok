"""Validate request identifiers exactly; never repair malformed user ISBNs."""
import re
from rest_framework.exceptions import ValidationError


def valid_isbn(value):
    if not isinstance(value, str):
        return False
    if re.fullmatch(r'(978|979)[0-9]{10}', value):
        return sum(int(digit) * (1 if index % 2 == 0 else 3)
                   for index, digit in enumerate(value)) % 10 == 0
    if re.fullmatch(r'[0-9]{9}[0-9X]', value):
        digits = [int(digit) if digit != 'X' else 10 for digit in value]
        return sum((10 - index) * digit for index, digit in enumerate(digits)) % 11 == 0
    return False


def validate_isbn(value):
    if not valid_isbn(value):
        raise ValidationError({'isbn': '유효한 ISBN-10 또는 ISBN-13을 입력해주세요.'})
    return value


def external_isbn(value):
    """Naver can provide multiple space-separated ISBNs; prefer a valid ISBN-13."""
    if not isinstance(value, str):
        return None
    tokens = [token for token in value.split() if valid_isbn(token)]
    return next((token for token in tokens if len(token) == 13), tokens[0] if tokens else None)

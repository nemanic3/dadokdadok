from rest_framework.exceptions import ValidationError


def bounded_integer(value, name, minimum, maximum):
    text = str(value)
    if not text.isascii() or not text.isdecimal() or len(text) > 6:
        raise ValidationError({name: '유효한 정수를 입력해주세요.'})
    result = int(text)
    if not minimum <= result <= maximum:
        raise ValidationError({name: f'{minimum}~{maximum} 범위여야 합니다.'})
    return result

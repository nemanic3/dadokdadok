"""One best-effort IP budget for external book lookups and recommendations."""
from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class BookThrottle(SimpleRateThrottle):
    scope = 'book'

    def get_rate(self):
        rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        return rates.get(self.scope, rates.get('books', '60/min'))

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': request.META.get('REMOTE_ADDR', 'unknown')}

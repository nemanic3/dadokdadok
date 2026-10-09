from hashlib import sha256

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.throttling import SimpleRateThrottle


class ExplicitAuthThrottle(SimpleRateThrottle):
    """Local defaults stay enabled even without global DRF throttle settings."""
    def get_rate(self):
        return getattr(settings, 'USER_AUTH_THROTTLE_RATES', {}).get(self.scope, self.default_rate)

    def get_cache_key(self, request, view):
        # Do not trust client-supplied X-Forwarded-For to bypass authentication limits.
        ident = request.META.get('REMOTE_ADDR', 'unknown')
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class SignupIPThrottle(ExplicitAuthThrottle):
    scope = 'signup_ip'
    default_rate = '5/min'


class LoginIPThrottle(ExplicitAuthThrottle):
    scope = 'login_ip'
    default_rate = '10/min'


class RecoveryIPThrottle(ExplicitAuthThrottle):
    scope = 'recovery_ip'
    default_rate = '10/hour'


class ResetIPThrottle(ExplicitAuthThrottle):
    scope = 'reset_ip'
    default_rate = '10/min'


class IdentifierThrottle(ExplicitAuthThrottle):
    fields = ()

    def get_cache_key(self, request, view):
        if not isinstance(request.data, dict):
            return None
        identifier = next((request.data.get(field) for field in self.fields if request.data.get(field)), None)
        if not isinstance(identifier, str):
            return None
        digest = sha256(self.normalize_identifier(identifier).encode()).hexdigest()
        return self.cache_format % {'scope': self.scope, 'ident': digest}

    def normalize_identifier(self, identifier):
        return identifier.strip().lower()


class LoginIdentityThrottle(IdentifierThrottle):
    scope = 'login_identity'
    default_rate = '5/min'
    fields = ('username', 'email')

    def normalize_identifier(self, identifier):
        return get_user_model().normalize_username(identifier).strip().lower()


class RecoveryIdentityThrottle(IdentifierThrottle):
    scope = 'recovery_identity'
    default_rate = '3/hour'
    fields = ('email',)


class ResetIdentityThrottle(IdentifierThrottle):
    scope = 'reset_identity'
    default_rate = '10/min'
    fields = ('uid',)


class UserMutationThrottle(ExplicitAuthThrottle):
    scope = 'user_mutation'
    default_rate = '20/min'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            return self.cache_format % {'scope': self.scope, 'ident': str(request.user.pk)}
        return super().get_cache_key(request, view)

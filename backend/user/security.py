from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken


def revoke_refresh_tokens(user):
    """Password changes invalidate every previously issued refresh token."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)

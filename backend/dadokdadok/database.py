"""Parse PostgreSQL configuration without including its secret URL in errors."""
from urllib.parse import unquote, urlsplit, parse_qs
from django.core.exceptions import ImproperlyConfigured


def postgres_database(value, require_tls=False):
    try:
        url = urlsplit(value)
        if url.scheme not in ('postgres', 'postgresql') or not url.hostname or not url.username or not url.path.strip('/'):
            raise ValueError
        query = parse_qs(url.query)
        sslmode = query.get('sslmode', ['require' if require_tls else 'prefer'])[0]
        if sslmode not in ('disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full'):
            raise ValueError
        if require_tls and sslmode not in ('require', 'verify-ca', 'verify-full'):
            raise ValueError
        options = {'sslmode': sslmode, 'connect_timeout': 15}
        if 'channel_binding' in query:
            mode = query['channel_binding'][0]
            if mode not in ('disable', 'prefer', 'require'):
                raise ValueError
            options['channel_binding'] = mode
        return {
            'ENGINE': 'django.db.backends.postgresql', 'NAME': unquote(url.path[1:]),
            'USER': unquote(url.username), 'PASSWORD': unquote(url.password or ''),
            'HOST': url.hostname, 'PORT': url.port or 5432,
            'CONN_MAX_AGE': 0, 'DISABLE_SERVER_SIDE_CURSORS': True, 'OPTIONS': options,
        }
    except (ValueError, TypeError, IndexError):
        raise ImproperlyConfigured('DATABASE_URL must be a valid PostgreSQL URL with required TLS in production.') from None

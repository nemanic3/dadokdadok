"""Accept proxy metadata only after verifying the Pages-to-origin secret."""
import ipaddress
import secrets
from django.conf import settings
from django.http import JsonResponse


class PagesProxyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.DEBUG and settings.ORIGIN_PROXY_SECRET:
            supplied = request.META.pop('HTTP_X_DADOK_PROXY_SECRET', '')
            if not secrets.compare_digest(supplied, settings.ORIGIN_PROXY_SECRET):
                return JsonResponse({'detail': 'Forbidden'}, status=403)
            address = request.META.pop('HTTP_X_DADOK_CLIENT_IP', '')
            try:
                request.META['REMOTE_ADDR'] = str(ipaddress.ip_address(address))
            except ValueError:
                return JsonResponse({'detail': 'Invalid proxy metadata'}, status=400)
            # Authenticated Pages code connects to the fixed HTTPS origin only.
            request.META['wsgi.url_scheme'] = 'https'
        for name in ('HTTP_FORWARDED', 'HTTP_X_FORWARDED_FOR', 'HTTP_X_FORWARDED_HOST', 'HTTP_X_FORWARDED_PROTO'):
            request.META.pop(name, None)
        return self.get_response(request)

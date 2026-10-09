from django.db import connection, DatabaseError
from django.http import JsonResponse
from django.views.decorators.http import require_safe


@require_safe
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({'status': 'unavailable'}, status=503, headers={'Cache-Control': 'no-store'})
    return JsonResponse({'status': 'ok'}, headers={'Cache-Control': 'no-store'})

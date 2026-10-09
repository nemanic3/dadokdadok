import os

bind = '0.0.0.0:' + os.environ.get('PORT', '8000')
# Modest resource use on the free 512MB instance; DB-backed cache shares quotas.
workers = 1
threads = 1
worker_class = 'sync'
timeout = 40
accesslog = None  # Never log recovery query strings or Authorization headers.
errorlog = '-'
forwarded_allow_ips = ''
secure_scheme_headers = {}

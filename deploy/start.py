"""Start a PostgreSQL origin; existing SQLite is never read or imported."""
import os
import subprocess
import sys
from pathlib import Path

os.umask(0o077)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dadokdadok.production')
import django
django.setup()
subprocess.run([sys.executable, 'manage.py', 'check', '--deploy', '--fail-level', 'WARNING'], check=True)
subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'], check=True)
subprocess.run([sys.executable, 'manage.py', 'createcachetable'], check=True)
os.execvp('gunicorn', ['gunicorn', 'dadokdadok.wsgi:application', '--config', '../deploy/gunicorn.conf.py'])

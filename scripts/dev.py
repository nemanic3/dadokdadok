"""Run the existing Django API + static frontend on loopback with a separate DB."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT / '.local/dev.sqlite3')
    parser.add_argument('--backend-port', type=int, default=8000)
    parser.add_argument('--frontend-port', type=int, default=5500)
    parser.add_argument('--check', action='store_true', help='Print safe configuration without starting/migrating anything')
    args = parser.parse_args()
    database = args.database.resolve()
    original = (ROOT / 'backend/db.sqlite3').resolve()
    if database == original or (database.exists() and original.exists() and database.samefile(original)):
        parser.error('Refusing to migrate or run against the original database; use an isolated path.')
    if not all(1 <= port <= 65535 for port in (args.backend_port, args.frontend_port)):
        parser.error('Ports must be between 1 and 65535.')
    if args.backend_port == args.frontend_port:
        parser.error('Backend and frontend ports must differ.')
    config = {'database': str(database), 'host': '127.0.0.1', 'backend_port': args.backend_port,
              'frontend_port': args.frontend_port}
    if args.check:
        print(json.dumps(config))
        return
    if args.backend_port != 8000:
        parser.error('Frontend defaults to port 8000; configure window.DADOK_API_BASE_URL before using a custom API port.')
    # Fail before migrations if either loopback port is already in use.
    for port in (args.backend_port, args.frontend_port):
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', port))
            except OSError:
                parser.error(f'Port {port} is already in use; no database migration was run.')
    env = dict(os.environ, DJANGO_DB_PATH=str(database), DJANGO_DEBUG='1', PYTHONDONTWRITEBYTECODE='1',
               DJANGO_CORS_ALLOWED_ORIGINS=f'http://127.0.0.1:{args.frontend_port}')
    database.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, '-B', 'manage.py', 'check'], cwd=ROOT / 'backend', env=env, check=True)
    subprocess.run([sys.executable, '-B', 'manage.py', 'migrate', '--noinput'], cwd=ROOT / 'backend', env=env, check=True)
    processes = []
    try:
        processes.append(subprocess.Popen([sys.executable, '-B', 'manage.py', 'runserver',
                          f'127.0.0.1:{args.backend_port}', '--noreload'], cwd=ROOT / 'backend', env=env))
        processes.append(subprocess.Popen([sys.executable, '-B', '-m', 'http.server',
                          str(args.frontend_port), '--bind', '127.0.0.1', '--directory', str(ROOT / 'frontend')], env=env))
        print(f'Frontend: http://127.0.0.1:{args.frontend_port}/screen/index.html\nIsolated DB: {database}', flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.25)
        raise RuntimeError('A development server exited unexpectedly.')
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    main()

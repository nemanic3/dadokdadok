"""Repository hygiene regressions; never inspect private file contents."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RepositorySafetyTests(unittest.TestCase):
    def assert_ignored(self, path):
        result = subprocess.run(['git', 'check-ignore', '--no-index', '--', path],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f'Generated/private artifact is not ignored: {path}')

    def test_arbitrary_local_databases_are_ignored(self):
        for path in ('backend/test-fixture.sqlite3', 'backend/test-fixture.sqlite3-wal'):
            self.assert_ignored(path)

    def test_ide_metadata_is_ignored(self):
        self.assert_ignored('.idea/.name')

    def test_local_credentials_and_generated_dependencies_are_ignored(self):
        for path in ('.venv-dev/lib/generated.py', 'backend/local_credentials.json', '.env', 'frontend/node_modules/generated.js',
                     'backend/user/__pycache__/generated.pyc'):
            self.assert_ignored(path)

    def test_index_does_not_track_private_or_generated_files(self):
        result = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True)
        unsafe = [path for path in result.stdout.decode().split('\0') if path and (
            'node_modules' in Path(path).parts or '__pycache__' in Path(path).parts or
            path.endswith('.sqlite3') or Path(path).name == 'local_credentials.json')]
        self.assertEqual(unsafe, [])

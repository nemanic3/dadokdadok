import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

import os
import tempfile
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO
import importlib.util

class LocalRunnerTests(unittest.TestCase):
    def test_hardlink_to_original_database_is_refused(self):
        spec = importlib.util.spec_from_file_location('dadok_dev_test', ROOT / 'scripts/dev.py')
        assert spec is not None and spec.loader is not None
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            sandbox = Path(directory)
            (sandbox / 'backend').mkdir()
            original = sandbox / 'backend/db.sqlite3'
            original.write_bytes(b'explicit-test-fixture')
            alias = sandbox / 'alias.sqlite3'
            os.link(original, alias)
            with patch.object(runner, 'ROOT', sandbox), patch.object(sys, 'argv', ['dev.py', '--check', '--database', str(alias)]), redirect_stdout(StringIO()):
                with self.assertRaises(SystemExit) as error:
                    runner.main()
                self.assertEqual(error.exception.code, 2)
            self.assertEqual(original.read_bytes(), b'explicit-test-fixture')

    def test_check_defaults_to_isolated_database_and_loopback(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/dev.py'), '--check'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)
        self.assertEqual(Path(config['database']), ROOT / '.local/dev.sqlite3')
        self.assertEqual(config['host'], '127.0.0.1')

    def test_original_database_is_refused(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/dev.py'), '--check',
                                '--database', str(ROOT / 'backend/db.sqlite3')], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('original database', result.stderr)

"""Offline upgrade acceptance gate; does not load settings or connect to a DB.

Run with either runtime: python -B tests/verify_supported_dependencies.py
This is a dated acceptance floor, not a live advisory service. Re-evaluate the
floor against official support policy and PyPI before future deployments.
"""
from importlib.metadata import version
import sys
import unittest


class SupportedDependencyAcceptance(unittest.TestCase):
    def test_supported_lts_with_verified_security_patch_is_installed(self):
        current = tuple(int(part) for part in version('Django').split('.'))
        self.assertEqual(current[:2], (5, 2), '2026-10-09 acceptance requires supported Django 5.2 LTS')
        self.assertGreaterEqual(current, (5, 2, 18), 'Install the verified 2026-10-06 patch or a later reviewed 5.2 patch')

    def test_drf_supports_django_52_with_verified_security_floor(self):
        current = tuple(int(part) for part in version('djangorestframework').split('.'))
        self.assertGreaterEqual(current, (3, 17, 2), 'The advisory database rejects the originally proposed DRF 3.16.1')
        self.assertEqual(current[0], 3)

    def test_simplejwt_includes_django_52_compatibility(self):
        current = tuple(int(part) for part in version('djangorestframework_simplejwt').split('.'))
        self.assertGreaterEqual(current, (5, 5, 1))
        self.assertEqual(current[0], 5)

    def test_supported_python(self):
        self.assertEqual(sys.version_info[:2], (3, 12))


if __name__ == '__main__':
    unittest.main(verbosity=2)

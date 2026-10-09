import importlib
from django.test import SimpleTestCase, override_settings
from django.urls import clear_url_caches


class DevelopmentMediaTests(SimpleTestCase):
    def test_legacy_profile_image_path_serves_existing_svg_in_development(self):
        from dadokdadok import urls
        with override_settings(DEBUG=True):
            importlib.reload(urls)
            clear_url_caches()
            response = self.client.get('/media/profile_images/profile_image1.svg')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'<svg', b''.join(response.streaming_content))
        importlib.reload(urls)
        clear_url_caches()

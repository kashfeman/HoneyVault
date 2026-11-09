"""Rendering contracts for the deliberately unprotected frontend preview."""

import unittest
from html.parser import HTMLParser

from scripts.preview_frontend import create_preview_app


class Inputs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        if tag == "input":
            self.inputs.append(dict(attrs))


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.app = create_preview_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def test_pages_render_with_local_assets_and_disclosure(self):
        for path in ("/login", "/dashboard"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn('id="main"', html)
                self.assertIn("fictional", html.lower())
                self.assertIn("no authentication", html.lower())
                self.assertNotIn("https://", html)
                self.assertNotIn("Set-Cookie", response.headers)
        for path in ("/static/css/main.css", "/static/js/main.js"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_dashboard_is_public_and_contains_demo_events(self):
        html = self.client.get("/dashboard").get_data(as_text=True)
        self.assertIn("DEMO-008", html)
        self.assertIn("Demo data only", html)
        self.assertIn("<caption", html)
        self.assertIn('scope="col"', html)

    def test_login_excludes_inputs_from_submission(self):
        html = self.client.get("/login").get_data(as_text=True)
        parser = Inputs()
        parser.feed(html)
        self.assertEqual(len(parser.inputs), 2)
        self.assertTrue(all("name" not in field for field in parser.inputs))
        self.assertIn('action="/dashboard" method="get"', html)
        self.assertEqual(self.client.post("/login").status_code, 405)

    def test_root_opens_login_preview(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")


if __name__ == "__main__":
    unittest.main()

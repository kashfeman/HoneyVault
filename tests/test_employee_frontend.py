"""Focused contracts for public presentation fixtures and document pages."""

import unittest
from unittest.mock import patch

from scripts.frontend_data import DOCUMENTS, select_documents
from scripts.preview_frontend import create_preview_app


class EmployeePreviewTests(unittest.TestCase):
    def setUp(self):
        self.client = create_preview_app().test_client()

    def test_pages_are_public_and_do_not_leak_classification(self):
        paths = ["/employee", "/employee/documents", "/dashboard/documents"]
        paths += [f"/employee/documents/{document['id']}" for document in DOCUMENTS]
        paths += ["/dashboard/documents/doc-102"]
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                html = response.get_data(as_text=True).lower()
                self.assertEqual(response.status_code, 200)
                self.assertIn("no authentication", html)
                self.assertNotIn("set-cookie", response.headers)
                for forbidden in ("decoy", "sensitivity", "confidential", "is_decoy", "classification"):
                    self.assertNotIn(forbidden, html)
        allowed = {"id", "title", "category", "format", "owner", "updated", "description", "content"}
        self.assertTrue(all(set(document) == allowed for document in DOCUMENTS))

    def test_search_category_sort_and_empty_state(self):
        results = select_documents("DEMO FINANCE", "Finance", "title")
        self.assertEqual([item["id"] for item in results], ["doc-102", "doc-104"])
        self.assertEqual(select_documents("handbook")[0]["id"], "doc-101")
        oldest = select_documents(sort="oldest")
        self.assertEqual(oldest[0]["id"], "doc-106")
        for base in ("/employee/documents", "/dashboard/documents"):
            response = self.client.get(base, query_string={"category": "Finance", "sort": "title"})
            html = response.get_data(as_text=True)
            self.assertIn("2 of 6 demo documents", html)
            self.assertLess(html.index("Quarterly budget forecast"), html.index("Vendor allocation register"))
            self.assertNotIn("Team handbook", html)
            empty = self.client.get(base, query_string={"q": "no-such-document"}).get_data(as_text=True)
            self.assertIn("No documents found", empty)
            self.assertIn("Clear filters", empty)
        html = self.client.get("/employee/documents?category=invalid&sort=invalid").get_data(as_text=True)
        self.assertIn("6 of 6 demo documents", html)

    def test_preview_escapes_content_and_unknown_reference_has_recovery(self):
        fixture = dict(DOCUMENTS[0], content='<script>alert("fictional")</script>')
        with patch("scripts.preview_frontend.DOCUMENTS", (fixture,)):
            html = self.client.get("/employee/documents/doc-101").get_data(as_text=True)
            self.assertIn("&lt;script&gt;", html)
            self.assertNotIn('<script>alert(', html)
        html = self.client.get("/employee/documents", query_string={"q": '<script>alert(1)</script>'}).get_data(as_text=True)
        self.assertNotIn('<script>alert(1)', html)
        for base in ("/employee", "/dashboard"):
            response = self.client.get(f"{base}/documents/unknown")
            self.assertEqual(response.status_code, 404)
            self.assertIn("Browse the library", response.get_data(as_text=True))

    def test_preview_assets_and_download_boundary(self):
        html = self.client.get("/employee/documents/doc-102").get_data(as_text=True)
        self.assertIn("department,quarter,planned_units", html)
        self.assertIn("Backend integration pending", html)
        self.assertIn("disabled", html)
        self.assertNotIn(' download=', html)
        self.assertEqual(self.client.post("/employee/documents/doc-102").status_code, 405)
        for path in ("/static/css/documents.css", "/static/js/documents.js"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            response.close()


if __name__ == "__main__":
    unittest.main()

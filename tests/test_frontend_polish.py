"""Regression checks for Milestone 5 presentation fixes."""

from copy import deepcopy
import unittest
from unittest.mock import patch

from scripts.admin_demo_data import EVENTS, dashboard_snapshot
from scripts.frontend_data import DOCUMENTS
from scripts.preview_frontend import create_preview_app


class FrontendPolishTests(unittest.TestCase):
    def setUp(self):
        self.client = create_preview_app().test_client()

    def test_recent_events_sort_by_timestamp_instead_of_tuple_position(self):
        expected = dashboard_snapshot()
        with patch("scripts.admin_demo_data.EVENTS", tuple(reversed(EVENTS))):
            actual = dashboard_snapshot()
        self.assertEqual(actual, expected)
        self.assertEqual(actual["events"][0]["id"], "DEMO-008")

    def test_unknown_pages_recover_in_the_correct_workspace_without_debug_details(self):
        cases = (("/missing-page", "/login"),
                 ("/employee/missing-page", "/employee"),
                 ("/dashboard/missing-page", "/dashboard"))
        for path, home in cases:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                html = response.get_data(as_text=True)
                self.assertIn("Page not found", html)
                self.assertIn("Return to preview home", html)
                self.assertIn(f'href="{home}"', html)
                self.assertNotIn(path, html)
                self.assertNotIn("Traceback", html)
                self.assertNotIn("SURFACE", html)
                if path.startswith("/employee/"):
                    for forbidden in ("decoy", "sensitivity", "admin.js", "Confidential"):
                        self.assertNotIn(forbidden, html)

    def test_current_employee_location_and_view_relationships_are_announced(self):
        html = self.client.get("/employee/documents/doc-102").get_data(as_text=True)
        self.assertIn('aria-label="Breadcrumb"', html)
        self.assertIn('href="/employee/documents" aria-current="location"', html)
        library = self.client.get("/employee/documents").get_data(as_text=True)
        self.assertIn('aria-controls="document-table"', library)
        self.assertIn('aria-controls="document-cards"', library)

    def test_management_and_review_pages_leave_public_fixtures_unchanged(self):
        before = deepcopy(DOCUMENTS)
        for path in ("/dashboard/manage-documents", "/dashboard/alerts/ALERT-001",
                     "/dashboard/events?outcome=Denied", "/employee/documents?q=Finance"):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(DOCUMENTS, before)
        self.assertTrue(all("classification" not in item and "sensitivity" not in item for item in DOCUMENTS))


if __name__ == "__main__":
    unittest.main()

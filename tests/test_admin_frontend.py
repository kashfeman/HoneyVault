"""Focused administrator UI contracts; these do not test real security controls."""

from html.parser import HTMLParser
from urllib.parse import urlsplit
import unittest

from scripts.admin_demo_data import (ADMIN_DOCUMENTS, ALERTS, EVENTS, DOCUMENT_BY_ID,
                                     ALERT_BY_ID, EVENT_BY_ID, dashboard_snapshot)
from scripts.frontend_data import DOCUMENTS
from scripts.preview_frontend import create_preview_app


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.add(attributes["id"])
        if tag == "a" and attributes.get("href", "").startswith("/"):
            self.links.append(attributes["href"])


class AdminFrontendTests(unittest.TestCase):
    def setUp(self):
        self.client = create_preview_app().test_client()

    def html(self, path, **kwargs):
        response = self.client.get(path, **kwargs)
        self.assertEqual(response.status_code, 200, path)
        self.assertNotIn("Set-Cookie", response.headers)
        return response.get_data(as_text=True)

    def test_new_routes_and_accessible_page_contracts(self):
        paths = ["/dashboard/manage-documents", "/dashboard/alerts", "/dashboard/events"]
        paths += [f"/dashboard/manage-documents/{item['id']}" for item in ADMIN_DOCUMENTS]
        paths += [f"/dashboard/alerts/{item['id']}" for item in ALERTS]
        paths += [f"/dashboard/events/{item['id']}" for item in EVENTS]
        for path in paths:
            with self.subTest(path=path):
                html = self.html(path)
                self.assertIn("no authentication", html)
                self.assertIn('id="main"', html)
                self.assertIn('aria-current=', html)
        inventory = self.html(paths[0])
        self.assertIn('aria-labelledby="dialog-title"', inventory)
        self.assertIn('method="dialog"', inventory)
        self.assertIn("Confidential", inventory)
        self.assertIn("inventory-cards", inventory)
        self.assertIn("required", inventory)
        for path in ("/static/css/admin.css", "/static/js/admin.js"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_inventory_filters_and_empty_state(self):
        html = self.html("/dashboard/manage-documents?category=Finance&format=CSV&q=budget")
        self.assertIn("1 of 6 demo documents", html)
        self.assertIn("quarterly_budget_forecast.csv", html)
        self.assertNotIn("vendor_allocation_register.csv", html)
        self.assertIn("No documents found", self.html("/dashboard/manage-documents?q=nonexistent"))
        self.assertIn("6 of 6 demo documents", self.html("/dashboard/manage-documents?format=invalid"))

    def test_alert_and_event_filters_and_utc_bounds(self):
        html = self.html("/dashboard/alerts?severity=High&status=Open&action=Download+request")
        self.assertIn("1 matching demo alerts", html)
        self.assertIn("ALERT-001", html)
        self.assertNotIn("ALERT-002", html)
        html = self.html("/dashboard/events?outcome=Denied&action=Download+response")
        self.assertIn("2 matching demo events", html)
        self.assertNotIn("DEMO-002", html)
        for path in ("/dashboard/alerts", "/dashboard/events"):
            html = self.html(path, query_string={"start": "2026-11-09T14:42", "end": "2026-11-09T14:42"})
            self.assertIn("1 matching demo alerts" if path.endswith("alerts") else "2 matching demo events", html)
            self.assertIn("Invalid start time", self.html(path + "?start=invalid"))
            self.assertIn("Start time must be before end time", self.html(path, query_string={"start": "2026-11-10T00:00", "end": "2026-11-09T00:00"}))
            self.assertIn("No " + path.rsplit("/", 1)[-1] + " found", self.html(path + "?q=nonexistent"))
        self.assertIn("1 matching demo events", self.html("/dashboard/events?q=DEMO-008&actor=Demo+analyst+04"))

    def test_references_and_dashboard_counts_are_consistent(self):
        for event in EVENTS:
            self.assertIn(event["document_id"], DOCUMENT_BY_ID)
            if event["alert_id"]:
                alert = ALERT_BY_ID[event["alert_id"]]
                self.assertIn(event["id"], alert["event_ids"])
                self.assertEqual(event["rule"], alert["rule"])
                self.assertEqual(event["actor"], alert["actor"])
                self.assertEqual(event["document_id"], alert["document_id"])
        for alert in ALERTS:
            for key in alert["event_ids"]:
                self.assertEqual(EVENT_BY_ID[key]["alert_id"], alert["id"])
        snapshot = dashboard_snapshot()
        self.assertEqual(snapshot["document_count"], len(DOCUMENTS))
        self.assertEqual(snapshot["event_count"], len(EVENTS))
        self.assertEqual(sum(snapshot["counts"].values()), len(ALERTS))
        self.assertEqual(sum(sample + decoy for _, sample, decoy in snapshot["chart"]), len(EVENTS))
        html = self.html("/dashboard")
        self.assertIn("Showing 4 of 8 illustrative events", html)
        self.assertIn("4 sample files · 2 decoys", html)
        self.assertIn("1 high · 1 medium · 1 low", html)
        detail = self.html("/dashboard/alerts/ALERT-001")
        self.assertIn("DEMO-007", detail)
        self.assertIn("DEMO-008", detail)
        self.assertLess(detail.index('datetime="2026-11-09T14:42:00Z"'), detail.index('datetime="2026-11-09T14:42:01Z"', detail.index('id="timeline-heading"')))

    def test_admin_metadata_and_script_are_absent_from_employee_responses(self):
        paths = ["/employee", "/employee/documents"]
        paths += [f"/employee/documents/{item['id']}" for item in DOCUMENTS]
        for path in paths:
            html = self.html(path).lower()
            for forbidden in ("decoy", "classification", "sensitivity", "restricted", "confidential", "admin.js", "admin.css", "alert-001", "demo-r01"):
                self.assertNotIn(forbidden, html, (path, forbidden))
        self.assertTrue(all("classification" not in document for document in DOCUMENTS))

    def test_no_mutations_unknown_references_and_escaped_search(self):
        for base in ("/dashboard/manage-documents", "/dashboard/alerts", "/dashboard/events"):
            self.assertEqual(self.client.post(base).status_code, 405)
            self.assertEqual(self.client.get(base + "/unknown").status_code, 404)
            html = self.html(base, query_string={"q": '<script>alert("demo")</script>'})
            self.assertIn("&lt;script&gt;", html)
            self.assertNotIn('<script>alert(', html)
        event = self.html("/dashboard/events/DEMO-008")
        self.assertNotIn("data-review=", event)
        self.assertNotIn("data-open-dialog", event)
        self.assertIn("not a real log entry", event)
        html = self.html("/dashboard/alerts/ALERT-001")
        self.assertIn("reset on refresh", html)

    def test_all_linked_pages_and_anchor_targets_exist(self):
        queue = ["/dashboard", "/login", "/employee"]
        seen = set()
        while queue:
            path = queue.pop()
            if path in seen:
                continue
            seen.add(path)
            html = self.html(path)
            parser = Links()
            parser.feed(html)
            for href in parser.links:
                parts = urlsplit(href)
                target = parts.path + ("?" + parts.query if parts.query else "")
                if parts.fragment:
                    anchor_parser = Links()
                    anchor_parser.feed(self.html(target))
                    self.assertIn(parts.fragment, anchor_parser.ids, href)
                if target not in seen:
                    queue.append(target)


if __name__ == "__main__":
    unittest.main()

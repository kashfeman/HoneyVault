"""Administrator presentation fixtures only. No rules, logs, storage or enforcement.

Never pass this module's enriched records to employee templates. Public document
content remains in frontend_data; this module joins admin labels by stable ID.
"""

if __package__:
    from .frontend_data import DOCUMENTS
else:
    from frontend_data import DOCUMENTS

SNAPSHOT = "2026-11-09"
ADMIN_LABELS = {
    "doc-101": ("Synthetic", "General", "Active"),
    "doc-102": ("Decoy", "Confidential", "Active"),
    "doc-103": ("Synthetic", "Internal", "Active"),
    "doc-104": ("Decoy", "Restricted", "Active"),
    "doc-105": ("Synthetic", "General", "Active"),
    "doc-106": ("Synthetic", "Internal", "Draft"),
}
ADMIN_DOCUMENTS = tuple(dict(document,
    filename=document["title"].lower().replace(" ", "_") + "." + document["format"].lower(),
    classification=ADMIN_LABELS[document["id"]][0],
    sensitivity=ADMIN_LABELS[document["id"]][1], status=ADMIN_LABELS[document["id"]][2],
    created="2026-11-01") for document in DOCUMENTS)
DOCUMENT_BY_ID = {document["id"]: document for document in ADMIN_DOCUMENTS}

# Request/response pairs are illustrative, not records of actual preview use.
EVENTS = (
    dict(id="DEMO-001", timestamp="2026-11-09T09:00:00Z", actor="Demo analyst 02", document_id="doc-101", action="Preview request", outcome="Requested", rule="—", alert_id=None, request_id="REQ-001"),
    dict(id="DEMO-002", timestamp="2026-11-09T09:00:01Z", actor="Demo analyst 02", document_id="doc-101", action="Preview response", outcome="Success", rule="—", alert_id=None, request_id="REQ-001"),
    dict(id="DEMO-003", timestamp="2026-11-09T10:15:00Z", actor="Demo analyst 07", document_id="doc-104", action="Download request", outcome="Requested", rule="DEMO-R02", alert_id="ALERT-002", request_id="REQ-002"),
    dict(id="DEMO-004", timestamp="2026-11-09T10:15:01Z", actor="Demo analyst 07", document_id="doc-104", action="Download response", outcome="Denied", rule="DEMO-R02", alert_id="ALERT-002", request_id="REQ-002"),
    dict(id="DEMO-005", timestamp="2026-11-09T12:24:00Z", actor="Demo analyst 04", document_id="doc-102", action="Preview request", outcome="Requested", rule="DEMO-R03", alert_id="ALERT-003", request_id="REQ-003"),
    dict(id="DEMO-006", timestamp="2026-11-09T12:24:01Z", actor="Demo analyst 04", document_id="doc-102", action="Preview response", outcome="Success", rule="DEMO-R03", alert_id="ALERT-003", request_id="REQ-003"),
    dict(id="DEMO-007", timestamp="2026-11-09T14:42:00Z", actor="Demo analyst 04", document_id="doc-102", action="Download request", outcome="Requested", rule="DEMO-R01", alert_id="ALERT-001", request_id="REQ-004"),
    dict(id="DEMO-008", timestamp="2026-11-09T14:42:01Z", actor="Demo analyst 04", document_id="doc-102", action="Download response", outcome="Denied", rule="DEMO-R01", alert_id="ALERT-001", request_id="REQ-004"),
)
ALERTS = (
    dict(id="ALERT-001", severity="High", status="Open", timestamp="2026-11-09T14:42:01Z", document_id="doc-102", actor="Demo analyst 04", action="Download request", rule="DEMO-R01", title="Download attempt on a decoy", explanation="This authored scenario associates a download request for the budget decoy with a high-severity example. The paired response illustrates a denial. No actual request was evaluated or denied by this preview.", event_ids=("DEMO-007", "DEMO-008")),
    dict(id="ALERT-002", severity="Medium", status="Open", timestamp="2026-11-09T10:15:01Z", document_id="doc-104", actor="Demo analyst 07", action="Download request", rule="DEMO-R02", title="Vendor register request", explanation="This medium-severity example illustrates a request for the vendor register and a denied response. Severity is authored fixture data, not a calculation or a finding about a real person.", event_ids=("DEMO-003", "DEMO-004")),
    dict(id="ALERT-003", severity="Low", status="Reviewed", timestamp="2026-11-09T12:24:01Z", document_id="doc-102", actor="Demo analyst 04", action="Preview request", rule="DEMO-R03", title="Budget document preview", explanation="This low-severity example pairs a preview request with a successful response. Its reviewed status is part of the fixed demo snapshot. Viewing a document alone does not establish malicious intent.", event_ids=("DEMO-005", "DEMO-006")),
)
ALERT_BY_ID = {alert["id"]: alert for alert in ALERTS}
EVENT_BY_ID = {event["id"]: event for event in EVENTS}


def filter_records(records, query="", filters=None, start="", end=""):
    """Presentation-only matching, including inclusive UTC timestamp bounds."""
    query = query.strip().casefold()
    result = []
    for record in records:
        document = DOCUMENT_BY_ID.get(record.get("document_id"), {})
        text = " ".join(str(value) for value in record.values()) + " " + document.get("title", "")
        if query not in text.casefold():
            continue
        if any(value and record.get(key) != value for key, value in (filters or {}).items()):
            continue
        timestamp = record.get("timestamp", "")
        if (start and timestamp < start) or (end and timestamp > end):
            continue
        result.append(record)
    return result


def dashboard_snapshot():
    counts = {severity: sum(alert["severity"] == severity for alert in ALERTS)
              for severity in ("High", "Medium", "Low")}
    recent = []
    for event in sorted(EVENTS, key=lambda item: item["timestamp"], reverse=True)[:4]:
        alert = ALERT_BY_ID.get(event["alert_id"])
        recent.append(dict(event, time=event["timestamp"][11:19] + " UTC",
                           document=DOCUMENT_BY_ID[event["document_id"]]["title"],
                           severity=alert["severity"].lower() if alert else "none"))
    chart = []
    for hour in range(0, 24, 4):
        group = [event for event in EVENTS if hour <= int(event["timestamp"][11:13]) < hour + 4]
        decoy = sum(DOCUMENT_BY_ID[event["document_id"]]["classification"] == "Decoy" for event in group)
        chart.append((f"{hour:02}:00", len(group) - decoy, decoy))
    return dict(document_count=len(ADMIN_DOCUMENTS), decoy_count=sum(document["classification"] == "Decoy" for document in ADMIN_DOCUMENTS),
                event_count=len(EVENTS), request_count=sum(event["action"].endswith("request") for event in EVENTS),
                response_count=sum(event["action"].endswith("response") for event in EVENTS),
                actor_count=len({event["actor"] for event in EVENTS}),
                alert_count=len(ALERTS), reviewed_count=sum(alert["status"] == "Reviewed" for alert in ALERTS),
                counts=counts, events=recent, chart=chart)

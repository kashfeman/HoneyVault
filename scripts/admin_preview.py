"""Read-only routes for the public administrator UI demonstration."""

from datetime import datetime, timezone

from flask import Blueprint, render_template, request

if __package__:
    from .admin_demo_data import ADMIN_DOCUMENTS, ALERTS, EVENTS, DOCUMENT_BY_ID, ALERT_BY_ID, EVENT_BY_ID, filter_records
    from .frontend_data import CATEGORIES
else:
    from admin_demo_data import ADMIN_DOCUMENTS, ALERTS, EVENTS, DOCUMENT_BY_ID, ALERT_BY_ID, EVENT_BY_ID, filter_records
    from frontend_data import CATEGORIES

admin_preview = Blueprint("admin_preview", __name__, url_prefix="/dashboard")


def query_options(choices):
    return {key: request.args.get(key, "") if request.args.get(key, "") in values else ""
            for key, values in choices.items()}


def time_bounds():
    bounds = {}
    errors = []
    for key in ("start", "end"):
        value = request.args.get(key, "")
        bounds[key] = ""
        if value:
            try:
                parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
                bounds[key] = parsed.strftime("%Y-%m-%dT%H:%M:") + ("00Z" if key == "start" else "59Z")
            except ValueError:
                errors.append(f"Invalid {key} time. Use the UTC date/time control.")
    if bounds["start"] and bounds["end"] and bounds["start"] > bounds["end"]:
        errors.append("Start time must be before end time.")
    return bounds, errors


@admin_preview.get("/manage-documents")
def inventory():
    choices = {"category": CATEGORIES, "format": ("CSV", "TXT")}
    filters = query_options(choices)
    query = request.args.get("q", "")[:120]
    records = filter_records(ADMIN_DOCUMENTS, query, filters)
    return render_template("admin/inventory.html", records=records, query=query,
                           filters=filters, choices=choices, categories=CATEGORIES,
                           total=len(ADMIN_DOCUMENTS))


@admin_preview.get("/manage-documents/<document_id>")
def document_detail(document_id):
    document = DOCUMENT_BY_ID.get(document_id)
    if document is None:
        return missing("Document", "admin_preview.inventory")
    return render_template("admin/document_detail.html", document=document, categories=CATEGORIES)


def list_activity(kind):
    is_alert = kind == "alerts"
    records = ALERTS if is_alert else EVENTS
    keys = ("severity", "status", "action") if is_alert else ("action", "outcome", "actor")
    choices = {key: tuple(sorted({item[key] for item in records})) for key in keys}
    filters = query_options(choices)
    query = request.args.get("q", "")[:120]
    bounds, errors = time_bounds()
    selected = [] if errors else filter_records(records, query, filters, **bounds)
    selected = sorted(selected, key=lambda item: item["timestamp"], reverse=True)
    return render_template("admin/activity.html", kind=kind, records=selected,
                           query=query, choices=choices, filters=filters, errors=errors,
                           documents=DOCUMENT_BY_ID, alerts=ALERTS,
                           counts={severity: sum(alert["severity"] == severity for alert in ALERTS) for severity in ("High", "Medium", "Low")},
                           reviewed=sum(alert["status"] == "Reviewed" for alert in ALERTS))


@admin_preview.get("/alerts")
def alerts():
    return list_activity("alerts")


@admin_preview.get("/events")
def events():
    return list_activity("events")


@admin_preview.get("/alerts/<alert_id>")
def alert_detail(alert_id):
    alert = ALERT_BY_ID.get(alert_id)
    if alert is None:
        return missing("Alert", "admin_preview.alerts")
    return render_template("admin/activity_detail.html", kind="alert", record=alert,
                           document=DOCUMENT_BY_ID[alert["document_id"]],
                           timeline=sorted((EVENT_BY_ID[key] for key in alert["event_ids"]), key=lambda item: item["timestamp"]))


@admin_preview.get("/events/<event_id>")
def event_detail(event_id):
    event = EVENT_BY_ID.get(event_id)
    if event is None:
        return missing("Event", "admin_preview.events")
    return render_template("admin/activity_detail.html", kind="event", record=event,
                           document=DOCUMENT_BY_ID[event["document_id"]],
                           timeline=sorted((item for item in EVENTS if item["request_id"] == event["request_id"]), key=lambda item: item["timestamp"]))


def missing(label, endpoint):
    return render_template("admin/not_found.html", label=label, endpoint=endpoint), 404

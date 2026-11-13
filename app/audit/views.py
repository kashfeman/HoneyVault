"""Bounded read-only view of recorded document operations, separate from fixtures."""
from datetime import datetime, timezone
from uuid import UUID

from flask import Blueprint, abort, render_template, request, url_for
from sqlalchemy import String, cast, or_, select

from ..auth import role_required
from ..extensions import db
from ..models import AuditEvent, Document, User
from .recording import ACTIONS, OUTCOMES

audit = Blueprint("audit", __name__, url_prefix="/dashboard")
PAGE_SIZE = 25
MAX_PAGE = 1000


@audit.get("/document-activity")
@role_required("admin")
def document_activity():
    filters = {key: request.args.get(key, "")[:120].strip()
               for key in ("q", "action", "outcome", "actor", "document", "start", "end")}
    page_text = request.args.get("page", "1")
    if not page_text.isascii() or not page_text.isdecimal() or len(page_text) > 4:
        abort(400)
    page = int(page_text)
    if not 1 <= page <= MAX_PAGE:
        abort(400)
    statement = select(
        AuditEvent.id, AuditEvent.occurred_at, AuditEvent.actor_id,
        User.username, AuditEvent.document_id, Document.filename,
        AuditEvent.action, AuditEvent.outcome,
    ).outerjoin(User, User.id == AuditEvent.actor_id).outerjoin(
        Document, Document.id == AuditEvent.document_id
    ).where(AuditEvent.action.in_(ACTIONS), AuditEvent.rule_id.is_(None))
    for key, choices, column in (("action", ACTIONS, AuditEvent.action),
                                  ("outcome", OUTCOMES, AuditEvent.outcome)):
        if filters[key]:
            if filters[key] not in choices:
                abort(400)
            statement = statement.where(column == filters[key])
    if filters["actor"]:
        actor = filters["actor"]
        if not actor.isascii() or not actor.isdecimal() or len(actor) > 10 or int(actor) < 1:
            abort(400)
        statement = statement.where(AuditEvent.actor_id == int(actor))
    if filters["document"]:
        try:
            if str(UUID(filters["document"])) != filters["document"]:
                abort(400)
        except ValueError:
            abort(400)
        statement = statement.where(AuditEvent.document_id == filters["document"])
    bounds = {}
    for key in ("start", "end"):
        if filters[key]:
            try:
                if len(filters[key]) != 16:
                    abort(400)
                value = datetime.strptime(filters[key], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
            except ValueError:
                abort(400)
            bounds[key] = value if key == "start" else value.replace(second=59, microsecond=999999)
    if len(bounds) == 2 and bounds["start"] > bounds["end"]:
        abort(400)
    if "start" in bounds:
        statement = statement.where(AuditEvent.occurred_at >= bounds["start"])
    if "end" in bounds:
        statement = statement.where(AuditEvent.occurred_at <= bounds["end"])
    if filters["q"]:
        statement = statement.where(or_(*(
            column.icontains(filters["q"], autoescape=True) for column in (
                AuditEvent.id, cast(AuditEvent.actor_id, String), User.username,
                AuditEvent.document_id, Document.filename, AuditEvent.action, AuditEvent.outcome)
        )))
    rows = db.session.execute(statement.order_by(
        AuditEvent.occurred_at.desc(), AuditEvent.id.desc()
    ).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE + 1)).mappings().all()
    return render_template(
        "admin/document_activity.html", records=rows[:PAGE_SIZE], filters=filters,
        actions=ACTIONS, outcomes=OUTCOMES, page=page,
        previous=url_for("audit.document_activity", **filters, page=page - 1) if page > 1 else None,
        following=url_for("audit.document_activity", **filters, page=page + 1)
        if len(rows) > PAGE_SIZE and page < MAX_PAGE else None,
        capped=page == MAX_PAGE and len(rows) > PAGE_SIZE,
    )

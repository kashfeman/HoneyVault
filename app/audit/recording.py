"""Record one server-derived outcome before releasing a document response."""
from functools import wraps
from uuid import UUID

from flask import abort, current_app, make_response
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from ..extensions import db
from ..models import AuditEvent, Document
from ..documents.service import visible_documents

ACTIONS = ("document.list", "document.preview", "document.download")
OUTCOMES = ("success", "denied", "unavailable", "error")


def record_outcome(action, actor_id, document_id, status):
    """Never persist raw URLs, invalid IDs, query text or exception details."""
    try:
        document = None
        if document_id:
            try:
                canonical = str(UUID(document_id)) == document_id
            except (ValueError, AttributeError):
                canonical = False
            if canonical:
                document = db.session.get(Document, document_id)
        outcome = "success" if 200 <= status < 300 else "error"
        if status == 403:
            outcome = "denied"
        elif status == 404:
            eligible = document is not None and db.session.execute(
                visible_documents().where(Document.id == document.id)
            ).scalar_one_or_none() is not None
            outcome = "denied" if document is not None and not eligible else "unavailable"
        db.session.add(AuditEvent(actor_id=actor_id,
                                  document_id=document.id if document else None,
                                  action=action, outcome=outcome))
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        # Exception strings can contain SQL parameters; do not log them.
        current_app.logger.error("Document audit persistence failed; response blocked.")
        abort(503)


def audit_document(action):
    """Wrap outside role_required so authenticated role denials are recorded too."""
    if action not in ACTIONS:
        raise ValueError("Unknown document audit action")

    def decorate(view):
        @wraps(view)
        def audited(*args, **kwargs):
            actor_id = current_user.id if current_user.is_authenticated else None
            document_id = kwargs.get("document_id")
            try:
                response = make_response(view(*args, **kwargs))
            except HTTPException as error:
                if actor_id is not None:
                    record_outcome(action, actor_id, document_id, error.code)
                raise
            except Exception:
                db.session.rollback()
                if actor_id is not None:
                    record_outcome(action, actor_id, document_id, 500)
                raise
            if actor_id is not None:
                try:
                    record_outcome(action, actor_id, document_id, response.status_code)
                except HTTPException:
                    response.close()
                    raise
            return response
        return audited
    return decorate

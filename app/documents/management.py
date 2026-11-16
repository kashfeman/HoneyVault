"""Administrator-only synthetic generation and non-destructive metadata management."""
from hashlib import sha256
import json
import re
from uuid import UUID, uuid4

from flask import abort, current_app, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from ..auth import role_required
from ..extensions import db
from ..models import AuditEvent, Document
from .service import read_document, staged_document

CATEGORIES = ("Finance", "Operations", "People", "Planning")
SENSITIVITIES = ("public", "internal", "confidential", "restricted")
STATUSES = ("active", "archived")
CLASSIFICATIONS = ("normal", "decoy")
CONTENT = {
    "TXT": "FICTIONAL UNIVERSITY DEMONSTRATION\n\nSample project working guide.\nShare a sample agenda and review classroom deliverables.\nNo real business or personal data is represented.\n",
    "CSV": "department,quarter,demo_credits\nFictional Research,Q1,36000\nFictional Operations,Q1,24000\n",
}
FIELDS = ("filename", "category", "format", "is_decoy", "sensitivity", "status", "storage_reference")


def version(document):
    return sha256(json.dumps([document.id] + [getattr(document, key) for key in FIELDS]).encode()).hexdigest()


def admin_record(document):
    # Storage references are never rendered, even in the administrator UI.
    return dict(id=document.id, filename=document.filename, title=document.filename,
                category=document.category, format=document.format,
                classification="decoy" if document.is_decoy else "normal",
                sensitivity=document.sensitivity, status=document.status,
                created="Not recorded", version=version(document))


def find_document(identifier):
    try:
        if str(UUID(identifier)) != identifier:
            abort(404)
    except ValueError:
        abort(404)
    document = db.session.get(Document, identifier)
    if document is None:
        abort(404)
    return document


def form_response(values, errors=(), document=None, status=200):
    return render_template("admin/document_form.html", values=values, errors=errors,
                           document=document, categories=CATEGORIES,
                           sensitivities=SENSITIVITIES, statuses=STATUSES,
                           classifications=CLASSIFICATIONS), status


def validate_form(document=None):
    allowed = {"csrf_token", "filename", "category", "format", "classification",
               "sensitivity", "status", "synthetic_ack"}
    if document:
        allowed.add("version")
    values = {key: request.form.get(key, "") for key in allowed if key != "csrf_token"}
    errors = []
    if request.files or set(request.form) - allowed or any(len(request.form.getlist(key)) != 1 for key in request.form):
        errors.append("Only the displayed fields are accepted. File uploads are unavailable.")
    filename = values["filename"]
    fmt = values["format"]
    if (len(filename) > 80 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,75}\.(csv|txt)", filename, re.IGNORECASE)
            or fmt not in CONTENT or not filename.lower().endswith("." + fmt.lower())):
        errors.append("Use a simple filename ending in the selected CSV/TXT format (at most 80 characters).")
    stem = filename.rsplit(".", 1)[0].upper().rstrip()
    if stem in {"CON", "PRN", "AUX", "NUL", *("COM" + str(n) for n in range(1, 10)), *("LPT" + str(n) for n in range(1, 10))}:
        errors.append("Choose a filename other than a reserved system name.")
    for field, choices in (("category", CATEGORIES), ("sensitivity", SENSITIVITIES),
                           ("status", STATUSES), ("classification", CLASSIFICATIONS)):
        if values[field] not in choices:
            errors.append("Choose a supported " + field + ".")
    if values["synthetic_ack"] != "yes":
        errors.append("Confirm that this is a fictional university demonstration document.")
    if document and fmt != document.format:
        errors.append("An existing document's file format cannot be changed.")
    return values, errors


@role_required("admin")
def inventory():
    choices = {"category": CATEGORIES, "format": tuple(CONTENT), "classification": CLASSIFICATIONS,
               "sensitivity": SENSITIVITIES, "status": STATUSES}
    filters = {key: request.args.get(key, "") for key in choices}
    if any(value and value not in choices[key] for key, value in filters.items()):
        abort(400)
    query = request.args.get("q", "")[:120].strip()
    text = request.args.get("page", "1")
    if not text.isascii() or not text.isdecimal() or len(text) > 4 or not 1 <= int(text) <= 1000:
        abort(400)
    page = int(text)
    statement = select(Document)
    if query:
        statement = statement.where(or_(Document.filename.icontains(query, autoescape=True),
                                        Document.id.icontains(query, autoescape=True)))
    for key, value in filters.items():
        if value:
            statement = statement.where(Document.is_decoy == (value == "decoy") if key == "classification"
                                        else getattr(Document, key) == value)
    rows = db.session.execute(statement.order_by(Document.filename, Document.id)
                              .offset((page - 1) * 25).limit(26)).scalars().all()
    return render_template("admin/inventory.html", managed=True,
                           records=[admin_record(d) for d in rows[:25]], query=query,
                           choices=choices, filters=filters, categories=CATEGORIES,
                           page=page, previous=url_for("admin_preview.inventory", **filters, q=query, page=page - 1) if page > 1 else None,
                           following=url_for("admin_preview.inventory", **filters, q=query, page=page + 1) if len(rows) > 25 and page < 1000 else None)


@role_required("admin")
def detail(document_id):
    document = find_document(document_id)
    record = admin_record(document)
    try:
        record["content"] = read_document(document).decode("utf-8")
    except HTTPException as error:
        if error.code != 404:
            raise
        record["content"] = None
    return render_template("admin/document_detail.html", managed=True, document=record,
                           categories=CATEGORIES)


@role_required("admin")
def create_document():
    if request.method == "GET":
        return form_response(dict(filename="", category="People", format="TXT",
                                  classification="normal", sensitivity="internal", status="archived"))
    values, errors = validate_form()
    if errors:
        return form_response(values, errors, status=400)
    identifier = str(uuid4())
    reference = identifier + "." + values["format"].lower()
    data = CONTENT[values["format"]].encode("utf-8")
    try:
        if len(data) > current_app.config["DOCUMENT_MAX_BYTES"]:
            return form_response(values, ["Generated document exceeds the configured size limit."], status=400)
        with staged_document(reference, data) as publish:
            document = Document(id=identifier, filename=values["filename"], category=values["category"],
                                format=values["format"], is_decoy=values["classification"] == "decoy",
                                sensitivity=values["sensitivity"], status=values["status"], storage_reference=reference)
            db.session.add(document)
            db.session.add(AuditEvent(actor_id=current_user.id, document=document,
                                      action="document.create", outcome="success"))
            db.session.flush()
            publish()
            db.session.commit()
    except (OSError, ValueError, SQLAlchemyError):
        db.session.rollback()
        current_app.logger.error("Synthetic document creation failed.")
        abort(503)
    return redirect(url_for("admin_preview.document_detail", document_id=identifier), code=303)


@role_required("admin")
def edit_document(document_id):
    document = find_document(document_id)
    record = admin_record(document)
    if request.method == "GET":
        return form_response(record, document=record)
    values, errors = validate_form(document)
    if errors:
        return form_response(values, errors, document=record, status=400)
    if values["version"] != version(document):
        return form_response(record, ["This record changed. Review the current values and submit again."], document=record, status=409)
    original = {key: getattr(document, key) for key in FIELDS}
    try:
        result = db.session.execute(update(Document).where(Document.id == document.id,
            *(getattr(Document, key) == value for key, value in original.items())).values(
                filename=values["filename"], category=values["category"],
                is_decoy=values["classification"] == "decoy", sensitivity=values["sensitivity"], status=values["status"])
            .execution_options(synchronize_session=False))
        if result.rowcount != 1:
            db.session.rollback()
            abort(409)
        db.session.add(AuditEvent(actor_id=current_user.id, document_id=document.id,
                                  action="document.update", outcome="success"))
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.error("Document metadata update failed.")
        abort(503)
    return redirect(url_for("admin_preview.document_detail", document_id=document_id), code=303)


def register_management(app):
    # Replace only this application's fixture views; the public preview stays unchanged.
    app.view_functions["admin_preview.inventory"] = inventory
    app.view_functions["admin_preview.document_detail"] = detail
    app.add_url_rule("/dashboard/manage-documents/new", "document_create", create_document, methods=["GET", "POST"])
    app.add_url_rule("/dashboard/manage-documents/<document_id>/edit", "document_edit", edit_document, methods=["GET", "POST"])

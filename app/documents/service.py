"""Private, bounded document reads and employee-safe presentation records."""
from pathlib import Path
import re
import stat
from uuid import UUID

from flask import abort, current_app
from sqlalchemy import select, or_

from ..extensions import db
from ..models import Document

SORTS = {"title": "Filename A–Z", "title_desc": "Filename Z–A", "category": "Category", "format": "Format"}


def visible_documents():
    # Shared library policy; classification is deliberately irrelevant.
    return select(Document).where(Document.status == "active",
                                  Document.sensitivity.in_(("public", "internal")),
                                  Document.format.in_(("CSV", "TXT")))


def public_record(document):
    # Explicit allowlist: never pass an ORM record to employee templates.
    return {"id": document.id, "title": document.filename,
            "category": document.category, "format": document.format}


def library_data(args):
    query = args.get("q", "")[:120].strip()
    category = args.get("category", "")[:80]
    sort = args.get("sort", "title")
    sort = sort if sort in SORTS else "title"
    base = visible_documents()
    categories = list(db.session.execute(base.with_only_columns(Document.category).distinct().order_by(Document.category)).scalars())
    total = db.session.execute(select(db.func.count()).select_from(base.subquery())).scalar_one()
    if query:
        base = base.where(or_(Document.filename.icontains(query, autoescape=True),
                              Document.category.icontains(query, autoescape=True),
                              Document.format.icontains(query, autoescape=True)))
    if category:
        base = base.where(Document.category == category)
    ordering = {"title": Document.filename.asc(), "title_desc": Document.filename.desc(),
                "category": Document.category.asc(), "format": Document.format.asc()}
    records = db.session.execute(base.order_by(ordering[sort], Document.filename, Document.id)).scalars()
    return dict(documents=[public_record(item) for item in records], categories=categories,
                total=total, query=query, category=category, sort=sort, sorts=SORTS)


def get_document(document_id):
    try:
        if str(UUID(document_id)) != document_id:
            abort(404)
    except (ValueError, AttributeError):
        abort(404)
    document = db.session.execute(visible_documents().where(Document.id == document_id)).scalar_one_or_none()
    if document is None:
        abort(404)
    return document


def storage_root():
    root = Path(current_app.config["DOCUMENT_STORAGE_ROOT"]).resolve()
    static = Path(current_app.static_folder).resolve()
    # Also reject ancestors of static: no overlap with public storage.
    if root == static or static in root.parents or root in static.parents:
        raise ValueError("Document storage must be separate from static assets")
    return root


def read_document(document):
    """Only flat application-managed names; reject links, devices and oversize files."""
    reference = document.storage_reference
    extension = document.format.lower()
    if (document.format not in ("CSV", "TXT") or
            not re.fullmatch(r"[A-Za-z0-9_-]+\.(csv|txt)", reference) or
            not reference.endswith("." + extension) or
            Path(document.filename).suffix.lower() != "." + extension):
        abort(404)
    try:
        root = storage_root()
        path = root / reference
        if path.is_symlink() or path.resolve().parent != root:
            abort(404)
        limit = current_app.config["DOCUMENT_MAX_BYTES"]
        if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size > limit:
            abort(404)
        with path.open("rb") as source:
            data = source.read(limit + 1)
        if len(data) > limit or b"\0" in data:
            abort(404)
        data.decode("utf-8")
        return data
    except (OSError, ValueError, UnicodeError):
        abort(404)

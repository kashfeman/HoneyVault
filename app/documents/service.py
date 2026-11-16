"""Private, bounded document reads and employee-safe presentation records."""
from pathlib import Path
from contextlib import contextmanager
import os
import re
import stat
import tempfile
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


def _remove_owned_file(path, identity, root):
    """Never sweep storage or unlink a collision/replacement owned by another operation."""
    try:
        if path.parent.resolve() != root:
            current_app.logger.error("Document cleanup refused a changed storage directory.")
            return
        actual = path.lstat()
        if stat.S_ISREG(actual.st_mode) and os.path.samestat(actual, identity):
            path.unlink()
        else:
            current_app.logger.error("Document cleanup preserved a file with changed ownership.")
    except FileNotFoundError:
        pass
    except OSError:
        # Do not expose paths or mask the original transaction failure.
        current_app.logger.error("Owned document file cleanup failed; operator review required.")


@contextmanager
def staged_document(reference, data):
    """Publish complete bytes atomically without overwrite; compensate handled failures.

    The caller must flush its new row, call publish(), then commit inside this
    context. A hard link is an atomic no-clobber publication on NTFS/POSIX local
    filesystems. os.replace/ordinary POSIX rename could overwrite an existing file.
    """
    try:
        stem, extension = reference.rsplit(".", 1)
        valid = str(UUID(stem)) == stem and extension in ("csv", "txt")
    except (ValueError, AttributeError):
        valid = False
    if not valid or len(data) > current_app.config["DOCUMENT_MAX_BYTES"]:
        raise ValueError("Invalid managed document")
    root = storage_root()
    root.mkdir(parents=True, exist_ok=True)
    final = root / reference
    pending = identity = None
    published = committed = False

    def publish():
        nonlocal published
        if published or not os.path.samestat(pending.lstat(), identity) or pending.is_symlink():
            raise ValueError("Invalid staging state")
        os.link(pending, final, follow_symlinks=False)
        published = True

    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix=".hv-create-", suffix=".tmp",
                                         dir=root, delete=False) as destination:
            pending = Path(destination.name)
            identity = os.fstat(destination.fileno())
            destination.write(data)
            destination.flush()
            os.fsync(destination.fileno())
        yield publish
        if not published:
            raise ValueError("Document was not published")
        committed = True
    finally:
        if pending is not None and identity is not None:
            if published and not committed:
                _remove_owned_file(final, identity, root)
            _remove_owned_file(pending, identity, root)


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

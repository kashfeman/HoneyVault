"""Explicit local-only, non-destructive synthetic document provisioning."""
from uuid import UUID, uuid5
from pathlib import Path
import click
from sqlalchemy import select
from ..extensions import db
from ..models import Document
from .service import storage_root

# No credentials or real personal data. Security classifications stay server-side.
EXAMPLES = (
    ("Team handbook.txt", "People", "TXT", False,
     "FICTIONAL UNIVERSITY DEMONSTRATION\nShare an agenda before sample team meetings.\n"),
    ("Workshop schedule.csv", "Operations", "CSV", False,
     "workshop,room,capacity\nSample orientation,Demo Room A,20\n"),
    ("Quarterly forecast.csv", "Finance", "CSV", True,
     "department,quarter,demo_credits\nFictional Research,Q1,36000\n"),
    ("Project roadmap.txt", "Planning", "TXT", True,
     "FICTIONAL UNIVERSITY DEMONSTRATION\nAurora sample project: classroom prototype review.\n"),
)


def init_documents(app):
    app.config.setdefault("DOCUMENT_STORAGE_ROOT", str(Path(app.instance_path) / "documents"))
    app.config.setdefault("DOCUMENT_MAX_BYTES", 1024 * 1024)

    @app.cli.command("seed-demo-documents")
    def seed():
        """Add fictional documents without changing existing rows or files."""
        root = storage_root()
        root.mkdir(parents=True, exist_ok=True)
        added = 0
        for filename, category, fmt, decoy, content in EXAMPLES:
            identifier = str(uuid5(UUID("edb01be1-1952-4b4e-9123-f5681d6a3392"), filename))
            reference = identifier + "." + fmt.lower()
            if db.session.get(Document, identifier) or db.session.execute(select(Document.id).where(Document.storage_reference == reference)).first():
                continue
            data = content.encode("utf-8")
            if len(data) > app.config["DOCUMENT_MAX_BYTES"]:
                raise click.ClickException("Demo exceeds configured document size limit.")
            try:
                with (root / reference).open("xb") as destination:
                    destination.write(data)
            except FileExistsError:
                click.echo("Existing file preserved; example skipped.")
                continue
            db.session.add(Document(id=identifier, filename=filename, category=category,
                                    format=fmt, is_decoy=decoy, sensitivity="internal",
                                    storage_reference=reference, status="active"))
            added += 1
        db.session.commit()
        click.echo(f"Added {added} fictional documents; existing rows and files preserved.")

"""Local, public UI preview. No authentication, persistence, or detection."""

from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

if __package__:
    from .frontend_data import CATEGORIES, DOCUMENTS, SORTS, select_documents
else:
    from frontend_data import CATEGORIES, DOCUMENTS, SORTS, select_documents


def create_preview_app():
    root = Path(__file__).resolve().parents[1] / "app"
    app = Flask(__name__, template_folder=str(root / "templates"),
                static_folder=str(root / "static"))

    @app.get("/")
    def index():
        return redirect(url_for("login"))

    @app.get("/login")
    def login():
        return render_template("auth/login.html")

    @app.get("/dashboard")
    def dashboard():
        # Fixed fictional fixtures, deliberately separate from future business logic.
        events = [
            dict(id="DEMO-008", actor="Demo analyst 04", action="Preview requested", document="Decoy budget · Q4", time="14:42 UTC", severity="high"),
            dict(id="DEMO-007", actor="Demo analyst 02", action="Document viewed", document="Sample project brief", time="14:38 UTC", severity="low"),
            dict(id="DEMO-006", actor="Demo analyst 07", action="Repeated preview", document="Decoy vendor register", time="14:31 UTC", severity="medium"),
            dict(id="DEMO-005", actor="Demo analyst 04", action="Document viewed", document="Sample team handbook", time="14:24 UTC", severity="low"),
        ]
        return render_template("dashboard/index.html", events=events)

    @app.get("/employee")
    def employee():
        return render_template("employee/index.html", documents=DOCUMENTS[:3],
                               total=len(DOCUMENTS), categories=CATEGORIES)

    @app.get("/employee/documents")
    @app.get("/dashboard/documents")
    def library():
        admin = request.path.startswith("/dashboard/")
        query = request.args.get("q", "")[:120]
        category = request.args.get("category", "")
        category = category if category in CATEGORIES else ""
        sort = request.args.get("sort", "newest")
        sort = sort if sort in SORTS else "newest"
        return render_template("documents/library.html", admin=admin,
                               layout="layouts/dashboard.html" if admin else "layouts/employee.html",
                               documents=select_documents(query, category, sort),
                               categories=CATEGORIES, sorts=SORTS, query=query,
                               category=category, sort=sort, total=len(DOCUMENTS))

    @app.get("/employee/documents/<document_id>")
    @app.get("/dashboard/documents/<document_id>")
    def document_preview(document_id):
        admin = request.path.startswith("/dashboard/")
        document = next((item for item in DOCUMENTS if item["id"] == document_id), None)
        if document is None:
            return render_template("documents/not_found.html", admin=admin,
                                   layout="layouts/dashboard.html" if admin else "layouts/employee.html"), 404
        return render_template("documents/preview.html", document=document, admin=admin,
                               layout="layouts/dashboard.html" if admin else "layouts/employee.html")

    return app


if __name__ == "__main__":
    create_preview_app().run(host="127.0.0.1", port=5000, debug=False)

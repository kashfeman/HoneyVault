"""Local, public UI preview. No authentication, persistence, or detection."""

from pathlib import Path
import os
import socket

from flask import Flask, redirect, render_template, request, url_for

if __package__:
    from .frontend_data import CATEGORIES, DOCUMENTS, SORTS, select_documents
    from .admin_demo_data import dashboard_snapshot
    from .admin_preview import admin_preview
else:
    from frontend_data import CATEGORIES, DOCUMENTS, SORTS, select_documents
    from admin_demo_data import dashboard_snapshot
    from admin_preview import admin_preview


def create_preview_app():
    root = Path(__file__).resolve().parents[1] / "app"
    app = Flask(__name__, template_folder=str(root / "templates"),
                static_folder=str(root / "static"))
    app.register_blueprint(admin_preview)

    @app.errorhandler(404)
    def page_not_found(error):
        # Recovery stays in the current workspace; no exception/path is displayed.
        employee_view = request.path.startswith("/employee/")
        admin_view = request.path.startswith("/dashboard/")
        layout = "layouts/employee.html" if employee_view else "layouts/dashboard.html" if admin_view else "layouts/base.html"
        return render_template("errors/not_found.html", layout=layout,
                               workspace=employee_view or admin_view,
                               home="employee" if employee_view else "dashboard" if admin_view else "login"), 404

    @app.get("/")
    def index():
        return redirect(url_for("login"))

    @app.get("/login")
    def login():
        return render_template("auth/login.html")

    @app.get("/dashboard")
    def dashboard():
        return render_template("dashboard/index.html", **dashboard_snapshot())

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


def check_preview_port(host, port):
    """Reject an occupied port before Werkzeug can reuse it on Windows."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind((host, port))
        except OSError as error:
            raise SystemExit(
                f"Cannot start HoneyVault at http://{host}:{port}: {error}.\n"
                "Stop the existing preview with Ctrl+C in its terminal, then restart. "
                "A running preview does not reload changed Python routes."
            ) from error


def main():
    host, port = "127.0.0.1", 5000
    check_preview_port(host, port)
    app = create_preview_app()
    print(f"HoneyVault preview | PID {os.getpid()} | {Path(__file__).resolve()}", flush=True)
    print("Code reload is OFF. Restart this process after Python route changes.", flush=True)
    for rule in sorted(app.url_map.iter_rules(), key=lambda item: item.rule):
        if rule.endpoint.startswith("admin_preview."):
            print(f"  GET http://{host}:{port}{rule.rule}", flush=True)
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()

"""Authenticated presentation routes; no document or administrator operations."""
from flask import abort, redirect, render_template, request, url_for
from flask_login import current_user
from .auth import role_required
from scripts.frontend_data import CATEGORIES, DOCUMENTS, SORTS, select_documents
from scripts.admin_preview import admin_preview
from scripts.admin_demo_data import dashboard_snapshot


def register_workspaces(app):
    # Apply the policy to every administrator blueprint view in this app only.
    # Never mutate the shared preview blueprint or its public preview factory.
    app.register_blueprint(admin_preview)
    for endpoint in list(app.view_functions):
        if endpoint.startswith("admin_preview."):
            app.view_functions[endpoint] = role_required("admin")(app.view_functions[endpoint])

    @app.get("/")
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for("login"))
        return redirect(url_for("dashboard" if current_user.role == "admin" else "employee"))

    @app.get("/dashboard")
    @role_required("admin")
    def dashboard():
        return render_template("dashboard/index.html", **dashboard_snapshot())

    @app.get("/employee")
    @role_required("employee")
    def employee():
        return render_template("employee/index.html", documents=DOCUMENTS[:3],
                               total=len(DOCUMENTS), categories=CATEGORIES)

    @app.get("/employee/documents", endpoint="library")
    @role_required("employee")
    def library():
        return library_response(False)

    @app.get("/dashboard/documents")
    @role_required("admin")
    def admin_library():
        return library_response(True)

    def library_response(admin):
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
    @role_required("employee")
    def document_preview(document_id):
        return preview_response(document_id, False)

    @app.get("/dashboard/documents/<document_id>")
    @role_required("admin")
    def admin_document_preview(document_id):
        return preview_response(document_id, True)

    def preview_response(document_id, admin):
        document = next((item for item in DOCUMENTS if item["id"] == document_id), None)
        if document is None:
            abort(404)
        return render_template("documents/preview.html", document=document, admin=admin,
                               layout="layouts/dashboard.html" if admin else "layouts/employee.html")

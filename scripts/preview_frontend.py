"""Local, public UI preview. No authentication, persistence, or detection."""

from pathlib import Path

from flask import Flask, redirect, render_template, url_for


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

    return app


if __name__ == "__main__":
    create_preview_app().run(host="127.0.0.1", port=5000, debug=False)

"""Authentication and role boundaries with real CSRF and isolated SQLite."""
from datetime import timedelta
import re
import secrets

import pytest
from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models import AuthSession, User, Document, utc_now


@pytest.fixture
def auth_app(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": secrets.token_hex(32),
                      "SESSION_COOKIE_SECURE": False,
                      "DOCUMENT_STORAGE_ROOT": str(tmp_path / "documents"),
                      "SQLALCHEMY_DATABASE_URI": "sqlite:///" + (tmp_path / "auth.sqlite3").as_posix()})
    assert app.test_cli_runner().invoke(args=["init-db"]).exit_code == 0
    assert app.test_cli_runner().invoke(args=["seed-demo-documents"]).exit_code == 0
    passwords = {}
    with app.app_context():
        for name, role, active in [("employee", "employee", True), ("administrator", "admin", True), ("inactive", "employee", False)]:
            passwords[name] = secrets.token_urlsafe(24)
            user = User(username=name, role=role, is_active=active)
            user.set_password(passwords[name])
            db.session.add(user)
        db.session.commit()
    app.test_passwords = passwords
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def csrf(client, path="/login"):
    response = client.get(path)
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match, response.get_data(as_text=True)
    return match.group(1)


def sign_in(app, client, name="employee", **extra):
    values = {"username": name, "password": app.test_passwords.get(name, secrets.token_urlsafe(24)),
              "csrf_token": csrf(client)}
    values.update(extra)
    return client.post("/login", data=values)


def test_login_rotation_logout_revocation(auth_app):
    client = auth_app.test_client()
    token = csrf(client)
    with client.session_transaction() as saved:
        saved["injected"] = "discard-me"
        old_csrf = saved["csrf_token"]
    result = client.post("/login", data={"username": "employee", "password": auth_app.test_passwords["employee"], "csrf_token": token})
    assert result.status_code == 302 and result.location == "/employee"
    cookie_name = auth_app.config["SESSION_COOKIE_NAME"]
    old_cookie = client.get_cookie(cookie_name).value
    assert "HttpOnly" in result.headers["Set-Cookie"] and "SameSite=Lax" in result.headers["Set-Cookie"]
    with client.session_transaction() as saved:
        assert "injected" not in saved and saved["_user_id"]
        assert "password" not in saved and "role" not in saved
    new_csrf = csrf(client, "/employee")
    with client.session_transaction() as saved:
        assert saved["csrf_token"] != old_csrf
    assert client.get("/logout").status_code == 405
    assert client.post("/logout").status_code == 400
    assert client.get("/employee").status_code == 200
    assert client.post("/logout", data={"csrf_token": new_csrf}).location == "/login"
    assert client.get("/employee").location == "/login"
    replay = auth_app.test_client()
    replay.set_cookie(cookie_name, old_cookie)
    assert replay.get("/employee").location == "/login"
    with auth_app.app_context():
        assert db.session.execute(select(AuthSession)).scalars().all() == []


@pytest.mark.parametrize("name", ["employee", "unknown", "inactive"])
def test_generic_failed_login(auth_app, name):
    client = auth_app.test_client()
    password = auth_app.test_passwords["inactive"] if name == "inactive" else secrets.token_urlsafe(24)
    response = sign_in(auth_app, client, name, password=password)
    assert response.status_code == 401
    assert "Unable to sign in. Check your credentials and try again." in response.text
    assert password not in response.text
    assert client.get("/employee").location == "/login"


def test_csrf_validation_and_configuration(auth_app):
    client = auth_app.test_client()
    values = {"username": "employee", "password": auth_app.test_passwords["employee"]}
    assert client.post("/login", data=values).status_code == 400
    assert client.post("/login", data={**values, "csrf_token": "invalid"}).status_code == 400
    token = csrf(client)
    another = auth_app.test_client()
    assert another.post("/login", data={**values, "csrf_token": token}).status_code == 400
    auth_app.config["WTF_CSRF_TIME_LIMIT"] = -1
    assert client.post("/login", data={**values, "csrf_token": token}).status_code == 400
    auth_app.config["SECRET_KEY"] = None
    assert client.get("/login").status_code == 503
    assert client.get("/health").json == {"status": "ok"}


@pytest.mark.parametrize("role", ["employee", "administrator"])
def test_role_boundaries_and_all_admin_routes(auth_app, role):
    client = auth_app.test_client()
    admin_paths = ["/dashboard", "/dashboard/documents", "/dashboard/documents/doc-101",
                   "/dashboard/manage-documents", "/dashboard/manage-documents/doc-101",
                   "/dashboard/alerts", "/dashboard/alerts/ALERT-001",
                   "/dashboard/events", "/dashboard/events/DEMO-008"]
    with auth_app.app_context():
        ids = list(db.session.execute(select(Document.id)).scalars())
    employee_paths = ["/employee", "/employee/documents"] + [
        f"/employee/documents/{identifier}{tail}" for identifier in ids for tail in ("", "/download")]
    for path in admin_paths + employee_paths:
        assert client.get(path + "?role=admin&password=private").location == "/login"
    response = sign_in(auth_app, client, role, role="admin", user_id="1", next="https://untrusted.example/")
    assert response.location == ("/dashboard" if role == "administrator" else "/employee")
    for path in admin_paths:
        assert client.get(path).status_code == (200 if role == "administrator" else 403), path
    for path in employee_paths:
        result = client.get(path)
        assert result.status_code == (403 if role == "administrator" else 200), path
        if role == "employee":
            assert "is_decoy" not in result.text and "sensitivity" not in result.text
            assert "classification" not in result.text.lower()
            assert "password_hash" not in result.text and "ALERT-001" not in result.text
            assert "No account or access protection" not in result.text
            assert "opens without an account" not in result.text
            assert "no authentication" not in result.text.lower()
            assert result.headers["Cache-Control"] == "no-store"
    # Role changes are loaded from the database on every request.
    with auth_app.app_context():
        user = db.session.execute(select(User).where(User.username == role)).scalar_one()
        user.role = "employee" if role == "administrator" else "admin"
        db.session.commit()
    assert client.get("/dashboard").status_code == (403 if role == "administrator" else 200)


@pytest.mark.parametrize("next_url", ["https://untrusted.example", "//untrusted.example", "/\\untrusted.example", "/dashboard?role=admin", "javascript:alert(1)"])
def test_next_is_ignored(auth_app, next_url):
    client = auth_app.test_client()
    token = csrf(client, "/login?next=" + next_url)
    response = client.post("/login?next=" + next_url, data={"username": "employee", "password": auth_app.test_passwords["employee"], "csrf_token": token, "next": next_url})
    assert response.location == "/employee"


def test_session_expiry_and_deactivation(auth_app):
    client = auth_app.test_client()
    sign_in(auth_app, client)
    with auth_app.app_context():
        record = db.session.execute(select(AuthSession)).scalar_one()
        record.expires_at = utc_now() - timedelta(seconds=1)
        db.session.commit()
    assert client.get("/employee").location == "/login"
    sign_in(auth_app, client)
    with auth_app.app_context():
        user = db.session.execute(select(User).where(User.username == "employee")).scalar_one()
        user.is_active = False
        db.session.commit()
    assert client.get("/employee").location == "/login"


def test_login_rate_limit(auth_app):
    client = auth_app.test_client()
    token = csrf(client)
    for _ in range(10):
        result = client.post("/login", data={"username": "unknown", "password": secrets.token_urlsafe(24), "csrf_token": token})
        assert result.status_code == 401
    assert client.post("/login", data={"username": "employee", "password": auth_app.test_passwords["employee"], "csrf_token": token}).status_code == 429
    assert client.get("/login").status_code == 200
    # A changed username or forged forwarding header cannot bypass the source-IP limit.
    assert client.post("/login", headers={"X-Forwarded-For": "192.0.2.1"}, data={"csrf_token": token}).status_code == 429


def test_cli_accounts_and_cookie_configuration(auth_app, monkeypatch):
    runner = auth_app.test_cli_runner()
    password = secrets.token_urlsafe(24)
    result = runner.invoke(args=["create-user", "--username", "synthetic-cli", "--role", "admin"], input=password + "\n" + password + "\n")
    assert result.exit_code == 0, result.output
    assert password not in result.output
    with auth_app.app_context():
        user = db.session.execute(select(User).where(User.username == "synthetic-cli")).scalar_one()
        assert user.role == "admin" and user.check_password(password)
        assert user.password_hash != password
    assert runner.invoke(args=["create-user", "--username", "synthetic-cli"]).exit_code != 0
    assert runner.invoke(args=["create-user", "--username", "../bad"]).exit_code != 0
    assert runner.invoke(args=["create-user", "--username", "other", "--role", "superuser"]).exit_code != 0
    short = secrets.token_hex(2)
    assert runner.invoke(args=["create-user", "--username", "short"], input=short + "\n" + short + "\n").exit_code != 0
    mismatch = runner.invoke(args=["create-user", "--username", "mismatch"], input=password + "\n" + secrets.token_urlsafe(24) + "\n")
    assert mismatch.exit_code != 0
    monkeypatch.setenv("HONEYVAULT_ENV", "development")
    assert create_app().config["SESSION_COOKIE_SECURE"] is False
    monkeypatch.setenv("HONEYVAULT_ENV", "production")
    production = create_app({"SECRET_KEY": secrets.token_hex(32)})
    response = production.test_client().get("/login", base_url="https://localhost")
    assert "Secure" in response.headers["Set-Cookie"]
    assert "Strict-Transport-Security" in response.headers
    assert production.config["PERMANENT_SESSION_LIFETIME"] == timedelta(minutes=30)


def test_cookie_tampering_and_no_write_routes(auth_app):
    client = auth_app.test_client()
    sign_in(auth_app, client, "administrator")
    token = csrf(client, "/dashboard")
    for path in ("/dashboard/manage-documents", "/dashboard/alerts", "/dashboard/events"):
        assert client.post(path, data={"csrf_token": token}).status_code == 405
    assert client.get("/register").status_code == 404
    assert client.get("/static/css/main.css").status_code == 200
    cookie_name = auth_app.config["SESSION_COOKIE_NAME"]
    cookie = client.get_cookie(cookie_name).value
    client.set_cookie(cookie_name, "tampered" + cookie)
    assert client.get("/dashboard").location == "/login"

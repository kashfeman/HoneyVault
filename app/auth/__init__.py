"""Login, revocable sessions, CSRF and reusable server-side role policy."""
from functools import wraps
from hashlib import sha256
import re
import secrets

import click
from flask import abort, redirect, render_template, request, session, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, CSRFError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..models import AuthSession, User, utc_now


def token_digest(token):
    return sha256(token.encode()).hexdigest()


def revoke_session():
    token = session.get("auth_token")
    if isinstance(token, str):
        db.session.execute(delete(AuthSession).where(AuthSession.token_hash == token_digest(token)))
        db.session.commit()


def role_required(role):
    def decorate(view):
        @wraps(view)
        @login_required
        def guarded(*args, **kwargs):
            if current_user.role != role:
                abort(403)
            return view(*args, **kwargs)
        return guarded
    return decorate


def init_auth(app):
    app.config["AUTHENTICATED_APP"] = True
    manager = LoginManager()
    manager.session_protection = "strong"
    manager.init_app(app)
    # Random dummy hash gives unknown users the same expensive verification path.
    dummy_hash = generate_password_hash(secrets.token_urlsafe(32))

    @app.before_request
    def require_auth_configuration():
        if request.endpoint not in ("health", "static", None):
            if not app.secret_key or len(app.secret_key) < 32:
                abort(503)

    csrf = CSRFProtect(app)
    limiter = Limiter(get_remote_address, storage_uri=app.config["RATELIMIT_STORAGE_URI"])
    limiter.init_app(app)

    @manager.user_loader
    def load_user(user_id):
        token = session.get("auth_token")
        if not isinstance(token, str) or not user_id.isdecimal():
            return None
        saved = db.session.get(AuthSession, token_digest(token))
        if not saved or saved.user_id != int(user_id) or saved.expires_at <= utc_now():
            session.clear()
            return None
        user = db.session.get(User, saved.user_id)
        if not user or not user.is_active:
            revoke_session()
            session.clear()
            return None
        return user

    @manager.unauthorized_handler
    def anonymous():
        # Do not echo the original query or path into a redirect URL.
        return redirect(url_for("login"))

    @app.context_processor
    def authenticated_context():
        return {"authenticated_app": True}

    @app.after_request
    def security_headers(response):
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template("auth/error.html", title="Form expired",
                               message="The form could not be verified. Reload the page and try again."), 400

    for code, title, message in [
        (403, "Access denied", "Your account cannot access this workspace."),
        (404, "Page not found", "This page is unavailable."),
        (429, "Please wait", "Too many sign-in attempts. Try again later."),
        (503, "Sign-in unavailable", "The application requires secure local configuration."),
    ]:
        def safe_error(error, title=title, message=message, code=code):
            return render_template("auth/error.html", title=title, message=message), code
        app.register_error_handler(code, safe_error)

    @app.route("/login", methods=["GET", "POST"])
    @limiter.limit("10 per minute; 50 per hour", methods=["POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard" if current_user.role == "admin" else "employee"))
        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = db.session.execute(select(User).where(User.username == username)).scalar_one_or_none() if len(username) <= 80 else None
            valid = (user.check_password(password) if user else check_password_hash(dummy_hash, password)) if len(password) <= 1024 else False
            if valid and user and user.is_active:
                revoke_session()
                session.clear()
                token = secrets.token_urlsafe(32)
                # Opportunistically prune expired authentication records.
                db.session.execute(delete(AuthSession).where(AuthSession.expires_at <= utc_now()))
                db.session.add(AuthSession(token_hash=token_digest(token), user_id=user.id,
                                           expires_at=utc_now() + app.permanent_session_lifetime))
                db.session.commit()
                session["auth_token"] = token
                session.permanent = True
                login_user(user, remember=False, fresh=True)
                # Deliberately ignore all next/role/user parameters. Fixed role landing pages.
                return redirect(url_for("dashboard" if user.role == "admin" else "employee"))
            error = "Unable to sign in. Check your credentials and try again."
        return render_template("auth/login.html", error=error), 401 if error else 200

    @app.post("/logout")
    @login_required
    def logout():
        revoke_session()
        logout_user()
        session.clear()
        return redirect(url_for("login"))

    @app.cli.command("create-user")
    @click.option("--username", prompt=True)
    @click.option("--role", type=click.Choice(["admin", "employee"]), default="employee", show_default=True)
    def create_user(username, role):
        """Create a synthetic local account. Passwords are accepted only by hidden prompt."""
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", username):
            raise click.ClickException("Use 1-80 letters, digits, dots, underscores or hyphens.")
        if db.session.execute(select(User.id).where(User.username == username)).first():
            raise click.ClickException("Username is already in use; no changes made.")
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
        if not 12 <= len(password) <= 1024:
            raise click.ClickException("Use a password between 12 and 1024 characters.")
        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise click.ClickException("Account could not be created; no changes made.") from None
        click.echo("Local account created.")

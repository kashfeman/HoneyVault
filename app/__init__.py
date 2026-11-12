"""Backend factory, separate from the public frontend preview."""
from pathlib import Path
import click
from flask import Flask
from .config import DevelopmentConfig, TestingConfig
from .extensions import db


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(DevelopmentConfig)
    app.config.update(DevelopmentConfig.environment())
    if config == "testing":
        app.config.from_object(TestingConfig)
    elif isinstance(config, dict):
        app.config.update(config)
    elif config is not None:
        app.config.from_object(config)
    db.init_app(app)
    from . import models  # Register metadata, without creating tables or data.
    from .auth import init_auth
    from .workspaces import register_workspaces
    init_auth(app)
    register_workspaces(app)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.cli.command("init-db")
    def init_db():
        """Create missing tables, preserving existing records."""
        if db.engine.url.database not in (None, ":memory:"):
            Path(db.engine.url.database).parent.mkdir(parents=True, exist_ok=True)
        db.create_all()
        click.echo("Database initialized; existing records preserved.")

    return app

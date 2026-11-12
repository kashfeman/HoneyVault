"""Milestone 6 contracts using isolated, persistent temporary SQLite files."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError, StatementError

from app import create_app
from app.extensions import db
from app.models import Alert, AuditEvent, DetectionRule, Document, User, alert_events


@pytest.fixture
def backend(tmp_path):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI":
                      "sqlite:///" + (tmp_path / "nested" / "test.sqlite3").as_posix()})
    result = app.test_cli_runner().invoke(args=["init-db"])
    assert result.exit_code == 0, result.output
    with app.app_context():
        yield app
        db.session.remove()
        db.engine.dispose()


def sample_user():
    user = User(username="fictional-test-user")
    user.set_password("test-only-password")
    return user


def test_factory_configuration_and_health(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "test-only-environment-value")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "not-created.sqlite3"))
    app = create_app()
    assert not app.debug and not app.testing
    assert app.config["SECRET_KEY"] == "test-only-environment-value"
    assert app.config["SESSION_COOKIE_HTTPONLY"]
    assert app.config["SESSION_COOKIE_SECURE"]
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert not (tmp_path / "not-created.sqlite3").exists()
    client = app.test_client()
    assert client.get("/health").json == {"status": "ok"}
    assert "Set-Cookie" not in client.get("/health").headers
    assert client.post("/health").status_code == 405
    assert {r.rule for r in app.url_map.iter_rules()} == {"/health"}
    for path in ("/login", "/dashboard", "/dashboard/events", "/documents", "/static/test.sqlite3"):
        assert client.get(path).status_code == 404
    monkeypatch.delenv("SECRET_KEY")
    assert create_app().secret_key is None
    testing = create_app("testing")
    assert testing.testing
    assert testing.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def test_initialization_repeatable_persistent_and_empty(backend):
    assert set(inspect(db.engine).get_table_names()) == {
        "user", "document", "audit_event", "detection_rule", "alert", "alert_events"}
    for table in db.metadata.sorted_tables:
        assert db.session.execute(select(db.func.count()).select_from(table)).scalar_one() == 0
    user = sample_user()
    db.session.add(user)
    db.session.commit()
    assert backend.test_cli_runner().invoke(args=["init-db"]).exit_code == 0
    uri = backend.config["SQLALCHEMY_DATABASE_URI"]
    other = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": uri})
    with other.app_context():
        assert db.session.execute(select(User)).scalar_one().username == user.username
        db.session.remove()
        db.engine.dispose()


def test_password_hash_and_user_timestamps(backend):
    user = sample_user()
    db.session.add(user)
    db.session.commit()
    db.session.expire_all()
    assert user.password_hash != "test-only-password"
    assert user.check_password("test-only-password")
    assert not user.check_password("incorrect")
    assert user.created_at.utcoffset() == timedelta(0)
    before = user.updated_at
    user.is_active = False
    db.session.commit()
    assert user.updated_at >= before
    with pytest.raises(ValueError):
        user.set_password("")


def test_relationships_and_utc_roundtrip(backend):
    user = sample_user()
    document = Document(filename="example.txt", category="Testing", format="TXT",
                        storage_reference="synthetic/example.txt", is_decoy=True)
    rule = DetectionRule(id="TEST-RULE", name="Fictional rule", severity="high",
                         parameters={"threshold": 3})
    when = datetime(2026, 1, 1, 5, tzinfo=timezone(timedelta(hours=5)))
    event = AuditEvent(actor=user, document=document, rule=rule, action="preview",
                       outcome="success", occurred_at=when)
    alert = Alert(actor=user, document=document, rule=rule, severity="high",
                  explanation="Test fixture only", events=[event])
    db.session.add(alert)
    db.session.commit()
    db.session.expire_all()
    assert event.occurred_at == when.astimezone(timezone.utc)
    assert event.occurred_at.utcoffset() == timedelta(0)
    assert alert.created_at.utcoffset() == timedelta(0)
    assert alert in user.alerts and event in user.audit_events
    assert event in document.audit_events and alert in document.alerts
    assert event in rule.audit_events and alert in rule.alerts
    assert event.alerts == [alert] and alert.events == [event]
    assert rule.parameters == {"threshold": 3}
    assert len({document.id, event.id, alert.id}) == 3
    with pytest.raises(IntegrityError):
        db.session.execute(alert_events.insert().values(alert_id=alert.id, event_id=event.id))
    db.session.rollback()


@pytest.mark.parametrize("model,values", [
    (User, {"username": "duplicate", "password_hash": "test-hash"}),
    (Document, {"filename": "x.txt", "category": "Test", "format": "TXT", "storage_reference": "same"}),
    (DetectionRule, {"id": "same-rule", "name": "Test", "severity": "low"}),
    (AuditEvent, {"id": "same-event", "action": "test", "outcome": "test"}),
])
def test_unique_constraints(backend, model, values):
    db.session.add_all([model(**values), model(**values)])
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


@pytest.mark.parametrize("model,values", [
    (User, {"username": "x", "password_hash": "test-hash", "role": "unknown"}),
    (Document, {"filename": "x", "category": "Test", "format": "TXT", "storage_reference": "x", "sensitivity": "unknown"}),
    (Document, {"filename": "x", "category": "Test", "format": "TXT", "storage_reference": "x", "status": "unknown"}),
    (DetectionRule, {"id": "x", "name": "Test", "severity": "unknown"}),
    (AuditEvent, {"action": "test"}),
])
def test_constraints_reject_invalid_records(backend, model, values):
    db.session.add(model(**values))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


@pytest.mark.parametrize("field,value", [("actor_id", 999), ("document_id", "missing"), ("rule_id", "missing")])
def test_foreign_keys_on_every_connection(backend, field, value):
    db.session.remove()
    db.engine.dispose()
    assert db.session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
    db.session.add(AuditEvent(action="test", outcome="test", **{field: value}))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_naive_timestamp_rejected(backend):
    db.session.add(AuditEvent(action="test", outcome="test", occurred_at=datetime(2026, 1, 1)))
    with pytest.raises(StatementError, match="Timezone-aware"):
        db.session.commit()
    db.session.rollback()


@pytest.mark.parametrize("overrides", [
    {"severity": "unknown"}, {"review_state": "unknown"},
    {"rule_id": "missing"}, {"actor_id": 999}, {"document_id": "missing"},
])
def test_alert_constraints(backend, overrides):
    db.session.add(DetectionRule(id="test-rule", name="Test", severity="low"))
    db.session.commit()
    values = {"rule_id": "test-rule", "severity": "low", "explanation": "Test"}
    values.update(overrides)
    db.session.add(Alert(**values))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_alert_unique_id_and_supporting_event_foreign_keys(backend):
    db.session.add(DetectionRule(id="test-rule", name="Test", severity="low"))
    db.session.commit()
    for _ in range(2):
        db.session.add(Alert(id="same-alert", rule_id="test-rule", severity="low", explanation="Test"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    db.session.add(Alert(id="test-alert", rule_id="test-rule", severity="low", explanation="Test"))
    db.session.add(AuditEvent(id="test-event", action="test", outcome="test"))
    db.session.commit()
    for alert_id, event_id in [("test-alert", "missing"), ("missing", "test-event")]:
        with pytest.raises(IntegrityError):
            db.session.execute(alert_events.insert().values(alert_id=alert_id, event_id=event_id))
        db.session.rollback()


def test_backend_runner_uses_loopback_port():
    import runpy
    with patch("flask.Flask.run") as run:
        runpy.run_path("run.py", run_name="__main__")
    run.assert_called_once_with(host="127.0.0.1", port=5001, debug=False, use_reloader=False)

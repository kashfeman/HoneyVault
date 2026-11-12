"""Persistence only; no authentication, event writer, or rule engine."""
from datetime import datetime, timezone
from uuid import uuid4
from flask_login import UserMixin
from sqlalchemy.types import TypeDecorator, DateTime
from werkzeug.security import check_password_hash, generate_password_hash
from .extensions import db


def utc_now():
    return datetime.now(timezone.utc)


def new_id():
    return str(uuid4())


class UTCDateTime(TypeDecorator):
    """Persist naive UTC in SQLite; expose aware UTC in Python."""
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone-aware datetime required")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None else None


alert_events = db.Table(
    "alert_events",
    db.Column("alert_id", db.String(36), db.ForeignKey("alert.id"), primary_key=True),
    db.Column("event_id", db.String(36), db.ForeignKey("audit_event.id"), primary_key=True),
    db.Index("ix_alert_events_event_id", "event_id"),
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(20), nullable=False, default="employee")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at = db.Column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)
    __table_args__ = (db.CheckConstraint("role IN ('admin', 'employee')", name="valid_user_role"),)

    def set_password(self, password):
        if not isinstance(password, str) or not password:
            raise ValueError("Password must be a nonempty string")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class AuthSession(db.Model):
    """Revocable sessions; only a digest of the random browser token is stored."""
    token_hash = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    expires_at = db.Column(UTCDateTime(), nullable=False, index=True)


class Document(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=new_id)
    filename = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    format = db.Column(db.String(20), nullable=False)
    is_decoy = db.Column(db.Boolean, nullable=False, default=False)
    sensitivity = db.Column(db.String(20), nullable=False, default="internal")
    storage_reference = db.Column(db.String(255), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")
    __table_args__ = (
        db.CheckConstraint("sensitivity IN ('public', 'internal', 'confidential', 'restricted')", name="valid_sensitivity"),
        db.CheckConstraint("status IN ('active', 'archived')", name="valid_document_status"),
        db.Index("ix_document_category_status", "category", "status"),
    )


class DetectionRule(db.Model):
    id = db.Column(db.String(80), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    parameters = db.Column(db.JSON, nullable=False, default=dict)
    severity = db.Column(db.String(20), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    __table_args__ = (db.CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name="valid_rule_severity"),)


class AuditEvent(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=new_id)
    occurred_at = db.Column(UTCDateTime(), nullable=False, default=utc_now, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    document_id = db.Column(db.String(36), db.ForeignKey("document.id"), index=True)
    rule_id = db.Column(db.String(80), db.ForeignKey("detection_rule.id"), index=True)
    action = db.Column(db.String(80), nullable=False)
    outcome = db.Column(db.String(80), nullable=False)
    actor = db.relationship("User", backref="audit_events")
    document = db.relationship("Document", backref="audit_events")
    rule = db.relationship("DetectionRule", backref="audit_events")


class Alert(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=new_id)
    severity = db.Column(db.String(20), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    document_id = db.Column(db.String(36), db.ForeignKey("document.id"), index=True)
    rule_id = db.Column(db.String(80), db.ForeignKey("detection_rule.id"), nullable=False, index=True)
    explanation = db.Column(db.Text, nullable=False)
    created_at = db.Column(UTCDateTime(), nullable=False, default=utc_now, index=True)
    review_state = db.Column(db.String(20), nullable=False, default="unreviewed", index=True)
    actor = db.relationship("User", backref="alerts")
    document = db.relationship("Document", backref="alerts")
    rule = db.relationship("DetectionRule", backref="alerts")
    events = db.relationship("AuditEvent", secondary=alert_events, backref="alerts")
    __table_args__ = (
        db.CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name="valid_alert_severity"),
        db.CheckConstraint("review_state IN ('unreviewed', 'reviewed')", name="valid_review_state"),
    )

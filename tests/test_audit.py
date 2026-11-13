"""Real request auditing, database persistence and administrator activity boundaries."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from app.extensions import db
from app.models import AuditEvent, Document, User, utc_now
from scripts.preview_frontend import create_preview_app
from test_documents import library as library, login, records


def events(app):
    with app.app_context():
        return [dict(id=e.id, occurred_at=e.occurred_at, actor_id=e.actor_id,
                     document_id=e.document_id, action=e.action, outcome=e.outcome,
                     rule_id=e.rule_id)
                for e in db.session.execute(select(AuditEvent).order_by(
                    AuditEvent.occurred_at, AuditEvent.id)).scalars()]


def user_id(app, name="employee"):
    with app.app_context():
        return db.session.scalar(select(User.id).where(User.username == name))


def test_success_attribution_timestamps_and_persistence(library):
    client = login(library)
    identifier = records(library)[0][0]
    before = utc_now()
    for tail in ("", "/download"):
        response = client.get("/employee/documents/" + identifier + tail,
                              query_string={"actor_id": user_id(library, "admin"),
                                            "timestamp": "2000-01-01", "action": "ignore"},
                              headers={"X-User-Id": str(user_id(library, "admin"))})
        assert response.status_code == 200
    after = utc_now()
    saved = events(library)
    assert [e["action"] for e in saved] == ["document.preview", "document.download"]
    for event in saved:
        assert event["actor_id"] == user_id(library)
        assert event["document_id"] == identifier
        assert event["outcome"] == "success" and event["rule_id"] is None
        assert before <= event["occurred_at"] <= after
        assert event["occurred_at"].utcoffset() == timedelta(0)
    reopened = create_app(dict(library.config))
    assert events(reopened) == saved
    with reopened.app_context():
        db.session.remove()
        db.engine.dispose()


def test_listing_and_home_record_no_search_or_document_contents(library):
    client = login(library)
    assert client.get("/employee").status_code == 200
    assert client.get("/employee/documents?q=PRIVATE-SEARCH").status_code == 200
    saved = events(library)
    assert len(saved) == 2
    assert all(e["action"] == "document.list" and e["outcome"] == "success"
               and e["document_id"] is None for e in saved)
    assert "PRIVATE-SEARCH" not in str(saved)


@pytest.mark.parametrize("field,value", [("status", "archived"),
    ("sensitivity", "restricted"), ("sensitivity", "confidential"), ("format", "HTML")])
def test_record_permission_denials_keep_generic_responses(library, field, value):
    identifier = records(library)[0][0]
    with library.app_context():
        setattr(db.session.get(Document, identifier), field, value)
        db.session.commit()
    client = login(library)
    for tail in ("", "/download"):
        result = client.get("/employee/documents/" + identifier + tail)
        assert result.status_code == 404
        assert value not in result.text
    assert len(events(library)) == 2
    assert all(e["document_id"] == identifier and e["outcome"] == "denied"
               and e["actor_id"] == user_id(library) for e in events(library))


def test_wrong_role_denial_is_attributed_to_actual_admin(library):
    client = login(library, "admin")
    identifier = records(library)[0][0]
    for path in ("/employee", "/employee/documents",
                 "/employee/documents/" + identifier,
                 "/employee/documents/" + identifier + "/download"):
        assert client.get(path).status_code == 403
    saved = events(library)
    assert len(saved) == 4
    assert all(e["actor_id"] == user_id(library, "admin") and e["outcome"] == "denied" for e in saved)


@pytest.mark.parametrize("inactive", [False, True])
def test_no_fabricated_actor_for_anonymous_or_inactive_requests(library, inactive):
    client = login(library) if inactive else library.test_client()
    if inactive:
        with library.app_context():
            db.session.get(User, user_id(library)).is_active = False
            db.session.commit()
    identifier = records(library)[0][0]
    for tail in ("", "/download"):
        assert client.get("/employee/documents/" + identifier + tail).location == "/login"
    assert events(library) == []


@pytest.mark.parametrize("identifier", [str(uuid4()), "not-a-document", "..%5Cprivate.txt"])
def test_unknown_ids_have_nullable_references_without_storing_raw_input(library, identifier):
    client = login(library)
    for tail in ("", "/download"):
        assert client.get("/employee/documents/" + identifier + tail).status_code == 404
    saved = events(library)
    assert len(saved) == 2
    assert all(e["document_id"] is None and e["outcome"] == "unavailable" for e in saved)
    assert identifier not in str(saved)


def test_missing_file_retains_valid_document_reference(library):
    identifier = records(library)[0][0]
    with library.app_context():
        reference = db.session.get(Document, identifier).storage_reference
    (Path(library.config["DOCUMENT_STORAGE_ROOT"]) / reference).unlink()
    client = login(library)
    for tail in ("", "/download"):
        assert client.get("/employee/documents/" + identifier + tail).status_code == 404
    assert all(e["document_id"] == identifier and e["outcome"] == "unavailable"
               for e in events(library))


@pytest.mark.parametrize("tail", ["", "/download"])
def test_audit_write_failure_blocks_content_and_rolls_back(library, monkeypatch, caplog, tail):
    client = login(library)
    identifier = records(library)[0][0]
    with monkeypatch.context() as patch:
        def fail():
            raise SQLAlchemyError("PRIVATE-EXCEPTION-DETAIL")
        patch.setattr(db.session, "commit", fail)
        result = client.get("/employee/documents/" + identifier + tail)
    assert result.status_code == 503
    assert "PRIVATE-EXCEPTION-DETAIL" not in result.text + caplog.text
    assert "Content-Disposition" not in result.headers
    assert result.headers["Cache-Control"] == "no-store"
    assert events(library) == []
    assert client.get("/employee/documents/" + identifier + tail).status_code == 200
    assert len(events(library)) == 1


def test_unexpected_error_record_does_not_store_exception_text(library, monkeypatch):
    client = login(library)
    identifier = records(library)[0][0]
    def fail(document):
        raise RuntimeError("PRIVATE-ERROR-CONTENT")
    monkeypatch.setattr("app.workspaces.read_document", fail)
    with pytest.raises(RuntimeError):
        client.get("/employee/documents/" + identifier)
    saved = events(library)
    assert len(saved) == 1 and saved[0]["outcome"] == "error"
    assert "PRIVATE-ERROR-CONTENT" not in str(saved)


def test_activity_access_is_admin_only_and_has_no_fixture_fallback(library):
    path = "/dashboard/document-activity"
    assert library.test_client().get(path).location == "/login"
    employee = login(library)
    assert employee.get(path + "?role=admin&actor=1").status_code == 403
    assert employee.get("/employee/document-activity").status_code == 404
    admin = login(library, "admin")
    page = admin.get(path)
    assert page.status_code == 200 and "No recorded document activity" in page.text
    assert "DEMO-008" not in page.text and "ALERT-001" not in page.text
    assert page.headers["Cache-Control"] == "no-store"
    assert events(library) == []  # Reading history does not recursively add document events.
    assert create_preview_app().test_client().get(path).status_code == 404


def populate_activity(app):
    docs = records(app)
    actor = user_id(app)
    other = user_id(app, "admin")
    when = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
    with app.app_context():
        for n in range(1, 61):
            db.session.add(AuditEvent(id=str(UUID(int=n)), occurred_at=when,
                                     actor_id=actor if n % 2 else other,
                                     document_id=docs[0 if n % 2 else 1][0],
                                     action="document.preview" if n % 2 else "document.download",
                                     outcome="success" if n % 2 else "denied"))
        db.session.add(AuditEvent(action="legacy.fixture", outcome="success"))
        db.session.commit()
    return docs, actor, other


def test_search_filters_utc_bounds_and_pagination(library):
    docs, actor, other = populate_activity(library)
    client = login(library, "admin")
    base = "/dashboard/document-activity"
    pages = [client.get(base, query_string={"page": page}).text for page in (1, 2, 3)]
    for page, first, last, count in ((pages[0], 60, 36, 25), (pages[1], 35, 11, 25), (pages[2], 10, 1, 10)):
        assert page.count('<th scope="row">') == count
        assert page.index(str(UUID(int=first))) < page.index(str(UUID(int=last)))
        assert "legacy.fixture" not in page
    assert 'rel="next"' in pages[0] and 'rel="prev"' not in pages[0]
    assert 'rel="next"' not in pages[2] and 'rel="prev"' in pages[2]
    response = client.get(base, query_string={"actor": actor, "document": docs[0][0],
        "action": "document.preview", "outcome": "success", "start": "2026-01-02T12:00",
        "end": "2026-01-02T12:00", "q": "employee"})
    assert response.status_code == 200 and response.text.count('<th scope="row">') == 25
    assert 'action=document.preview' in response.text and 'actor=' + str(actor) in response.text
    assert str(UUID(int=59)) in response.text and str(UUID(int=60)) not in response.text
    for query in ({"q": str(UUID(int=60))}, {"q": docs[1][1]}, {"actor": other}):
        assert str(UUID(int=60)) in client.get(base, query_string=query).text
    for query in ({"q": "%"}, {"q": "' OR 1=1--"}, {"q": "_"},
                  {"start": "2026-01-03T00:00"}, {"page": 4}):
        assert "No recorded document activity" in client.get(base, query_string=query).text
    assert client.get(base + "?page=1000").status_code == 200


def test_timestamp_ordering_and_result_window_notice(library, monkeypatch):
    populate_activity(library)
    with library.app_context():
        newest = db.session.get(AuditEvent, str(UUID(int=1)))
        newest.occurred_at += timedelta(days=1)
        db.session.commit()
    monkeypatch.setattr("app.audit.views.MAX_PAGE", 1)
    page = login(library, "admin").get("/dashboard/document-activity")
    assert page.status_code == 200
    assert page.text.index(str(UUID(int=1))) < page.text.index(str(UUID(int=60)))
    assert page.text.count('<th scope="row">') == 25
    assert "Result window reached" in page.text
    assert 'rel="next"' not in page.text


@pytest.mark.parametrize("query", ["page=0", "page=-1", "page=1001", "page=abc",
    "page=99999999999999999999", "action=anything", "outcome=anything",
    "actor=-1", "actor=abc", "actor=999999999999999999999", "document=bad",
    "start=bad", "end=2026-99-99T00:00", "start=2026-01-03T00:00&end=2026-01-02T00:00"])
def test_invalid_activity_filters_are_safe(library, query):
    client = login(library, "admin")
    response = client.get("/dashboard/document-activity?" + query)
    assert response.status_code == 400
    assert "Traceback" not in response.text


def test_two_employees_cannot_spoof_attribution_or_read_each_other_history(library):
    with library.app_context():
        other = User(username="second", role="employee")
        other.set_password("synthetic-test-password")
        db.session.add(other)
        db.session.commit()
        second_id = other.id
    first = login(library)
    second = login(library, "second")
    identifier = records(library)[0][0]
    for client, forged in ((first, second_id), (second, user_id(library))):
        assert client.get("/employee/documents/" + identifier,
                          query_string={"actor_id": forged}).status_code == 200
        assert client.get("/dashboard/document-activity?actor=" + str(forged)).status_code == 403
    assert [e["actor_id"] for e in events(library)] == [user_id(library), second_id]


def test_activity_and_records_exclude_contents_paths_and_security_metadata(library):
    identifier = records(library)[0][0]
    with library.app_context():
        document = db.session.get(Document, identifier)
        reference = document.storage_reference
        document.filename = '<script>NAME-CANARY</script>.txt'
        document.format = 'TXT'
        document.storage_reference = "private-canary.txt"
        (Path(library.config["DOCUMENT_STORAGE_ROOT"]) / document.storage_reference).write_text(
            "BODY-CANARY password=SECRET-CANARY", encoding="utf-8")
        db.session.commit()
    client = login(library)
    assert client.get("/employee/documents/" + identifier).status_code == 200
    page = login(library, "admin").get("/dashboard/document-activity")
    assert "&lt;script&gt;NAME-CANARY&lt;/script&gt;.txt" in page.text
    assert '<script>NAME-CANARY' not in page.text
    for secret in ("BODY-CANARY", "SECRET-CANARY", "private-canary.txt", reference,
                   library.config["DOCUMENT_STORAGE_ROOT"], "storage_reference", "is_decoy", "password_hash"):
        assert secret not in page.text + str(events(library))
    for path, disclosure in (("/dashboard/alerts", "No rules are evaluated"),
                             ("/dashboard/events", "not real server logs"),
                             ("/dashboard", "fictional document interactions")):
        assert disclosure in login(library, "admin").get(path).text

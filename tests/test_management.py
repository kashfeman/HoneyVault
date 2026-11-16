"""Administrator generation, metadata control and private-storage regression tests."""
from pathlib import Path
import re
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import AuditEvent, Document, User
from scripts.preview_frontend import create_preview_app
from test_documents import library as library, login, records

NEW = '/dashboard/manage-documents/new'


def token(client, path):
    page = client.get(path)
    assert page.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', page.text)[1]


def values(**overrides):
    fields = dict(filename='Sample guide.txt', category='People', format='TXT',
                  classification='normal', sensitivity='internal', status='active', synthetic_ack='yes')
    fields.update(overrides)
    return fields


def create(client, **overrides):
    return client.post(NEW, data={**values(**overrides), 'csrf_token': token(client, NEW)})


def snapshot(app):
    with app.app_context():
        return [(d.id, d.filename, d.category, d.format, d.is_decoy, d.sensitivity,
                 d.status, d.storage_reference) for d in db.session.execute(select(Document).order_by(Document.id)).scalars()]


def edit_values(client, identifier, **overrides):
    path = '/dashboard/manage-documents/' + identifier + '/edit'
    page = client.get(path)
    assert page.status_code == 200
    fields = values(**overrides)
    fields['csrf_token'] = re.search(r'name="csrf_token" value="([^"]+)"', page.text)[1]
    fields['version'] = re.search(r'name="version" value="([^"]+)"', page.text)[1]
    return path, fields


@pytest.mark.parametrize('fmt,classification', [('TXT', 'normal'), ('TXT', 'decoy'), ('CSV', 'normal'), ('CSV', 'decoy')])
def test_create_private_synthetic_document_and_employee_access(library, fmt, classification):
    admin = login(library, 'admin')
    stem = ('a' if fmt == 'TXT' else 'x' * 76) if classification == 'normal' else 'Sample plan'
    filename = stem + '.' + fmt.lower()
    response = create(admin, filename=filename, format=fmt, classification=classification)
    assert response.status_code == 303
    identifier = response.location.rsplit('/', 1)[1]
    with library.app_context():
        doc = db.session.get(Document, identifier)
        assert doc.filename == filename
        assert doc.format == fmt and doc.is_decoy == (classification == 'decoy')
        assert doc.storage_reference == identifier + '.' + fmt.lower()
        path = Path(library.config['DOCUMENT_STORAGE_ROOT']) / doc.storage_reference
        body = path.read_bytes()
        assert b'decoy' not in body.lower() and b'internal' not in body.lower()
        event = db.session.execute(select(AuditEvent).where(AuditEvent.action == 'document.create')).scalar_one()
        assert event.actor_id == db.session.scalar(select(User.id).where(User.role == 'admin'))
        assert event.document_id == identifier and event.outcome == 'success'
    employee = login(library)
    for tail in ('', '/download'):
        result = employee.get('/employee/documents/' + identifier + tail)
        assert result.status_code == 200
        for secret in ('is_decoy', 'classification', 'sensitivity', 'storage_reference', str(path)):
            assert secret not in result.text
    assert admin.get(response.location).status_code == 200
    assert employee.get('/static/documents/' + path.name).status_code == 404


def test_metadata_archive_reactivate_preserves_bytes_identity_and_history(library):
    admin = login(library, 'admin')
    identifier = create(admin).location.rsplit('/', 1)[1]
    employee = login(library)
    assert employee.get('/employee/documents/' + identifier).status_code == 200
    with library.app_context():
        doc = db.session.get(Document, identifier)
        reference = doc.storage_reference
        original = (Path(library.config['DOCUMENT_STORAGE_ROOT']) / reference).read_bytes()
        old_events = list(db.session.execute(select(AuditEvent.id)).scalars())
    for status, sensitivity, expected in [('archived', 'internal', 404), ('active', 'restricted', 404), ('active', 'public', 200)]:
        path, fields = edit_values(admin, identifier, filename='Renamed plan.txt', classification='decoy', status=status, sensitivity=sensitivity)
        assert admin.post(path, data=fields).status_code == 303
        assert employee.get('/employee/documents/' + identifier).status_code == expected
        assert employee.get('/employee/documents/' + identifier + '/download').status_code == expected
        with library.app_context():
            doc = db.session.get(Document, identifier)
            assert doc.storage_reference == reference and doc.is_decoy
            assert (Path(library.config['DOCUMENT_STORAGE_ROOT']) / reference).read_bytes() == original
            assert set(old_events) <= set(db.session.execute(select(AuditEvent.id)).scalars())
    with library.app_context():
        assert len(db.session.execute(select(AuditEvent).where(AuditEvent.action == 'document.update')).scalars().all()) == 3


@pytest.mark.parametrize('role,expected', [(None, 302), ('employee', 403), ('inactive', 302)])
def test_all_management_actions_require_active_admin(library, role, expected):
    client = library.test_client() if role is None else login(library, 'admin' if role == 'inactive' else role)
    identifier = records(library)[0][0]
    csrf_token = None
    if role is not None:
        csrf_token = token(client, NEW) if role == 'inactive' else re.search(r'name="csrf_token" value="([^"]+)"', client.get('/employee').text)[1]
    else:
        csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', client.get('/login').text)[1]
    if role == 'inactive':
        with library.app_context():
            db.session.execute(db.update(User).where(User.role == 'admin').values(is_active=False))
            db.session.commit()
    before = snapshot(library)
    for path in ('/dashboard/manage-documents', '/dashboard/manage-documents/' + identifier,
                 NEW, '/dashboard/manage-documents/' + identifier + '/edit'):
        assert client.get(path).status_code == expected
    if role == 'inactive':
        # Revoking the inactive session also discards its old CSRF token.
        assert client.post(NEW, data={**values(), 'csrf_token': csrf_token}).status_code == 400
        csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', client.get('/login').text)[1]
    for path in (NEW, '/dashboard/manage-documents/' + identifier + '/edit'):
        assert client.post(path, data={**values(), 'csrf_token': csrf_token}).status_code == expected
    assert snapshot(library) == before


def test_csrf_required_and_no_delete_or_file_mutation_routes(library):
    admin = login(library, 'admin')
    before = snapshot(library)
    identifier = records(library)[0][0]
    for path in (NEW, '/dashboard/manage-documents/' + identifier + '/edit'):
        assert admin.post(path, data=values()).status_code == 400
        assert admin.post(path, data={**values(), 'csrf_token': 'invalid'}).status_code == 400
    for method in (admin.delete, admin.put, admin.patch):
        assert method('/dashboard/manage-documents/' + identifier,
                      headers={'X-CSRFToken': token(admin, NEW)}).status_code == 405
    assert snapshot(library) == before


@pytest.mark.parametrize('changes', [dict(filename='../bad.txt'), dict(filename='C:\\bad.txt'),
    dict(filename='bad\r\nheader.txt'), dict(filename='bad.html'), dict(filename='CON.txt'),
    dict(filename='x' * 90 + '.txt'), dict(format='HTML'), dict(filename='bad.csv'),
    dict(category='Unknown'), dict(classification='admin'), dict(sensitivity='secret'),
    dict(status='deleted'), dict(synthetic_ack=''), dict(storage_reference='../outside.txt'),
    dict(content='PRIVATE-DATA'), dict(id=str(uuid4()))])
def test_creation_validation_is_non_destructive(library, changes):
    admin = login(library, 'admin')
    before = snapshot(library)
    files = sorted(Path(library.config['DOCUMENT_STORAGE_ROOT']).iterdir())
    result = create(admin, **changes)
    assert result.status_code == 400
    assert snapshot(library) == before
    assert sorted(Path(library.config['DOCUMENT_STORAGE_ROOT']).iterdir()) == files
    assert 'Traceback' not in result.text


def test_edit_rejects_stale_version_format_change_and_mass_assignment(library):
    admin = login(library, 'admin')
    identifier = create(admin).location.rsplit('/', 1)[1]
    path, first = edit_values(admin, identifier)
    _, stale = edit_values(admin, identifier)
    first['filename'] = 'New name.txt'
    assert admin.post(path, data=first).status_code == 303
    stale['filename'] = 'Stale name.txt'
    assert admin.post(path, data=stale).status_code == 409
    before = snapshot(library)
    for changes in (dict(format='CSV', filename='Bad format.csv'), dict(storage_reference='other.txt')):
        _, fields = edit_values(admin, identifier, **changes)
        assert admin.post(path, data=fields).status_code == 400
    assert snapshot(library) == before


@pytest.mark.parametrize('identifier', ['doc-101', '..%5Coutside.txt', str(uuid4())])
def test_invalid_ids_are_safe(library, identifier):
    admin = login(library, 'admin')
    for tail in ('', '/edit'):
        result = admin.get('/dashboard/manage-documents/' + identifier + tail)
        assert result.status_code == 404 and 'Traceback' not in result.text
    result = admin.post('/dashboard/manage-documents/' + identifier + '/edit',
                        data={**values(), 'csrf_token': token(admin, NEW)})
    assert result.status_code == 404


def test_missing_file_allows_metadata_management_without_leaking_paths(library):
    admin = login(library, 'admin')
    identifier = records(library)[0][0]
    with library.app_context():
        doc = db.session.get(Document, identifier)
        (Path(library.config['DOCUMENT_STORAGE_ROOT']) / doc.storage_reference).unlink()
    response = admin.get('/dashboard/manage-documents/' + identifier)
    assert response.status_code == 200 and 'Preview unavailable' in response.text
    assert library.config['DOCUMENT_STORAGE_ROOT'] not in response.text
    assert admin.get('/dashboard/manage-documents/' + identifier + '/edit').status_code == 200


def test_inventory_filters_pagination_navigation_and_preview_isolation(library):
    admin = login(library, 'admin')
    page = admin.get('/dashboard/manage-documents')
    assert page.status_code == 200 and 'simulation' not in page.text.lower()
    assert '/dashboard/document-activity' in page.text
    assert 'Alert severity (Overview)' in page.text and 'Recent events (Overview)' in page.text
    assert admin.get('/dashboard/manage-documents?classification=decoy&category=Finance').text.count('<th scope="row">') == 1
    assert 'No documents found' in admin.get('/dashboard/manage-documents?q=%25').text
    assert admin.get('/dashboard/manage-documents?status=deleted').status_code == 400
    assert admin.get('/dashboard/manage-documents?page=99999999').status_code == 400
    with library.app_context():
        for n in range(30):
            db.session.add(Document(filename=f'Sample {n:02}.txt', category='People', format='TXT', storage_reference=str(uuid4()) + '.txt'))
        db.session.commit()
    page = admin.get('/dashboard/manage-documents')
    assert page.text.count('<th scope="row">') == 25 and 'rel="next"' in page.text
    assert admin.get('/dashboard/manage-documents?page=2').text.count('<th scope="row">') == 9
    preview = create_preview_app().test_client()
    assert 'Simulation' in preview.get('/dashboard/manage-documents/doc-101').text
    assert preview.get(NEW).status_code == 404
    assert preview.post(NEW).status_code in (404, 405)
    assert admin.get('/dashboard/events/DEMO-008').status_code == 200
    assert '/dashboard/documents/doc-' in admin.get('/dashboard/events/DEMO-008').text


def test_failed_transactions_preserve_existing_rows_and_audit(library, monkeypatch, caplog):
    admin = login(library, 'admin')
    csrf = token(admin, NEW)
    before = snapshot(library)
    with monkeypatch.context() as patch:
        def fail():
            raise SQLAlchemyError('PRIVATE-ERROR-PATH')
        patch.setattr(db.session, 'commit', fail)
        response = admin.post(NEW, data={**values(), 'csrf_token': csrf})
    assert response.status_code == 503
    assert 'PRIVATE-ERROR-PATH' not in response.text + caplog.text
    assert snapshot(library) == before
    with library.app_context():
        assert db.session.execute(select(AuditEvent).where(AuditEvent.action == 'document.create')).scalars().all() == []


def test_storage_limits_and_static_root_rejected(library):
    admin = login(library, 'admin')
    before = snapshot(library)
    library.config['DOCUMENT_MAX_BYTES'] = 1
    assert create(admin).status_code == 400
    library.config['DOCUMENT_MAX_BYTES'] = 1024 * 1024
    library.config['DOCUMENT_STORAGE_ROOT'] = library.static_folder
    assert create(admin).status_code == 503
    assert snapshot(library) == before


def test_uploads_duplicate_fields_and_html_names_are_rejected(library):
    from io import BytesIO
    from werkzeug.datastructures import MultiDict
    admin = login(library, 'admin')
    before = snapshot(library)
    csrf = token(admin, NEW)
    upload = {**values(), 'csrf_token': csrf, 'file': (BytesIO(b'PRIVATE-UPLOAD'), '../../outside.txt')}
    assert admin.post(NEW, data=upload).status_code == 400
    duplicate = MultiDict(list({**values(), 'csrf_token': csrf}.items()) + [('classification', 'decoy')])
    assert admin.post(NEW, data=duplicate).status_code == 400
    response = create(admin, filename='<script>alert(1)</script>.txt')
    assert response.status_code == 400
    assert '<script>alert(1)</script>' not in response.text
    assert '&lt;script&gt;' in response.text
    assert snapshot(library) == before


def test_update_commit_failure_rolls_back_metadata_and_audit(library, monkeypatch):
    admin = login(library, 'admin')
    identifier = create(admin).location.rsplit('/', 1)[1]
    path, fields = edit_values(admin, identifier, filename='Should not persist.txt', status='archived')
    before = snapshot(library)
    with library.app_context():
        event_ids = set(db.session.execute(select(AuditEvent.id)).scalars())
    with monkeypatch.context() as patch:
        def fail():
            raise SQLAlchemyError('private-error')
        patch.setattr(db.session, 'commit', fail)
        assert admin.post(path, data=fields).status_code == 503
    assert snapshot(library) == before
    with library.app_context():
        assert set(db.session.execute(select(AuditEvent.id)).scalars()) == event_ids
    assert admin.post(path, data=fields).status_code == 303

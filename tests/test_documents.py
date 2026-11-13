"""Milestone 8 contracts against private files and temporary SQLite databases."""
import re
import secrets
from uuid import uuid4

import pytest
from sqlalchemy import select, func

from app import create_app
from app.extensions import db
from app.models import Document, User, AuditEvent, Alert


@pytest.fixture
def library(tmp_path):
    app = create_app({'TESTING': True, 'SECRET_KEY': secrets.token_hex(32),
                      'SESSION_COOKIE_SECURE': False,
                      'DOCUMENT_STORAGE_ROOT': str(tmp_path / 'private'),
                      'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + (tmp_path / 'library.sqlite3').as_posix()})
    runner = app.test_cli_runner()
    assert runner.invoke(args=['init-db']).exit_code == 0
    assert runner.invoke(args=['seed-demo-documents']).exit_code == 0
    with app.app_context():
        for role in ('employee', 'admin'):
            user = User(username=role, role=role)
            user.set_password('synthetic-test-password')
            db.session.add(user)
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def login(app, role='employee'):
    client = app.test_client()
    token = re.search(r'name="csrf_token" value="([^"]+)"', client.get('/login').text)[1]
    assert client.post('/login', data={'csrf_token': token, 'username': role,
                                      'password': 'synthetic-test-password'}).status_code == 302
    return client


def records(app):
    with app.app_context():
        return [(d.id, d.filename, d.is_decoy) for d in db.session.execute(select(Document).order_by(Document.filename)).scalars()]


def test_database_listing_filter_sort_and_home(library):
    client = login(library)
    docs = records(library)
    response = client.get('/employee/documents')
    assert response.status_code == 200
    assert '4 of 4 demo documents' in response.text
    positions = [response.text.index(name) for _, name, _ in docs]
    assert positions == sorted(positions)
    for suffix in ('?sort=category', '?sort=format', '?sort=invalid'):
        assert client.get('/employee/documents' + suffix).status_code == 200
    reverse = client.get('/employee/documents?sort=title_desc').text
    positions = [reverse.index(name) for _, name, _ in reversed(docs)]
    assert positions == sorted(positions)
    for query in ('?category=Finance', '?q=forecast'):
        result = client.get('/employee/documents' + query).text
        assert 'Quarterly forecast.csv' in result and 'Team handbook.txt' not in result
    for query in ('?q=%25', '?q=%27%20OR%201=1--', '?category=unknown'):
        assert 'No documents found' in client.get('/employee/documents' + query).text
    assert '4' in client.get('/employee').text


def test_previews_downloads_and_metadata_confidentiality(library):
    client = login(library)
    assert {item[2] for item in records(library)} == {True, False}
    with library.app_context():
        private_references = list(db.session.execute(select(Document.storage_reference)).scalars())
    for identifier, name, decoy in records(library):
        prefix = '/employee/documents/' + identifier
        preview = client.get(prefix)
        download = client.get(prefix + '/download')
        assert preview.status_code == download.status_code == 200
        assert name in preview.text
        assert download.data.decode('utf-8') in preview.text
        assert download.headers['Content-Disposition'].startswith('attachment;')
        assert download.headers['Content-Type'].startswith('text/csv' if name.endswith('.csv') else 'text/plain')
        for response in (preview, download, client.get('/employee/documents'), client.get('/employee')):
            assert response.headers['Cache-Control'] == 'no-store'
            assert response.headers['X-Content-Type-Options'] == 'nosniff'
            combined = response.text + str(response.headers)
            for secret in ('is_decoy', 'sensitivity', 'storage_reference', 'password_hash', 'detection_rule', library.config['DOCUMENT_STORAGE_ROOT'], *private_references):
                assert secret not in combined
        assert 'ETag' not in download.headers and 'Last-Modified' not in download.headers
    with library.app_context():
        assert db.session.scalar(select(func.count()).select_from(AuditEvent)) == 16
        assert db.session.scalar(select(func.count()).select_from(Alert)) == 0


@pytest.mark.parametrize('role,expected', [(None, 302), ('admin', 403), ('employee', 302)])
def test_anonymous_wrong_role_and_deactivated(library, role, expected):
    client = login(library, role) if role else library.test_client()
    identifier = records(library)[0][0]
    if role == 'employee':
        with library.app_context():
            db.session.execute(db.update(User).where(User.role == 'employee').values(is_active=False))
            db.session.commit()
    for path in ('/employee', '/employee/documents', '/employee/documents/' + identifier,
                 '/employee/documents/' + identifier + '/download'):
        response = client.get(path)
        assert response.status_code == expected
        if expected == 302:
            assert response.location == '/login'


@pytest.mark.parametrize('field,value', [('status', 'archived'), ('sensitivity', 'confidential'),
    ('sensitivity', 'restricted'), ('format', 'HTML'), ('format', 'txt')])
def test_record_level_policy(library, field, value):
    identifier, name, _ = records(library)[0]
    with library.app_context():
        setattr(db.session.get(Document, identifier), field, value)
        db.session.commit()
    client = login(library)
    assert name not in client.get('/employee/documents').text
    for tail in ('', '/download'):
        assert client.get('/employee/documents/' + identifier + tail + '?role=admin').status_code == 404


@pytest.mark.parametrize('reference', ['../outside.txt', '..\\outside.txt', '/etc/passwd',
    'C:\\Windows\\win.ini', 'file.txt:stream', 'bad.html', 'nested/file.txt', 'missing.txt'])
def test_untrusted_database_paths(library, reference):
    with library.app_context():
        doc = db.session.execute(select(Document).where(Document.format == 'TXT')).scalars().first()
        identifier = doc.id
        doc.storage_reference = reference
        db.session.commit()
    client = login(library)
    for tail in ('', '/download'):
        assert client.get('/employee/documents/' + identifier + tail).status_code == 404


@pytest.mark.parametrize('identifier', ['doc-101', '0', 'not-a-uuid', str(uuid4()),
    '..%2F..%2F.env', '..%5C..%5C.env', '%00', 'C:%5CWindows%5Cwin.ini'])
def test_invalid_ids(library, identifier):
    client = login(library)
    for tail in ('', '/download'):
        response = client.get('/employee/documents/' + identifier + tail)
        assert response.status_code == 404
        assert 'Traceback' not in response.text


def test_escaped_preview_and_safe_filename(library):
    from pathlib import Path
    with library.app_context():
        doc = db.session.execute(select(Document).where(Document.format == 'TXT')).scalars().first()
        identifier = doc.id
        doc.filename = '../../<script>example</script>\r\nX-Injected: true.txt'
        (Path(library.config['DOCUMENT_STORAGE_ROOT']) / doc.storage_reference).write_text('<script>alert(1)</script>\n<b>text</b>', encoding='utf-8')
        db.session.commit()
    client = login(library)
    response = client.get('/employee/documents/' + identifier)
    assert '<script>alert(1)</script>' not in response.text
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in response.text
    download = client.get('/employee/documents/' + identifier + '/download')
    assert download.status_code == 200
    assert 'X-Injected' not in download.headers
    assert '../' not in download.headers['Content-Disposition']


@pytest.mark.parametrize('content', [b'x' * (1024 * 1024 + 1), b'\xff\xfe', b'bad\0data'])
def test_bounded_utf8_only(library, content):
    from pathlib import Path
    with library.app_context():
        doc = db.session.execute(select(Document)).scalars().first()
        identifier = doc.id
        (Path(library.config['DOCUMENT_STORAGE_ROOT']) / doc.storage_reference).write_bytes(content)
    client = login(library)
    for tail in ('', '/download'):
        assert client.get('/employee/documents/' + identifier + tail).status_code == 404


def test_seed_non_destructive_and_no_public_storage(library):
    from pathlib import Path
    root = Path(library.config['DOCUMENT_STORAGE_ROOT'])
    original = {p.name: p.read_bytes() for p in root.iterdir()}
    with library.app_context():
        doc = db.session.execute(select(Document)).scalars().first()
        doc.category = 'Preserved'
        db.session.commit()
    result = library.test_cli_runner().invoke(args=['seed-demo-documents'])
    assert result.exit_code == 0 and 'Added 0' in result.output
    assert original == {p.name: p.read_bytes() for p in root.iterdir()}
    with library.app_context():
        assert db.session.scalar(select(func.count()).select_from(Document)) == 4
        assert db.session.execute(select(Document).where(Document.category == 'Preserved')).scalar_one()
    client = login(library)
    for name in original:
        assert client.get('/static/documents/' + name).status_code == 404
    library.config['DOCUMENT_STORAGE_ROOT'] = library.static_folder
    assert library.test_cli_runner().invoke(args=['seed-demo-documents']).exit_code != 0


def test_empty_database(library):
    with library.app_context():
        db.session.execute(db.delete(Document))
        db.session.commit()
    client = login(library)
    assert '0 of 0' in client.get('/employee/documents').text
    assert client.get('/employee').status_code == 200


def test_missing_file_directory_link_and_extension_mismatch(library, monkeypatch):
    from pathlib import Path
    client = login(library)
    with library.app_context():
        doc = db.session.execute(select(Document).where(Document.format == 'TXT')).scalars().first()
        identifier = doc.id
        path = Path(library.config['DOCUMENT_STORAGE_ROOT']) / doc.storage_reference
    data = path.read_bytes()
    path.unlink()
    for tail in ('', '/download'):
        assert client.get('/employee/documents/' + identifier + tail).status_code == 404
    path.mkdir()
    assert client.get('/employee/documents/' + identifier).status_code == 404
    path.rmdir()
    path.write_bytes(data)
    with monkeypatch.context() as patch:
        original = Path.is_symlink
        patch.setattr(Path, 'is_symlink', lambda self: self == path or original(self))
        assert client.get('/employee/documents/' + identifier).status_code == 404
    with library.app_context():
        db.session.get(Document, identifier).filename = 'example.html'
        db.session.commit()
    assert client.get('/employee/documents/' + identifier + '/download').status_code == 404


def test_seed_preserves_file_collision(library):
    from pathlib import Path
    identifier = records(library)[0][0]
    with library.app_context():
        doc = db.session.get(Document, identifier)
        path = Path(library.config['DOCUMENT_STORAGE_ROOT']) / doc.storage_reference
        db.session.delete(doc)
        db.session.commit()
    path.write_bytes(b'preserve existing file')
    result = library.test_cli_runner().invoke(args=['seed-demo-documents'])
    assert result.exit_code == 0
    assert path.read_bytes() == b'preserve existing file'
    with library.app_context():
        assert db.session.get(Document, identifier) is None

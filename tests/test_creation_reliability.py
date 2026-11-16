"""No-clobber publication and compensating cleanup touch only owned new files."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.documents.service import staged_document
from app.extensions import db
from app.models import AuditEvent, Document
from test_documents import library as library, login, records
from test_management import NEW, create, snapshot, token, values


def file_snapshot(app):
    root = Path(app.config['DOCUMENT_STORAGE_ROOT'])
    return {p.name: p.read_bytes() for p in root.iterdir()}


@pytest.mark.parametrize('failure', ['flush', 'commit', 'fsync', 'publish', 'write'])
def test_failed_creation_cleans_only_its_own_files(library, monkeypatch, failure):
    import app.documents.service as storage
    admin = login(library, 'admin')
    csrf = token(admin, NEW)
    root = Path(library.config['DOCUMENT_STORAGE_ROOT'])
    (root / 'historical-orphan.txt').write_bytes(b'preserve historical orphan')
    (root / '.hv-create-historical.tmp').write_bytes(b'preserve historical temporary file')
    before_files = file_snapshot(library)
    before_rows = snapshot(library)
    with library.app_context():
        before_events = set(db.session.execute(select(AuditEvent.id)).scalars())
    def fail(*args, **kwargs):
        raise SQLAlchemyError('private-db-error') if failure in ('flush', 'commit') else OSError('private-storage-error')
    with monkeypatch.context() as patch:
        if failure in ('flush', 'commit'):
            patch.setattr(db.session, failure, fail)
        elif failure == 'fsync':
            patch.setattr(storage.os, 'fsync', fail)
        elif failure == 'publish':
            patch.setattr(storage.os, 'link', fail)
        else:
            original = storage.tempfile.NamedTemporaryFile
            class FailedWriter:
                def __init__(self, *args, **kwargs):
                    self.file = original(*args, **kwargs)
                    self.name = self.file.name
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    self.file.close()
                def fileno(self):
                    return self.file.fileno()
                def write(self, data):
                    self.file.write(data[:8])
                    self.file.flush()
                    raise OSError('partial-write-error')
            patch.setattr(storage.tempfile, 'NamedTemporaryFile', FailedWriter)
        response = admin.post(NEW, data={**values(), 'csrf_token': csrf})
    assert response.status_code == 503
    assert 'private-' not in response.text and 'partial-write-error' not in response.text
    assert file_snapshot(library) == before_files
    assert snapshot(library) == before_rows
    with library.app_context():
        assert set(db.session.execute(select(AuditEvent.id)).scalars()) == before_events


@pytest.mark.parametrize('existing_row', [False, True])
def test_collisions_never_overwrite_or_remove_existing_data(library, monkeypatch, existing_row):
    admin = login(library, 'admin')
    identifier = records(library)[0][0] if existing_row else str(uuid4())
    root = Path(library.config['DOCUMENT_STORAGE_ROOT'])
    # Use a TXT reference for both a new orphan and an actual existing record.
    if existing_row:
        with library.app_context():
            document = db.session.execute(select(Document).where(Document.format == 'TXT')).scalars().first()
            identifier = document.id
            reference = document.storage_reference
    else:
        reference = identifier + '.txt'
        (root / reference).write_bytes(b'legitimate existing orphan')
    before_files, before_rows = file_snapshot(library), snapshot(library)
    monkeypatch.setattr('app.documents.management.uuid4', lambda: UUID(identifier))
    assert create(admin).status_code == 503
    assert file_snapshot(library) == before_files
    assert snapshot(library) == before_rows
    with library.app_context():
        assert db.session.execute(select(AuditEvent).where(AuditEvent.action == 'document.create')).scalars().all() == []


def test_atomic_publication_is_complete_and_never_visible_as_partial(library, monkeypatch):
    import app.documents.service as storage
    admin = login(library, 'admin')
    before = file_snapshot(library)
    original = storage.os.link
    observed = []
    def observe(source, destination, **kwargs):
        assert not Path(destination).exists()
        data = Path(source).read_bytes()
        assert data.startswith(b'FICTIONAL UNIVERSITY DEMONSTRATION')
        original(source, destination, **kwargs)
        assert Path(destination).read_bytes() == data
        observed.append(Path(destination).name)
    monkeypatch.setattr(storage.os, 'link', observe)
    result = create(admin)
    assert result.status_code == 303 and len(observed) == 1
    after = file_snapshot(library)
    assert set(after) - set(before) == set(observed)
    assert {name: after[name] for name in before} == before
    assert not any(name.startswith('.hv-create-') for name in after)


def test_concurrent_publication_has_one_winner_and_preserves_existing_files(library):
    before = file_snapshot(library)
    reference = str(uuid4()) + '.txt'
    barrier = Barrier(2)
    def worker(data):
        try:
            with library.app_context():
                with staged_document(reference, data) as publish:
                    barrier.wait(timeout=15)
                    publish()
            return True, data
        except FileExistsError:
            return False, data
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, (b'first complete document', b'second complete document')))
    assert sum(won for won, data in results) == 1
    winner = next(data for won, data in results if won)
    after = file_snapshot(library)
    assert after == {**before, reference: winner}


def test_cleanup_preserves_replaced_file_instead_of_deleting_unowned_data(library):
    reference = str(uuid4()) + '.txt'
    root = Path(library.config['DOCUMENT_STORAGE_ROOT'])
    with library.app_context():
        with pytest.raises(RuntimeError):
            with staged_document(reference, b'operation-owned bytes') as publish:
                publish()
                # Simulate an external operator replacing the new entry during failure.
                (root / reference).unlink()
                (root / reference).write_bytes(b'operator replacement must survive')
                raise RuntimeError('rollback')
    assert (root / reference).read_bytes() == b'operator replacement must survive'
    assert not any(p.name.startswith('.hv-create-') for p in root.iterdir())


@pytest.mark.parametrize('reference', ['../outside.txt', 'C:\\outside.txt', 'bad.html', 'not-a-uuid.txt'])
def test_staging_rejects_raw_paths_and_invalid_names(library, reference):
    before = file_snapshot(library)
    with library.app_context():
        with pytest.raises(ValueError):
            with staged_document(reference, b'synthetic'):
                pytest.fail('Invalid reference reached publication')
    assert file_snapshot(library) == before

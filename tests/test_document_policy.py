"""Policy eligibility is independent of classification; no employee bypasses."""
import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Document, User
from test_documents import library as library, login
from test_management import create


@pytest.mark.parametrize('status,sensitivity,classification,eligible', [
    ('active', 'internal', 'normal', True),
    ('active', 'internal', 'decoy', True),
    ('active', 'public', 'decoy', True),
    ('active', 'confidential', 'decoy', False),
    ('active', 'restricted', 'decoy', False),
    ('archived', 'internal', 'decoy', False),
    ('archived', 'public', 'normal', False),
])
def test_policy_listing_direct_access_and_private_metadata(library, status, sensitivity, classification, eligible):
    admin = login(library, 'admin')
    result = create(admin, filename='Policy example.txt', status=status,
                    sensitivity=sensitivity, classification=classification)
    assert result.status_code == 303
    identifier = result.location.rsplit('/', 1)[1]
    with library.app_context():
        reference = db.session.get(Document, identifier).storage_reference
    inventory = admin.get('/dashboard/manage-documents')
    assert 'Employee library policy:' in inventory.text
    assert 'Confidential, Restricted and archived records are excluded' in inventory.text
    assert classification in admin.get(result.location).text
    assert sensitivity in admin.get(result.location).text
    employee = login(library)
    for query in ('', '?q=Policy', '?q=Policy&role=admin&sensitivity=public&status=active&is_decoy=0'):
        page = employee.get('/employee/documents' + query)
        assert page.status_code == 200
        assert ('Policy example.txt' in page.text) is eligible
        for secret in ('is_decoy', 'classification', 'sensitivity', 'storage_reference',
                       'detection_rule', reference, library.config['DOCUMENT_STORAGE_ROOT']):
            assert secret not in page.text
        assert 'decoy' not in page.text.lower()
    for tail in ('', '/download'):
        response = employee.get('/employee/documents/' + identifier + tail + '?role=admin&sensitivity=public')
        assert response.status_code == (200 if eligible else 404)
        combined = response.text + str(response.headers)
        for secret in ('is_decoy', 'classification', 'sensitivity', 'storage_reference',
                       'detection_rule', reference, library.config['DOCUMENT_STORAGE_ROOT']):
            assert secret not in combined
        assert 'decoy' not in combined.lower()
    for path in ('/dashboard/manage-documents', result.location, result.location + '/edit'):
        assert employee.get(path + '?role=admin').status_code == 403
    assert employee.get('/employee/documents/' + identifier[:-1] + 'x').status_code == 404
    if not eligible:
        assert 'Policy example.txt' not in employee.get('/employee').text


def test_deactivated_account_cannot_read_eligible_decoy(library):
    admin = login(library, 'admin')
    identifier = create(admin, classification='decoy').location.rsplit('/', 1)[1]
    employee = login(library)
    with library.app_context():
        db.session.execute(db.update(User).where(User.role == 'employee').values(is_active=False))
        db.session.commit()
    for path in ('/employee/documents', '/employee/documents/' + identifier,
                 '/employee/documents/' + identifier + '/download'):
        assert employee.get(path).location == '/login'

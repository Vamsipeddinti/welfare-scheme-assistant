"""Real PostgreSQL integration tests. Refuse destructive access to an application database."""
import json
import os
from pathlib import Path
import jwt
import pytest
from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.integration


def assert_test_database(test_url, app_url):
    target = make_url(test_url)
    source = make_url(app_url)
    if target.get_backend_name() != 'postgresql' or not target.database or not target.database.endswith('_test'):
        raise RuntimeError('Disposable PostgreSQL database name must end in _test')
    if target.database == source.database:
        raise RuntimeError('Refusing application database')


@pytest.fixture
def client(tmp_path, monkeypatch):
    env = dotenv_values(ROOT / '.env')
    test_url = os.getenv('TEST_DATABASE_URL') or env.get('TEST_DATABASE_URL')
    app_url = os.getenv('APPLICATION_DATABASE_URL') or env.get('DATABASE_URL')
    if not test_url or not app_url:
        pytest.skip('TEST_DATABASE_URL and separate APPLICATION_DATABASE_URL/.env required')
    assert_test_database(test_url, app_url)
    monkeypatch.setenv('DATABASE_URL', test_url)
    monkeypatch.setenv('JWT_SECRET', 'test-fixture-secret-' * 4)
    monkeypatch.setenv('UPLOAD_DIR', str(tmp_path / 'uploads'))
    monkeypatch.setenv('AUTH_RATE_LIMIT', '1000')
    monkeypatch.setenv('EXPENSIVE_RATE_LIMIT', '1000')
    from app.config import settings
    from app.db import engine
    settings.cache_clear()
    engine.cache_clear()
    command.upgrade(Config(str(ROOT / 'backend/alembic.ini')), 'head')
    from app.models import Base
    with engine().begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    from app.cli import seed
    seed()
    from app.main import create_app
    with TestClient(create_app()) as test_client:
        yield test_client
    engine().dispose()
    engine.cache_clear()
    settings.cache_clear()


def register(client, name='citizen'):
    response = client.post('/api/v1/auth/register', json={'username': name, 'email': f'{name}@example.com', 'password': 'A-valid-demo-password-42'})
    assert response.status_code == 201, response.text
    return response.json()


def auth(data):
    return {'Authorization': 'Bearer ' + data['access_token']}


def fixture_profile():
    return json.loads((ROOT / 'data/citizens.json').read_text())[0]['profile']


def test_guard_refuses_application_database():
    with pytest.raises(RuntimeError):
        assert_test_database('postgresql://x@localhost/app', 'postgresql://x@localhost/app')
    with pytest.raises(RuntimeError):
        assert_test_database('postgresql://x@localhost/app_test', 'postgresql://x@localhost/app_test')
    with pytest.raises(RuntimeError):
        assert_test_database('postgresql://x@127.0.0.1/app_test', 'postgresql://x@localhost/app_test')
    with pytest.raises(RuntimeError):
        assert_test_database('postgresql://x@localhost:5432/app_test', 'postgresql://x@localhost/app_test')


def test_sessions_refresh_replay_logout_and_forgery(client):
    data = register(client)
    assert client.get('/api/v1/profile').status_code == 401
    assert client.get('/api/v1/auth/me', headers=auth(data)).json()['role'] == 'citizen'
    assert client.get('/api/v1/admin/analytics', headers=auth(data)).status_code == 403
    assert client.post('/api/v1/auth/register', json={'username': 'citizen', 'email': 'citizen@example.com', 'password': 'different-valid-password'}).status_code == 409
    assert client.post('/api/v1/auth/login', json={'username': 'citizen', 'password': 'wrong'}).status_code == 401
    rotated = client.post('/api/v1/auth/refresh', json={'refresh_token': data['refresh_token']})
    assert rotated.status_code == 200
    assert rotated.json()['refresh_token'] != data['refresh_token']
    assert client.post('/api/v1/auth/refresh', json={'refresh_token': data['refresh_token']}).status_code == 401
    assert client.get('/api/v1/profile', headers=auth(rotated.json())).status_code == 401
    fresh = client.post('/api/v1/auth/login', json={'username': 'citizen', 'password': 'A-valid-demo-password-42'}).json()
    assert client.post('/api/v1/auth/logout', headers=auth(fresh)).status_code == 200
    assert client.get('/api/v1/auth/me', headers=auth(fresh)).status_code == 401
    assert client.post('/api/v1/auth/refresh', json={'refresh_token': fresh['refresh_token']}).status_code == 401
    from app.config import settings
    payload = jwt.decode(data['access_token'], options={'verify_signature': False})
    payload['exp'] -= 100000
    expired = jwt.encode(payload, settings().jwt_secret, algorithm='HS256')
    assert client.get('/api/v1/profile', headers={'Authorization': 'Bearer ' + expired}).status_code == 401
    forged = jwt.encode(payload, 'attacker-key-longer-than-thirty-two-bytes', algorithm='HS256')
    assert client.get('/api/v1/profile', headers={'Authorization': 'Bearer ' + forged}).status_code == 401


def test_profiles_recommendations_and_catalog(client):
    data = register(client)
    headers = auth(data)
    assert client.patch('/api/v1/profile', headers=headers, json={'annual_family_income': -1}).status_code == 422
    result = client.patch('/api/v1/profile', headers=headers, json={'annual_family_income': 0, 'disability_status': False})
    assert result.json()['annual_family_income'] == 0 and result.json()['disability_status'] is False
    assert client.patch('/api/v1/profile', headers=headers, json={'date_of_birth': '2100-01-01'}).status_code == 422
    profile = fixture_profile().copy()
    profile.pop('revision')
    assert client.patch('/api/v1/profile', headers=headers, json=profile).status_code == 200
    result = client.post('/api/v1/schemes/demo-family-support/eligibility', headers=headers)
    assert result.status_code == 200 and result.json()['status'] == 'ELIGIBLE'
    schemes = client.get('/api/v1/schemes?page_size=5').json()
    assert schemes['total'] == 12 and len(schemes['items']) == 5
    families = client.get('/api/v1/schemes?category=family').json()
    assert families['total'] == 2 and all(s['category'] == 'family' for s in families['items'])
    recommended = client.get('/api/v1/recommendations', headers=headers)
    assert recommended.status_code == 200 and recommended.json()
    assert all(x['eligibility']['status'] != 'NOT_ELIGIBLE' for x in recommended.json())
    assert client.get('/api/v1/schemes/demo-family-support/export', headers=headers).status_code == 200


def test_document_flow_ownership_corrections_deletion(client):
    first, other = register(client), register(client, 'second')
    profile = fixture_profile().copy()
    profile.pop('revision')
    client.patch('/api/v1/profile', headers=auth(first), json=profile)
    ids = []
    for filename in ('asha-identity.pdf', 'asha-income.pdf', 'asha-residence.pdf'):
        content = (ROOT / 'data/synthetic_documents' / filename).read_bytes()
        result = client.post('/api/v1/documents', headers=auth(first), files={'file': (filename, content, 'application/pdf')})
        assert result.status_code == 201, result.text
        assert result.json()['status'] == 'PROCESSED'
        ids.append(result.json()['id'])
    document_id = ids[0]
    assert client.get(f'/api/v1/documents/{document_id}/download', headers=auth(other)).status_code == 404
    assert client.patch(f'/api/v1/documents/{document_id}/corrections', headers=auth(other), json={'confirmed': True, 'fields': {'full_name': 'Wrong Name'}}).status_code == 404
    assert client.delete(f'/api/v1/documents/{document_id}', headers=auth(other)).status_code == 404
    ready = client.get('/api/v1/schemes/demo-family-support/readiness', headers=auth(first))
    assert ready.json()['status'] == 'READY', ready.text
    client.patch(f'/api/v1/documents/{document_id}/corrections', headers=auth(first), json={'confirmed': True, 'fields': {'full_name': 'Incorrect Name'}})
    assert client.patch(f'/api/v1/documents/{document_id}/corrections', headers=auth(first), json={'fields': {'full_name': 'No confirmation'}}).status_code == 422
    mismatch = client.get('/api/v1/schemes/demo-family-support/readiness', headers=auth(first)).json()
    assert mismatch['status'] != 'READY'
    corrected = client.patch(f'/api/v1/documents/{document_id}/corrections', headers=auth(first), json={'confirmed': True, 'fields': {'full_name': profile['full_name']}})
    assert corrected.json()['manually_corrected']
    assert client.get('/api/v1/schemes/demo-family-support/readiness', headers=auth(first)).json()['status'] == 'READY'
    assert client.delete(f'/api/v1/documents/{document_id}', headers=auth(first)).status_code == 200
    assert client.get(f'/api/v1/documents/{document_id}/download', headers=auth(first)).status_code == 404
    assert client.get('/api/v1/schemes/demo-family-support/readiness', headers=auth(first)).json()['status'] != 'READY'
    assert client.get('/api/v1/documents', headers=auth(other)).json() == []


def test_upload_failures_and_chat_ownership(client):
    first, other = register(client), register(client, 'other')
    assert client.post('/api/v1/documents', headers=auth(first), files={'file': ('../x.pdf', b'x')}).status_code == 422
    assert client.post('/api/v1/documents', headers=auth(first), files={'file': ('x.exe', b'x')}).status_code == 415
    assert client.post('/api/v1/documents', headers=auth(first), files={'file': ('empty.pdf', b'')}).status_code == 422
    assert client.post('/api/v1/documents', headers=auth(first), files={'file': ('large.pdf', b'x' * (11 * 1024 * 1024))}).status_code == 413
    chunks = (b'x' * 65536 for _ in range(180))
    assert client.post('/api/v1/documents', headers={**auth(first), 'Content-Type': 'multipart/form-data; boundary=test'}, content=chunks).status_code == 413
    for filename, expected in [('spoofed.pdf', 'ERROR'), ('synthetic-image.png', 'NEEDS_OCR'), ('encrypted.pdf', 'ERROR')]:
        path = ROOT / 'data/synthetic_documents' / filename
        if not path.exists() and filename == 'blank.png':
            path = ROOT / 'data/synthetic_documents/blank-image.png'
        if path.exists():
            response = client.post('/api/v1/documents', headers=auth(first), files={'file': (path.name, path.read_bytes())})
            assert response.status_code == 201 and response.json()['status'] == expected, response.text
    session = client.post('/api/v1/chat/sessions', headers=auth(first)).json()['id']
    assert client.get(f'/api/v1/chat/sessions/{session}/messages', headers=auth(other)).status_code == 404
    assert client.post(f'/api/v1/chat/sessions/{session}/messages', headers=auth(other), json={'message': 'hello'}).status_code == 404
    personal = client.post(f'/api/v1/chat/sessions/{session}/messages', headers=auth(first), json={'message': 'Am I eligible?', 'scheme_id': 'demo-family-support'})
    assert personal.status_code == 200 and personal.json()['mode'] == 'deterministic'
    assert personal.json()['eligibility']['status'] == 'POTENTIALLY_ELIGIBLE'
    assert len(client.get(f'/api/v1/chat/sessions/{session}/messages', headers=auth(first)).json()) == 2
    unsupported = client.post(f'/api/v1/chat/sessions/{session}/messages', headers=auth(first), json={'message': 'What will my income tax refund be next week?'})
    assert unsupported.status_code == 200 and unsupported.json()['status'] == 'INSUFFICIENT_INFORMATION'


def test_admin_publication_validation_metrics_and_seed_idempotence(client):
    admin = register(client, 'administrator')
    from app.db import engine
    from app.models import User
    with Session(engine()) as db:
        row = db.scalar(select(User).where(User.username == 'administrator'))
        row.role = 'admin'
        db.commit()
    headers = auth(admin)
    schemes = client.get('/api/v1/admin/schemes', headers=headers).json()
    scheme = schemes[0]
    invalid = {**scheme, 'required_documents': [{'id': 'bad', 'any_of': ['identity_proof'], 'mandatory': 'yes'}]}
    assert client.put(f'/api/v1/admin/schemes/{scheme["id"]}', headers=headers, json=invalid).status_code == 422
    original_version = scheme['version']
    for malformed in [dict(coverage=[]), dict(source={'title': 'Demo', 'passage': {}, 'reference': 'local'}),
                      dict(required_documents=[{'id': {}, 'any_of': ['identity_proof']}]),
                      dict(required_documents=[{'id': 'bad', 'any_of': ['identity_proof'], 'fields': [{}]}])]:
        assert client.put(f'/api/v1/admin/schemes/{scheme["id"]}', headers=headers, json={**scheme, **malformed}).status_code == 422
    scheme['name'] += ' updated'
    changed = client.put(f'/api/v1/admin/schemes/{scheme["id"]}', headers=headers, json=scheme)
    assert changed.status_code == 200 and changed.json()['version'] == original_version + 1
    assert client.get(f'/api/v1/schemes/{scheme["id"]}').status_code == 404
    assert client.post(f'/api/v1/admin/schemes/{scheme["id"]}/publish', headers=headers).status_code == 200
    assert client.get(f'/api/v1/schemes/{scheme["id"]}').json()['name'].endswith('updated')
    assert client.post(f'/api/v1/admin/schemes/{scheme["id"]}/archive', headers=headers).status_code == 200
    from app.cli import seed
    seed()
    assert client.get(f'/api/v1/schemes/{scheme["id"]}').status_code == 404
    assert client.get('/api/v1/admin/analytics', headers=headers).json()['schemes'] == 12


def test_preparation_export_is_readable_authenticated_and_escapes_untrusted_content(client):
    import html
    from app.db import engine
    from app.models import User

    admin = register(client, 'export_admin')
    citizen = register(client, 'export_citizen')
    with Session(engine()) as db:
        db.scalar(select(User).where(User.username == 'export_admin')).role = 'admin'
        db.commit()
    headers = auth(admin)
    scheme_id = 'demo-family-support'
    value = client.get(f'/api/v1/schemes/{scheme_id}').json()
    malicious_name = 'Demo <img src=x onerror="alert(1)">'
    malicious_source = '<script>alert("source")</script>'
    value['name'] = malicious_name
    value['source']['title'] = malicious_source
    value['source']['passage'] = f'Fictional fixture source: {malicious_source}'
    value['rules']['all'][0]['source'] = {'reference': malicious_source, 'section': 'Rule evidence'}
    value['application_url'] = 'https://example.test/application?step=1&mode=demo'
    edited = client.put(f'/api/v1/admin/schemes/{scheme_id}', headers=headers, json=value)
    assert edited.status_code == 200, edited.text
    assert client.post(f'/api/v1/admin/schemes/{scheme_id}/publish', headers=headers).status_code == 200
    assert client.get(f'/api/v1/schemes/{scheme_id}/export').status_code == 401
    exported = client.get(f'/api/v1/schemes/{scheme_id}/export', headers=auth(citizen))
    assert exported.status_code == 200
    page = exported.text
    for section in ('Eligibility', 'Requirement explanations', 'Preparation checklist', 'Remaining actions',
                    'Scheme source', 'Application information', 'Your value', 'Encoded condition', 'Reason and evidence'):
        assert section in page
    assert 'More information is needed for eligibility' in page
    assert 'Complete this profile field.' in page
    assert 'Resolve eligibility information: annual family income.' in page
    assert 'No government application has been submitted.' in page
    assert html.escape(malicious_name, quote=True) in page
    assert html.escape(malicious_source, quote=True) in page
    assert '<script' not in page.lower() and '<img' not in page.lower()
    assert '<pre>' not in page
    assert 'href="https://example.test/application?step=1&amp;mode=demo"' in page
    assert "default-src 'none'" in exported.headers['content-security-policy']
    assert 'attachment;' in exported.headers['content-disposition']


def test_missing_synthetic_document_field_requires_confirmed_correction_and_preserves_evidence(client):
    from io import BytesIO
    from reportlab.pdfgen.canvas import Canvas

    citizen = register(client, 'manual_review')
    headers = auth(citizen)
    profile = fixture_profile().copy()
    profile.pop('revision')
    assert client.patch('/api/v1/profile', headers=headers, json=profile).status_code == 200

    def synthetic_pdf(document_type, lines):
        buffer = BytesIO()
        page = Canvas(buffer)
        for index, line in enumerate(['SYNTHETIC DEMONSTRATION DOCUMENT', f'Document Type: {document_type}', *lines]):
            page.drawString(40, 800 - 24 * index, line)
        page.save()
        return buffer.getvalue()

    incomplete_pdf = synthetic_pdf('identity_proof', [f'Full Name: {profile["full_name"]}'])
    uploaded = client.post('/api/v1/documents', headers=headers,
                           files={'file': ('missing-dob.pdf', incomplete_pdf, 'application/pdf')})
    assert uploaded.status_code == 201, uploaded.text
    original = uploaded.json()
    assert original['status'] == 'NEEDS_MANUAL_REVIEW'
    assert original['extracted_fields'] == {'full_name': profile['full_name']}
    assert 'date_of_birth' not in original['evidence']
    document_id = original['id']
    for kind, fields in [
        ('income_certificate', [f'Full Name: {profile["full_name"]}', f'Annual Family Income: {profile["annual_family_income"]}']),
        ('residence_proof', [f'Full Name: {profile["full_name"]}', f'State: {profile["state"]}']),
    ]:
        complete = client.post('/api/v1/documents', headers=headers,
                               files={'file': (f'{kind}.pdf', synthetic_pdf(kind, fields), 'application/pdf')})
        assert complete.status_code == 201 and complete.json()['status'] == 'PROCESSED', complete.text
    before = client.get('/api/v1/schemes/demo-family-support/readiness', headers=headers).json()
    assert before['status'] == 'NEEDS_INFORMATION'
    assert before['percentage'] < 100
    correction_url = f'/api/v1/documents/{document_id}/corrections'
    unconfirmed = client.patch(correction_url, headers=headers, json={'fields': {'date_of_birth': profile['date_of_birth']}})
    assert unconfirmed.status_code == 422
    corrected = client.patch(correction_url, headers=headers,
                             json={'fields': {'date_of_birth': profile['date_of_birth']}, 'confirmed': True})
    assert corrected.status_code == 200, corrected.text
    corrected = corrected.json()
    assert corrected['status'] == 'PROCESSED'
    assert corrected['extraction_status'] == 'NEEDS_MANUAL_REVIEW'
    assert corrected['extracted_fields'] == original['extracted_fields']
    assert corrected['evidence'] == original['evidence']
    assert corrected['corrections']['date_of_birth'] == profile['date_of_birth']
    assert corrected['fields']['date_of_birth'] == profile['date_of_birth']
    assert all(check['status'] == 'MATCH' for check in corrected['checks'])
    assert corrected['correction_events'][-1]['provenance'] == 'user-confirmed'
    assert corrected['correction_events'][-1]['user_id'] == citizen['user']['id']
    assert corrected['correction_events'][-1]['at']
    after = client.get('/api/v1/schemes/demo-family-support/readiness', headers=headers).json()
    assert after['status'] == 'READY' and after['percentage'] == 100
    identity_item = next(item for item in after['items'] if item.get('document_id') == document_id)
    assert identity_item['manual_confirmation'] is True
    assert 'not independently verified' in identity_item['evidence_label']

"""Prepare/check a synthetic persistence probe across an intentional service restart."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import httpx

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'runtime/persistence-probe.json'
parser = argparse.ArgumentParser()
parser.add_argument('phase', choices=['prepare', 'check'])
args = parser.parse_args()
with httpx.Client(base_url=os.getenv('PROBE_API_URL', 'http://127.0.0.1:8000/api/v1'), timeout=90) as client:
    if args.phase == 'prepare':
        username = 'persist_' + secrets.token_hex(6)
        password = secrets.token_urlsafe(20)
        result = client.post('/auth/register', json={'username': username, 'email': username + '@example.com', 'password': password})
        result.raise_for_status()
        token = result.json()['access_token']
        client.headers['Authorization'] = 'Bearer ' + token
        result = client.patch('/profile', json={'full_name': 'Asha Rao', 'date_of_birth': '1988-04-12', 'annual_family_income': 120000})
        result.raise_for_status()
        content = (ROOT / 'data/synthetic_documents/asha-identity.pdf').read_bytes()
        result = client.post('/documents', files={'file': ('identity.pdf', content, 'application/pdf')})
        result.raise_for_status()
        doc_id = result.json()['id']
        result = client.post('/chat/sessions')
        result.raise_for_status()
        session = result.json()['id']
        result = client.post(f'/chat/sessions/{session}/messages', json={'message': 'What is the income limit for Demo Family Support?', 'scheme_id': 'demo-family-support'})
        result.raise_for_status()
        assert result.json()['status'] == 'ANSWERED' and result.json()['citations']
        state = dict(username=username, password=password, access_token=token, document_id=doc_id, session_id=session,
                     sha256=hashlib.sha256(content).hexdigest(), answer=result.json()['answer'], prepared_at=datetime.now(timezone.utc).isoformat())
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state), encoding='utf-8')
        print('Synthetic persistence probe prepared; credentials retained only in ignored runtime/. Restart services, then run check.')
    else:
        state = json.loads(STATE.read_text(encoding='utf-8'))
        client.headers['Authorization'] = 'Bearer ' + state['access_token']
        profile = client.get('/profile')
        profile.raise_for_status()
        assert profile.json()['full_name'] == 'Asha Rao'
        result = client.get(f'/documents/{state["document_id"]}/download')
        result.raise_for_status()
        assert hashlib.sha256(result.content).hexdigest() == state['sha256']
        result = client.get(f'/chat/sessions/{state["session_id"]}/messages')
        result.raise_for_status()
        assert any(x.get('content') == state['answer'] for x in result.json())
        result = client.post(f'/chat/sessions/{state["session_id"]}/messages', json={'message': 'What is the income limit for Demo Family Support?', 'scheme_id': 'demo-family-support'})
        result.raise_for_status()
        assert result.json()['status'] == 'ANSWERED' and result.json()['citations']
        evidence = dict(status='PASS', prepared_at=state['prepared_at'], checked_at=datetime.now(timezone.utc).isoformat(),
                        checks=['server session and profile', 'private file SHA256', 'chat history', 'real cited local retrieval after restart'])
        target = ROOT / 'artifacts/test-results/persistence.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print('PASS: session/profile, uploaded file, history and real retrieval persisted across the requested restart.')

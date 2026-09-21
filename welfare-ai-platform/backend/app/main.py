import html
import logging
import re
import threading
import time
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .config import settings
from .db import get_db
from .models import User, Profile, LoginSession, RefreshToken, Scheme, Document, Evaluation, ChatSession, ChatMessage, now, uid
from .security import admin_user, current_user, current_session, check_password, digest, hash_password, issue_tokens, unauthorized, user_view
from . import domain

log = logging.getLogger('welfare')


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_.-]+$')
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=256)


class CorrectionRequest(BaseModel):
    fields: dict
    confirmed: bool = False


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    scheme_id: str | None = Field(default=None, max_length=80)


def profile_data(db, user):
    row = db.get(Profile, user.id)
    return {**(row.data if row else {}), 'revision': row.revision if row else 0}


def scheme_data(row):
    return {**row.data, 'id': row.id, 'version': row.version, 'active': row.active}


def active_schemes(db):
    return [scheme_data(s) for s in db.scalars(select(Scheme).where(Scheme.active.is_(True)).order_by(Scheme.id))]


def get_scheme(db, scheme_id, active=True):
    row = db.get(Scheme, scheme_id)
    if row is None or (active and not row.active):
        raise HTTPException(404, 'Scheme not found')
    return row


def owned(db, model, item_id, user):
    row = db.get(model, item_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, 'Resource not found')
    return row


def document_view(row, profile):
    from .documents import consistency, DOCUMENT_FIELDS
    fields = {**row.result.get('fields', {}), **row.corrections}
    status = row.result.get('status')
    required = DOCUMENT_FIELDS.get(row.result.get('document_type'), ())
    if status == 'NEEDS_MANUAL_REVIEW' and required and row.corrections and all(fields.get(f) is not None for f in required):
        status = 'PROCESSED'
    return {**row.result, 'id': row.id, 'original_filename': row.original_filename,
            'status': status, 'extraction_status': row.result.get('status'),
            'size_bytes': row.size_bytes, 'created_at': row.created_at.isoformat(),
            'fields': fields, 'extracted_fields': row.result.get('fields', {}),
            'corrections': row.corrections, 'manually_corrected': bool(row.corrections),
            'checks': consistency(profile, fields, row.result.get('document_type'))}


def user_documents(db, user):
    profile = profile_data(db, user)
    return [document_view(row, profile) for row in db.scalars(
        select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc()))]


@lru_cache
def knowledge():
    from .rag import SchemeKnowledge
    cfg = settings()
    return SchemeKnowledge(cfg.chroma_dir, cfg.model_dir, cfg.embedding_revision)


def validate_scheme(data):
    if not isinstance(data, dict):
        raise ValueError('Scheme must be an object')
    for key in ('id', 'name', 'category', 'description', 'benefits', 'application_procedure'):
        if not isinstance(data.get(key), str) or not data[key].strip() or len(data[key]) > 15000:
            raise ValueError(f'{key} must be a nonempty text value')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', data['id']):
        raise ValueError('Invalid scheme ID')
    domain.validate_rule(data.get('rules'))
    if not isinstance(data.get('coverage'), str) or data['coverage'] not in {'complete', 'incomplete', 'stale'}:
        raise ValueError('coverage must be complete, incomplete or stale')
    if not isinstance(data.get('is_fictional'), bool):
        raise ValueError('Explicit is_fictional flag required')
    source = data.get('source')
    if not isinstance(source, dict) or any(not isinstance(source.get(k), str) or not source[k].strip() for k in ('title', 'passage')):
        raise ValueError('Source title and supporting passage required')
    if any(source.get(k) is not None and not isinstance(source[k], str) for k in ('reference', 'url', 'section')):
        raise ValueError('Source reference, URL and section must be text')
    if not (source.get('reference') or source.get('url')):
        raise ValueError('Source reference or URL required')
    if not data['is_fictional'] and not str(source.get('url') or '').startswith('https://'):
        raise ValueError('Real schemes require an HTTPS source URL')
    for url in (source.get('url'), data.get('application_url')):
        if url and (not isinstance(url, str) or not url.startswith('https://')):
            raise ValueError('Only HTTPS source/application URLs are accepted')
    fields = data.get('required_fields', [])
    if not isinstance(fields, list) or any(not isinstance(x, str) for x in fields):
        raise ValueError('required_fields must be a list')
    domain.validate_profile(dict.fromkeys(fields))
    docs = data.get('required_documents', [])
    if not isinstance(docs, list):
        raise ValueError('required_documents must be a list')
    for group in docs:
        if not isinstance(group, dict) or not isinstance(group.get('id'), str) or not group['id'].strip() or not group.get('any_of'):
            raise ValueError('Document groups require id and nonempty any_of')
        if not isinstance(group['any_of'], list) or any(not isinstance(x, str) for x in group['any_of']):
            raise ValueError('Document alternatives must be strings')
        if 'condition' in group:
            domain.validate_rule(group['condition'])
        group_fields = group.get('fields', [])
        if not isinstance(group_fields, list) or any(not isinstance(x, str) for x in group_fields):
            raise ValueError('Document fields must be a list of strings')
        domain.validate_profile(dict.fromkeys(group_fields))
    if len({g['id'] for g in docs}) != len(docs):
        raise ValueError('Document group IDs must be unique')
    domain.readiness(data, {}, [])
    return data


def create_app():
    from .body_limit import BodyLimitMiddleware
    cfg = settings()
    app = FastAPI(title='Welfare Scheme Assistant', version='1.0.0', docs_url='/api/docs', redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=cfg.cors_origins.split(','),
                       allow_credentials=False, allow_methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'],
                       allow_headers=['Authorization', 'Content-Type'])
    app.add_middleware(BodyLimitMiddleware, upload_limit=cfg.max_upload_bytes)
    buckets = defaultdict(deque)
    bucket_lock = threading.Lock()

    @app.middleware('http')
    async def boundaries(request: Request, call_next):
        path = request.url.path
        if request.method in {'POST', 'PUT', 'PATCH'}:
            length = request.headers.get('content-length')
            limit = cfg.max_upload_bytes + 65536 if path.endswith('/documents') else 100000
            if length and (not length.isdigit() or int(length) > limit):
                return JSONResponse({'detail': 'Request too large'}, status_code=413)
        category = 'auth' if '/auth/' in path else 'expensive' if '/chat/' in path or path.endswith('/documents') else None
        if category and request.method == 'POST':
            # Do not trust forwarded headers; one backend worker is the documented local topology.
            key = (request.client.host if request.client else 'unknown', category)
            timestamp = time.monotonic()
            maximum = cfg.auth_rate_limit if category == 'auth' else cfg.expensive_rate_limit
            with bucket_lock:
                bucket = buckets[key]
                while bucket and bucket[0] < timestamp - 60:
                    bucket.popleft()
                if len(bucket) >= maximum:
                    return JSONResponse({'detail': 'Too many requests. Try again shortly.'}, status_code=429,
                                        headers={'Retry-After': '60'})
                bucket.append(timestamp)
                if len(buckets) > 10000:
                    for old_key in list(buckets):
                        if not buckets[old_key] or buckets[old_key][-1] < timestamp - 60:
                            del buckets[old_key]
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        log.error('Database operation failed: %s', type(exc).__name__)
        return JSONResponse({'detail': 'The database is temporarily unavailable. Please retry.'}, status_code=503)

    @app.exception_handler(ValueError)
    async def invalid_input(request, exc):
        return JSONResponse({'detail': str(exc)[:500]}, status_code=422)

    @app.get('/api/health')
    def health(db=Depends(get_db)):
        db.execute(text('SELECT 1'))
        return {'status': 'ok', 'database': 'postgresql', 'chat_mode': cfg.llm_mode}

    prefix = '/api/v1'

    @app.post(prefix + '/auth/register', status_code=201)
    def register(body: RegisterRequest, db=Depends(get_db)):
        user = User(username=body.username.lower(), email=str(body.email).lower(), password_hash=hash_password(body.password))
        try:
            db.add(user)
            db.flush()
            db.add(Profile(user_id=user.id, data={}))
            return issue_tokens(db, user)
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'Username or email is already registered') from None

    @app.post(prefix + '/auth/login')
    def login(body: LoginRequest, db=Depends(get_db)):
        user = db.scalar(select(User).where(User.username == body.username.lower()))
        valid = check_password(body.password, user.password_hash if user else None)
        if not user or not valid or not user.active:
            raise HTTPException(401, 'Invalid credentials')
        return issue_tokens(db, user)

    @app.post(prefix + '/auth/refresh')
    def refresh(body: RefreshRequest, db=Depends(get_db)):
        token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest(body.refresh_token)).with_for_update())
        if token is None:
            raise unauthorized()
        session = db.scalar(select(LoginSession).where(LoginSession.id == token.session_id).with_for_update())
        if not session or session.revoked or session.expires_at <= now():
            raise unauthorized()
        if token.used:
            session.revoked = True
            db.commit()
            raise unauthorized()
        user = db.get(User, session.user_id)
        if not user or not user.active:
            raise unauthorized()
        token.used = True
        return issue_tokens(db, user, session)

    @app.post(prefix + '/auth/logout')
    def logout(pair=Depends(current_session), db=Depends(get_db)):
        pair[1].revoked = True
        db.commit()
        return {'message': 'Session revoked'}

    @app.get(prefix + '/auth/me')
    def me(user=Depends(current_user)):
        return user_view(user)

    @app.get(prefix + '/profile')
    def profile(user=Depends(current_user), db=Depends(get_db)):
        result = profile_data(db, user)
        return {**result, 'completeness': domain.completeness(result)}

    @app.patch(prefix + '/profile')
    def update_profile(body: dict, user=Depends(current_user), db=Depends(get_db)):
        if 'revision' in body or 'completeness' in body:
            raise HTTPException(422, 'Metadata fields cannot be updated')
        normalized = domain.validate_profile(body)
        row = db.scalar(select(Profile).where(Profile.user_id == user.id).with_for_update())
        if row is None:
            row = Profile(user_id=user.id, data={}, revision=0)
            db.add(row)
        row.data = {**row.data, **normalized}
        row.revision += 1
        db.commit()
        return profile(user, db)

    @app.get(prefix + '/schemes')
    def schemes(q: str = Query('', max_length=200), state: str = '', category: str = '',
                page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db=Depends(get_db)):
        rows = active_schemes(db)
        if q:
            rows = [s for s in rows if q.casefold() in (s['name'] + ' ' + s['description']).casefold()]
        if category:
            rows = [s for s in rows if s['category'].casefold() == category.casefold()]
        if state:
            rows = [s for s in rows if str(s.get('jurisdiction', 'all')).casefold() in {'all', 'india', 'national'}
                    or state.casefold() in str(s.get('jurisdiction', '')).casefold()]
        return {'items': rows[(page - 1) * page_size:page * page_size], 'total': len(rows), 'page': page, 'page_size': page_size}

    @app.get(prefix + '/schemes/{scheme_id}')
    def scheme_detail(scheme_id: str, db=Depends(get_db)):
        return scheme_data(get_scheme(db, scheme_id))

    @app.post(prefix + '/schemes/{scheme_id}/eligibility')
    def check_eligibility(scheme_id: str, user=Depends(current_user), db=Depends(get_db)):
        result = domain.eligibility(scheme_data(get_scheme(db, scheme_id)), profile_data(db, user))
        db.add(Evaluation(user_id=user.id, scheme_id=scheme_id, status=result['status'], result=result))
        db.commit()
        return result

    @app.get(prefix + '/recommendations')
    def recommend(include_ineligible: bool = False, user=Depends(current_user), db=Depends(get_db)):
        ranked = domain.recommendations(active_schemes(db), profile_data(db, user), include_ineligible)
        return [{**item['scheme'], **{key: value for key, value in item.items() if key != 'scheme'}} for item in ranked]

    @app.get(prefix + '/documents')
    def documents(user=Depends(current_user), db=Depends(get_db)):
        return user_documents(db, user)

    @app.post(prefix + '/documents', status_code=201)
    def upload_document(file: UploadFile = File(...), user=Depends(current_user), db=Depends(get_db)):
        from .documents import extract_document
        original = file.filename or ''
        if not original or '/' in original or '\\' in original or len(original) > 255:
            raise HTTPException(422, 'Invalid filename')
        suffix = Path(original).suffix.lower()
        if suffix not in {'.pdf', '.png', '.jpg', '.jpeg'}:
            raise HTTPException(415, 'Only PDF, PNG and JPEG files are accepted')
        cfg.upload_dir.mkdir(parents=True, exist_ok=True)
        stored = uid() + suffix
        path = cfg.upload_dir / stored
        size = 0
        try:
            with path.open('xb') as output:
                while chunk := file.file.read(65536):
                    size += len(chunk)
                    if size > cfg.max_upload_bytes:
                        raise HTTPException(413, 'File exceeds upload limit')
                    output.write(chunk)
            if not size:
                raise HTTPException(422, 'File is empty')
            result = extract_document(path, original, cfg.max_upload_bytes)
            row = Document(user_id=user.id, original_filename=original, stored_name=stored,
                           size_bytes=size, result=result, corrections={})
            db.add(row)
            db.commit()
            db.refresh(row)
            return document_view(row, profile_data(db, user))
        except Exception:
            db.rollback()
            path.unlink(missing_ok=True)
            raise
        finally:
            file.file.close()

    @app.get(prefix + '/documents/{document_id}/download')
    def download_document(document_id: str, user=Depends(current_user), db=Depends(get_db)):
        row = owned(db, Document, document_id, user)
        path = cfg.upload_dir / row.stored_name
        if not path.is_file():
            raise HTTPException(404, 'Stored file is unavailable')
        return FileResponse(path, media_type='application/octet-stream', filename=row.original_filename)

    @app.patch(prefix + '/documents/{document_id}/corrections')
    def correct_document(document_id: str, body: CorrectionRequest, user=Depends(current_user), db=Depends(get_db)):
        from .documents import DOCUMENT_FIELDS
        row = owned(db, Document, document_id, user)
        if not body.confirmed:
            raise HTTPException(422, 'Explicit confirmation of document corrections is required')
        if row.result.get('status') not in {'PROCESSED', 'NEEDS_MANUAL_REVIEW'} or row.result.get('document_type') not in DOCUMENT_FIELDS:
            raise HTTPException(409, 'Corrections require a recognized text-based synthetic document; OCR and unknown formats remain unresolved')
        allowed = set(DOCUMENT_FIELDS[row.result['document_type']])
        if set(body.fields) - allowed:
            raise HTTPException(422, 'Unsupported correction field')
        row.corrections = {**row.corrections, **domain.validate_profile(body.fields)}
        row.result = {**row.result, 'correction_events': [*row.result.get('correction_events', []),
                      {'at': now().isoformat(), 'user_id': user.id, 'fields': list(body.fields), 'provenance': 'user-confirmed'}]}
        db.commit()
        return document_view(row, profile_data(db, user))

    @app.delete(prefix + '/documents/{document_id}')
    def delete_document(document_id: str, user=Depends(current_user), db=Depends(get_db)):
        row = owned(db, Document, document_id, user)
        path = cfg.upload_dir / row.stored_name
        path.unlink(missing_ok=True)
        db.delete(row)
        db.commit()
        return {'message': 'Document and extracted data deleted'}

    @app.get(prefix + '/schemes/{scheme_id}/readiness')
    def readiness(scheme_id: str, user=Depends(current_user), db=Depends(get_db)):
        return domain.readiness(scheme_data(get_scheme(db, scheme_id)), profile_data(db, user), user_documents(db, user))

    @app.get(prefix + '/schemes/{scheme_id}/export')
    def export(scheme_id: str, user=Depends(current_user), db=Depends(get_db)):
        scheme = scheme_data(get_scheme(db, scheme_id))
        result = readiness(scheme_id, user, db)
        outcome = result['eligibility']

        def escaped(value):
            return html.escape(str(value), quote=True)

        def display(value):
            if value is None:
                return 'Not provided'
            if type(value) is bool:
                return 'Yes' if value else 'No'
            if isinstance(value, list):
                return ', '.join(display(item) for item in value)
            return str(value)

        def source_label(value):
            if isinstance(value, dict):
                return ' — '.join(str(value[key]) for key in ('title', 'reference', 'url', 'section') if value.get(key)) or 'See scheme source below'
            return str(value) if value else 'See scheme source below'

        labels = {'PASS': 'Matches', 'FAIL': 'Does not match', 'UNKNOWN': 'More information needed',
                  'ELIGIBLE': 'Matches the encoded eligibility rules', 'NOT_ELIGIBLE': 'Does not match the encoded eligibility rules',
                  'POTENTIALLY_ELIGIBLE': 'More information is needed for eligibility', 'SATISFIED': 'Satisfied',
                  'MISSING': 'Missing', 'MISMATCH': 'Mismatch', 'READY': 'Ready for application preparation',
                  'INCOMPLETE': 'Preparation incomplete', 'NEEDS_INFORMATION': 'More information needed',
                  'NOT_APPLICABLE': 'No applicable mandatory checklist items'}

        def trace_rows(node, path='1'):
            children = node.get('children', [])
            if children:
                requirement = 'All requirements in this group' if node.get('group') == 'all' else 'At least one alternative in this group'
                used, expected = '—', 'Every child must match' if node.get('group') == 'all' else 'One matching child is sufficient'
            else:
                requirement = str(node.get('field', 'Requirement')).replace('_', ' ').capitalize()
                used = display(node.get('value'))
                expected = f"{node.get('op', '')} {display(node.get('expected'))}"
            row = (f'<tr><th scope="row">{escaped(path)}. {escaped(requirement)}</th>'
                   f'<td>{escaped(labels.get(node.get("result"), node.get("result", "UNKNOWN")))}</td>'
                   f'<td>{escaped(used)}</td><td>{escaped(expected)}</td>'
                   f'<td>{escaped(node.get("reason", ""))}<br><small>Source: {escaped(source_label(node.get("source")))}</small></td></tr>')
            return row + ''.join(trace_rows(child, f'{path}.{index}') for index, child in enumerate(children, 1))

        rule_rows = trace_rows(outcome['trace'])
        rows = ''.join(
            f'<tr><th scope="row">{escaped(item.get("label", item.get("id", "Requirement")))}</th>'
            f'<td>{"Required" if item.get("mandatory") else "Optional"}</td>'
            f'<td>{escaped(labels.get(item.get("status"), item.get("status", "UNKNOWN")))}</td>'
            f'<td>{escaped(item.get("reason", ""))}'
            f'{"<br><small>" + escaped(item["evidence_label"]) + "</small>" if item.get("evidence_label") else ""}</td></tr>'
            for item in result['items'])
        if not rows:
            rows = '<tr><td colspan="4">No mandatory or optional checklist items apply.</td></tr>'
        actions = list(result.get('remaining_actions', []))
        actions.extend(f"Resolve eligibility information: {field.replace('_', ' ')}." for field in outcome.get('missing_information', []))
        if outcome['status'] == 'NOT_ELIGIBLE':
            actions.append('Review the requirements marked “Does not match”. Complete paperwork does not override an ineligible result.')
        if not actions:
            actions.append('Review the current source and application information before taking any next step. This summary does not submit an application.')
        remaining = ''.join(f'<li>{escaped(action)}</li>' for action in dict.fromkeys(actions))
        source = scheme.get('source', {})
        link = scheme.get('application_url')
        link_label = 'Demonstration application information' if scheme.get('is_fictional') else 'Official application page'
        application = f'<a href="{escaped(link)}" rel="noreferrer">{link_label}</a>' if link else 'No verified application link.'
        percentage = 'Not applicable' if result['percentage'] is None else f"{result['percentage']:g}%"
        page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Preparation checklist — {escaped(scheme['name'])}</title>
        <style>body{{font:15px system-ui;max-width:1000px;margin:32px auto;padding:0 20px;line-height:1.5;color:#163c34}}
        h1,h2{{line-height:1.2}}h2{{margin-top:28px}}table{{width:100%;border-collapse:collapse;font-size:13px;table-layout:fixed}}
        th,td{{border:1px solid #9cb3ac;padding:9px;text-align:left;vertical-align:top;overflow-wrap:anywhere}}thead{{background:#edf5f1}}
        small{{color:#385e52}}li{{margin:8px 0}}a{{color:#145640;overflow-wrap:anywhere}}.notice{{padding:12px;border:1px solid #9cb3ac}}
        @media print{{body{{max-width:none;margin:0;padding:0;font-size:11px}}table{{font-size:9px}}thead{{display:table-header-group}}tr{{break-inside:avoid}}h2{{break-after:avoid}}}}</style></head><body>
        <h1>{escaped(scheme['name'])}</h1><p>Preparation summary — {escaped(now().date())}</p>
        <p>{'Fictional demonstration scheme.' if scheme.get('is_fictional') else 'Guidance based on encoded requirements.'}</p>
        <p>{escaped(scheme.get('description', ''))}</p><p><strong>Benefits described:</strong> {escaped(scheme.get('benefits', ''))}</p>
        <p><strong>Preparation status:</strong> {escaped(labels.get(result['status'], result['status']))}<br>
        <strong>Checklist completion:</strong> {escaped(percentage)} ({result['satisfied_mandatory']} of {result['applicable_mandatory']} mandatory items satisfied)</p>
        <h2>Eligibility</h2><p><strong>{escaped(labels.get(outcome['status'], outcome['status']))}</strong></p>
        <p>{escaped(outcome.get('explanation', ''))}</p>
        <p>Evaluation date: {escaped(outcome['evaluation_date'])} · Rule version: {escaped(outcome['rule_version'])} · Profile revision: {escaped(outcome['profile_revision'])}<br>
        Rule coverage: {escaped(outcome.get('coverage', 'incomplete'))}</p>
        <h2>Requirement explanations</h2><p>A passing alternative group needs only one matching branch. Other alternatives may fail or remain unanswered without changing that passing group.</p>
        <table aria-label="Eligibility requirement explanations"><thead><tr><th>Requirement</th><th>Result</th><th>Your value</th><th>Encoded condition</th><th>Explanation and source</th></tr></thead><tbody>{rule_rows}</tbody></table>
        <h2>Preparation checklist</h2><table aria-label="Preparation checklist"><thead><tr><th>Item</th><th>Requirement</th><th>Status</th><th>Reason and evidence</th></tr></thead><tbody>{rows}</tbody></table>
        <h2>Remaining actions</h2><ul>{remaining}</ul>
        <h2>Scheme source</h2><p><strong>{escaped(source.get('title', ''))}</strong><br>{escaped(source.get('url') or source.get('reference', ''))}<br>
        Publisher: {escaped(source.get('publisher') or 'Not recorded')}<br>Source retrieval date: {escaped(source.get('retrieved_at') or 'Not recorded; local fictional fixtures are not government verification')}</p>
        <p>{escaped(source.get('passage', ''))}</p><h2>Application information</h2><p>{escaped(scheme.get('application_procedure', ''))}</p><p>{application}</p>
        <p class="notice">This is application preparation guidance, not official entitlement, approval, or document authentication. User-confirmed corrections are not independently verified. No government application has been submitted.</p>
        </body></html>'''
        return HTMLResponse(page, headers={'Content-Disposition': f'attachment; filename="{scheme_id}-checklist.html"',
                                          'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'"})

    @app.get(prefix + '/chat/sessions')
    def chat_sessions(user=Depends(current_user), db=Depends(get_db)):
        return [{'id': s.id, 'created_at': s.created_at} for s in db.scalars(select(ChatSession).where(
            ChatSession.user_id == user.id).order_by(ChatSession.created_at.desc()))]

    @app.post(prefix + '/chat/sessions', status_code=201)
    def new_chat(user=Depends(current_user), db=Depends(get_db)):
        row = ChatSession(user_id=user.id)
        db.add(row)
        db.commit()
        return {'id': row.id, 'created_at': row.created_at}

    @app.get(prefix + '/chat/sessions/{session_id}/messages')
    def messages(session_id: str, user=Depends(current_user), db=Depends(get_db)):
        owned(db, ChatSession, session_id, user)
        return [{'id': m.id, **m.data, 'created_at': m.created_at} for m in db.scalars(select(ChatMessage).where(
            ChatMessage.session_id == session_id).order_by(ChatMessage.created_at, ChatMessage.id))]

    @app.post(prefix + '/chat/sessions/{session_id}/messages')
    def message(session_id: str, body: MessageRequest, user=Depends(current_user), db=Depends(get_db)):
        from .rag import is_personal_question, INJECTION, UNSUPPORTED
        owned(db, ChatSession, session_id, user)
        schemes = active_schemes(db)
        if body.scheme_id:
            get_scheme(db, body.scheme_id)
        personal = is_personal_question(body.message) and not INJECTION.search(body.message) and not UNSUPPORTED.search(body.message)
        if personal:
            if body.scheme_id:
                scheme = scheme_data(get_scheme(db, body.scheme_id))
                result = domain.eligibility(scheme, profile_data(db, user))
                response = {'answer': f'Your encoded-rule result is {result["status"]}. This is guidance, not official approval.',
                            'citations': [], 'mode': 'deterministic', 'status': 'answered', 'eligibility': result}
            else:
                response = {'answer': 'Choose a scheme so I can evaluate its rules against your saved profile.',
                            'citations': [], 'mode': 'deterministic', 'status': 'needs_scheme'}
        else:
            try:
                response = knowledge().answer(body.message, schemes, body.scheme_id,
                                              cfg.llm_mode, cfg.llm_api_key or None, cfg.llm_model or None)
            except (RuntimeError, OSError, ImportError) as exc:
                log.warning('Knowledge service unavailable: %s', type(exc).__name__)
                raise HTTPException(503, 'Knowledge service unavailable. Prepare the pinned model cache and run the index command; check server logs.') from None
        db.add(ChatMessage(session_id=session_id, data={'role': 'user', 'content': body.message}))
        db.add(ChatMessage(session_id=session_id, data={'role': 'assistant', 'content': response['answer'], **response}))
        db.commit()
        return response

    @app.get(prefix + '/admin/schemes')
    def admin_schemes(user=Depends(admin_user), db=Depends(get_db)):
        return [scheme_data(s) for s in db.scalars(select(Scheme).order_by(Scheme.id))]

    @app.post(prefix + '/admin/schemes', status_code=201)
    def create_scheme(body: dict, user=Depends(admin_user), db=Depends(get_db)):
        data = validate_scheme(body)
        if db.get(Scheme, data['id']):
            raise HTTPException(409, 'Scheme ID already exists')
        row = Scheme(id=data['id'], data=data, version=1, active=False)
        db.add(row)
        db.commit()
        return scheme_data(row)

    @app.put(prefix + '/admin/schemes/{scheme_id}')
    def edit_scheme(scheme_id: str, body: dict, user=Depends(admin_user), db=Depends(get_db)):
        row = get_scheme(db, scheme_id, active=False)
        if body.get('id') != scheme_id:
            raise HTTPException(422, 'Scheme ID cannot change')
        row.data = validate_scheme(body)
        row.version += 1
        # Changes require explicit republishing. All query results are recalculated from current content.
        row.active = False
        db.commit()
        return scheme_data(row)

    @app.post(prefix + '/admin/schemes/{scheme_id}/publish')
    def publish(scheme_id: str, user=Depends(admin_user), db=Depends(get_db)):
        row = get_scheme(db, scheme_id, active=False)
        validate_scheme(scheme_data(row))
        row.active = True
        db.commit()
        return scheme_data(row)

    @app.post(prefix + '/admin/schemes/{scheme_id}/archive')
    def archive(scheme_id: str, user=Depends(admin_user), db=Depends(get_db)):
        row = get_scheme(db, scheme_id, active=False)
        row.active = False
        db.commit()
        return scheme_data(row)

    @app.get(prefix + '/admin/analytics')
    def analytics(user=Depends(admin_user), db=Depends(get_db)):
        def count(model):
            return db.scalar(select(func.count()).select_from(model))
        outcomes = dict(db.execute(select(Evaluation.status, func.count()).group_by(Evaluation.status)).all())
        document_status = Document.result['status'].astext.label('document_status')
        documents = dict(db.execute(select(document_status, func.count()).group_by(document_status)).all())
        return {'users': count(User), 'schemes': count(Scheme), 'active_schemes': db.scalar(select(func.count()).select_from(Scheme).where(Scheme.active.is_(True))),
                'evaluations': count(Evaluation), 'evaluation_statuses': outcomes, 'documents': count(Document),
                'document_statuses': documents, 'chat_sessions': count(ChatSession),
                'definitions': {'evaluations': 'Historical explicit eligibility checks, including previous profile and rule revisions.',
                                'documents': 'Currently stored documents only.', 'users': 'All registered users including administrators.'}}

    if cfg.static_dir is not None:
        from .static_site import ReactApplication
        app.mount('/', ReactApplication(cfg.static_dir), name='web')
    return app


app = create_app()

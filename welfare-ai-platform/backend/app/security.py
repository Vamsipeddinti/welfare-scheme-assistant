import hashlib
import secrets
from datetime import timedelta
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User, LoginSession, RefreshToken, now

password_hasher = PasswordHasher()
dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))
bearer = HTTPBearer(auto_error=False)


def hash_password(password):
    return password_hasher.hash(password)


def check_password(password, hashed):
    try:
        return password_hasher.verify(hashed or dummy_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def user_view(user):
    return {'id': user.id, 'username': user.username, 'email': user.email, 'role': user.role}


def issue_tokens(db: Session, user: User, session=None):
    cfg = settings()
    if session is None:
        session = LoginSession(user_id=user.id, expires_at=now() + timedelta(days=cfg.refresh_days))
        db.add(session)
        db.flush()
    refresh = secrets.token_urlsafe(48)
    db.add(RefreshToken(token_hash=digest(refresh), session_id=session.id))
    issued = now()
    access = jwt.encode({'sub': user.id, 'sid': session.id, 'iat': issued,
                         'exp': min(issued + timedelta(minutes=cfg.access_minutes), session.expires_at),
                         'iss': cfg.jwt_issuer, 'aud': 'welfare-web'}, cfg.jwt_secret, algorithm='HS256')
    db.commit()
    return {'access_token': access, 'refresh_token': refresh, 'token_type': 'bearer', 'user': user_view(user)}


def unauthorized():
    return HTTPException(401, 'Invalid or expired session', headers={'WWW-Authenticate': 'Bearer'})


def current_session(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(get_db)):
    if credentials is None:
        raise unauthorized()
    cfg = settings()
    try:
        payload = jwt.decode(credentials.credentials, cfg.jwt_secret, algorithms=['HS256'],
                             issuer=cfg.jwt_issuer, audience='welfare-web',
                             options={'require': ['sub', 'sid', 'exp', 'iat', 'iss', 'aud']})
    except jwt.PyJWTError:
        raise unauthorized() from None
    session = db.get(LoginSession, payload['sid'])
    if not session or session.revoked or session.expires_at <= now() or session.user_id != payload['sub']:
        raise unauthorized()
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise unauthorized()
    return user, session


def current_user(pair=Depends(current_session)):
    return pair[0]


def admin_user(user=Depends(current_user)):
    if user.role != 'admin':
        raise HTTPException(403, 'Administrator access required')
    return user

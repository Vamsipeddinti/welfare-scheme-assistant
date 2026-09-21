from pathlib import Path
import json
import secrets
import sys
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import engine
from app.models import User, Profile
from app.security import hash_password

from app.config import settings
if not settings().demo_mode:
    raise RuntimeError('DEMO_MODE=true required for browser demo administrator setup')
target = root / 'runtime/browser-admin.json'
target.parent.mkdir(parents=True, exist_ok=True)
if not target.exists():
    password = secrets.token_urlsafe(24)
    with Session(engine()) as db:
        if db.scalar(select(User).where(User.username == 'demo_admin')):
            raise RuntimeError('Existing administrator preserved; supply credentials manually')
        user = User(username='demo_admin', email='admin@example.test', password_hash=hash_password(password), role='admin')
        db.add(user)
        db.flush()
        db.add(Profile(user_id=user.id, data={}))
        db.commit()
    target.write_text(json.dumps({'username': 'demo_admin', 'password': password}), encoding='utf-8')
print('Private browser test administrator configured.')

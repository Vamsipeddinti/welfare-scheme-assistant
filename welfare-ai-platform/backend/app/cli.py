"""Run from backend: python -m app.cli seed|index|create-admin."""
import argparse
import getpass
import json
import secrets
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import ROOT, settings
from .db import engine
from .domain import validate_profile
from .models import Profile, Scheme, User
from .security import hash_password


def seed(demo=False):
    from .main import validate_scheme
    with Session(engine()) as db:
        for data in json.loads((ROOT / 'data/schemes.json').read_text(encoding='utf-8')):
            validate_scheme(data)
            if db.get(Scheme, data['id']) is None:
                db.add(Scheme(id=data['id'], data=data, active=data['active'], version=data['version']))
        credentials = []
        if demo:
            if not settings().demo_mode:
                raise RuntimeError('DEMO_MODE=true is required to seed synthetic accounts')
            for citizen in json.loads((ROOT / 'data/citizens.json').read_text(encoding='utf-8')):
                if db.scalar(select(User).where(User.username == citizen['username'])):
                    continue
                password = secrets.token_urlsafe(18)
                user = User(username=citizen['username'], email=citizen['email'], password_hash=hash_password(password))
                db.add(user)
                db.flush()
                data = validate_profile(citizen['profile'])
                revision = data.pop('revision', 1)
                db.add(Profile(user_id=user.id, data=data, revision=revision))
                credentials.append({'username': user.username, 'password': password, 'scenario': citizen['scenario']})
        db.commit()
    if credentials:
        path = ROOT / 'runtime/demo-credentials.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = json.loads(path.read_text()) if path.exists() else []
        path.write_text(json.dumps(previous + credentials, indent=2), encoding='utf-8')
        print('Synthetic account credentials saved privately to runtime/demo-credentials.json')
    print('Seed complete (existing scheme edits and accounts preserved).')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['seed', 'index', 'create-admin'])
    parser.add_argument('--demo', action='store_true')
    args = parser.parse_args()
    if args.command == 'seed':
        seed(args.demo)
    elif args.command == 'index':
        from .main import active_schemes, knowledge
        with Session(engine()) as db:
            print(knowledge().index(active_schemes(db)))
    elif args.command == 'create-admin':
        from .main import RegisterRequest
        request = RegisterRequest(username=input('Admin username: ').strip(), email=input('Admin email: ').strip(),
                                  password=getpass.getpass('Admin password (10+ characters): '))
        with Session(engine()) as db:
            if db.scalar(select(User).where(User.username == request.username.lower())):
                raise RuntimeError('An account with this username already exists; no privilege changes made')
            user = User(username=request.username.lower(), email=str(request.email).lower(),
                        password_hash=hash_password(request.password), role='admin')
            db.add(user)
            db.flush()
            db.add(Profile(user_id=user.id, data={}))
            db.commit()
        print('Administrator created.')


if __name__ == '__main__':
    main()

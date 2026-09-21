"""Generate workspace-local secrets; never overwrite an existing environment."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
target = root / '.env'
if target.exists():
    print('.env already exists; preserved.')
else:
    password = secrets.token_hex(24)
    content = (root / '.env.example').read_text().replace('GENERATE_DATABASE_PASSWORD', password)
    content = content.replace('GENERATE_JWT_SECRET', secrets.token_hex(48))
    target.write_text(content, encoding='utf-8')
    print('Created .env with local secrets. Do not commit this file.')

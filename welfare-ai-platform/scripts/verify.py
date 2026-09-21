"""Run repeatable local checks and keep timestamped evidence. Run with the project venv."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/test-results'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pnpm', default=shutil.which('pnpm'))
    parser.add_argument('--real-rag', action='store_true')
    parser.add_argument('--browser', action='store_true', help='Requires running backend/frontend and demo administrator')
    args = parser.parse_args()
    if not args.pnpm:
        parser.error('Install pnpm or provide --pnpm path/to/pnpm.mjs')
    pnpm = ['node', args.pnpm] if args.pnpm.endswith('.mjs') else [args.pnpm]
    env = os.environ.copy()
    if args.real_rag:
        env.update(RUN_RAG_INTEGRATION='1', MODEL_CACHE_DIR=str(ROOT / 'runtime/model'),
                   RAG_EVALUATION_OUTPUT=str(OUT / 'rag-evaluation.json'))
    env.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(ROOT / 'runtime/browsers'))
    checks = [
        ('backend-tests', 'backend', [sys.executable, '-m', 'pytest', 'tests', '-q', '-p', 'no:cacheprovider',
         f'--basetemp=../runtime/pytest-{uuid.uuid4().hex[:12]}', '--junitxml=../artifacts/test-results/backend.xml', '--tb=short']),
        ('backend-lint', 'backend', [sys.executable, '-m', 'ruff', 'check', 'app', 'tests']),
        ('dependencies', '.', [sys.executable, '-m', 'pip', 'check']),
        ('frontend-tests', 'frontend', [*pnpm, 'test', '--reporter=default', '--reporter=junit', '--outputFile=../artifacts/test-results/frontend.xml']),
        ('frontend-lint', 'frontend', [*pnpm, 'lint']),
        ('frontend-build', 'frontend', [*pnpm, 'build']),
    ]
    if args.browser:
        checks.append(('browser', 'frontend', [*pnpm, 'test:e2e']))
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for name, cwd, command in checks:
        start = datetime.now(timezone.utc)
        result = subprocess.run(command, cwd=ROOT / cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding='utf-8', errors='replace')
        text = result.stdout.replace(str(ROOT), '<PROJECT_ROOT>')
        (OUT / f'{name}.log').write_text(text, encoding='utf-8')
        record = dict(check=name, cwd=cwd, command=[x.replace(str(ROOT), '<PROJECT_ROOT>') for x in command],
                      started_at=start.isoformat(), finished_at=datetime.now(timezone.utc).isoformat(), exit_code=result.returncode)
        records.append(record)
        (OUT / 'verification.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
        print(f'{name}: exit {result.returncode}', flush=True)
        if result.returncode:
            print(text[-7000:], flush=True)
    return 1 if any(r['exit_code'] for r in records) else 0


if __name__ == '__main__':
    sys.exit(main())

"""Container startup: initialize owned volume directories, drop privileges, migrate, serve."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    port = int(os.environ.get('PORT', '8000'))
    if not 1 <= port <= 65535:
        raise ValueError('PORT must be between 1 and 65535')
    for path in (Path('/app/runtime'), Path('/app/runtime/uploads'), Path('/app/runtime/chroma')):
        if path.is_symlink():
            raise RuntimeError('Runtime directories must not be symlinks')
        path.mkdir(parents=True, exist_ok=True)
        if os.getuid() == 0:
            os.chown(path, 10001, 10001)
    if os.getuid() == 0:
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)
    os.chdir('/app/backend')
    for args in (['-m', 'alembic', 'upgrade', 'head'], ['-m', 'app.cli', 'seed'], ['-m', 'app.cli', 'index']):
        subprocess.run([sys.executable, *args], check=True)
    os.execv(sys.executable, [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0',
                            '--port', str(port), '--workers', '1', '--no-proxy-headers'])


if __name__ == '__main__':
    main()

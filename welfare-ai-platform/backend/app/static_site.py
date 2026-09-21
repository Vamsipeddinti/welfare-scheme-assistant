"""Serve an optional built React application while preserving API 404 responses."""
from pathlib import Path
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles


class ReactApplication(StaticFiles):
    def __init__(self, directory):
        if not (Path(directory) / 'index.html').is_file():
            raise RuntimeError('STATIC_DIR must contain the built frontend index.html')
        super().__init__(directory=directory, html=True)

    async def get_response(self, path, scope):
        route_path = path.replace('\\', '/')
        if route_path == 'api' or route_path.startswith('api/'):
            raise HTTPException(404)
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or '.' in Path(path).name or route_path.startswith('assets/'):
                raise
            response = await super().get_response('index.html', scope)
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

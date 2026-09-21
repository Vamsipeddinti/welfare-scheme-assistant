"""Enforce real received-byte limits before Starlette's multipart parser spools files."""
from fastapi.responses import JSONResponse


class BodyLimitMiddleware:
    def __init__(self, app, upload_limit):
        self.app = app
        self.upload_limit = upload_limit

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in {'POST', 'PUT', 'PATCH'}:
            return await self.app(scope, receive, send)
        maximum = self.upload_limit + 65536 if scope['path'].endswith('/documents') else 100000
        headers = dict(scope.get('headers', []))
        declared = headers.get(b'content-length')
        if declared and (not declared.isdigit() or int(declared) > maximum):
            return await JSONResponse({'detail': 'Request too large'}, 413)(scope, receive, send)
        body = bytearray()
        while True:
            event = await receive()
            if event['type'] == 'http.disconnect':
                return
            piece = event.get('body', b'')
            if len(body) + len(piece) > maximum:
                return await JSONResponse({'detail': 'Request too large'}, 413)(scope, receive, send)
            body.extend(piece)
            if not event.get('more_body', False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()

        await self.app(scope, bounded_receive, send)

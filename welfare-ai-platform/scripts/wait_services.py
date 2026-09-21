"""Wait at most one minute for local services; exits nonzero on failure."""
import time
import urllib.request

deadline = time.monotonic() + 60
for url in ('http://127.0.0.1:8000/api/health', 'http://127.0.0.1:5173'):
    while True:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                assert response.status == 200
            break
        except Exception:
            if time.monotonic() >= deadline:
                raise RuntimeError('Service did not start: ' + url) from None
            time.sleep(1)
print('Backend and frontend responded successfully.')

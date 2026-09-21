import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.config import Settings
from app.static_site import ReactApplication


def test_cloud_postgres_urls_keep_explicit_psycopg_driver():
    for prefix in ('postgres://', 'postgresql://', 'postgresql+psycopg://'):
        cfg = Settings(_env_file=None, database_url=prefix + 'user:password@host/db', jwt_secret='a' * 48)
        assert cfg.database_url == 'postgresql+psycopg://user:password@host/db'
    with pytest.raises(ValueError):
        Settings(_env_file=None, database_url='sqlite:///test', jwt_secret='a' * 48)


def test_spa_deep_links_assets_and_api_boundaries(tmp_path):
    (tmp_path / 'index.html').write_text('<html>Synthetic application shell</html>')
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'assets/app.js').write_text('console.log("synthetic")')
    app = FastAPI()
    app.mount('/', ReactApplication(tmp_path))
    with TestClient(app) as client:
        assert client.get('/profile').status_code == 200
        assert 'application shell' in client.get('/schemes/demo-family-support').text
        assert client.get('/assets/app.js').status_code == 200
        assert client.get('/assets/missing.js').status_code == 404
        assert client.get('/api/v1/not-an-endpoint').status_code == 404
        assert client.get('/.env').status_code == 404
        assert "frame-ancestors 'none'" in client.get('/').headers['content-security-policy']

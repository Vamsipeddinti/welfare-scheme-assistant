# Sahaay — Welfare Scheme Assistant

A locally runnable academic prototype for exploring welfare rules, preparing documents and understanding source material. It contains **12 explicitly fictional schemes and five synthetic citizen scenarios**. It does not establish official entitlement, authenticate documents or submit government applications.

The frontend uses React 18, Vite, Tailwind and React Router. The backend uses FastAPI, SQLAlchemy, Alembic and PostgreSQL. Local chat uses the real `sentence-transformers/all-MiniLM-L6-v2` embedding model and persistent Chroma. Local mode needs no LLM API key after the model has been downloaded.

Verification status is recorded in [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md), [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) and [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md). Windows native execution was exercised. Docker was unavailable in the build environment, so a fresh Compose startup is **BLOCKED**, not verified. macOS/Linux execution and a paid live-provider call were not observed.

## Start with Docker Compose

Run all commands in the `welfare-ai-platform` project root. Prerequisites: Docker Desktop with Linux containers/WSL2 on Windows, or Docker Engine and Compose v2 on Linux; Python 3.12 for the small secret-generation script. Initial dependency and model downloads require internet access and several GB of free disk space. CPU inference is supported.

```sh
python scripts/setup_env.py
docker compose build
docker compose run --rm backend python /app/scripts/setup_model.py
docker compose up -d
docker compose exec backend python -m app.cli index
docker compose ps
```

`setup_env.py` generates random local secrets and preserves an existing `.env`. Never commit that file. On systems whose Python executable is named `python3`, substitute it for `python`. Compose runs PostgreSQL health checks, Alembic migrations and an idempotent scheme seed before the API starts. Model setup populates the persistent model volume; it is a distinct first-time step and cannot be skipped for local chat.

Open:

- Application: [http://localhost:3000](http://localhost:3000)
- API health: [http://localhost:8000/api/health](http://localhost:8000/api/health)
- OpenAPI documentation: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)

Register a citizen account in the UI. To create an administrator, use the protected local command, which prompts for the password without printing it:

```sh
docker compose exec backend python -m app.cli create-admin
```

Public registration cannot create administrators. The backend uses one worker because the local rate limiter and embedding/index lock are process-local.

## Native development

Use Python **3.12.14**, Node **22.12 or later** and pnpm **11.19.0**. The recorded Windows build used Python 3.12.14. PostgreSQL must be available; SQLite is not supported as a substitute. The container definition specifies PostgreSQL 17.11. Native verification used a separate locally provisioned PostgreSQL service; see the evidence document for the observed version and port.

Create a PostgreSQL role and application database using your normal administrator account. For a fresh local installation, `createuser --pwprompt welfare` and `createdb --owner=welfare welfare` are suitable interactive commands. The selected password must match the credentials in the application's `.env`. Do not put a real password in command history or share it in logs.

PowerShell, from the project root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe scripts/setup_env.py
```

POSIX shell, from the project root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python scripts/setup_env.py
```

Edit `.env` locally so `DATABASE_URL` points to your PostgreSQL database with the `postgresql+psycopg://` driver. The template uses port 5432; the recorded development session used 55432. Keep the generated `JWT_SECRET`. The application does not create the PostgreSQL role/database automatically.

PowerShell backend setup/start:

```powershell
.\.venv\Scripts\python.exe scripts/setup_model.py
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.cli seed
..\.venv\Scripts\python.exe -m app.cli index
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

POSIX backend setup/start:

```sh
.venv/bin/python scripts/setup_model.py
cd backend
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m app.cli seed
../.venv/bin/python -m app.cli index
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

In a second terminal, from the project root:

```sh
cd frontend
corepack enable
corepack prepare pnpm@11.19.0 --activate
pnpm install --frozen-lockfile
pnpm build
pnpm preview
```

For live development reloads, use `pnpm dev`. This sandbox blocked Vite dependency optimization from reading a home-directory ancestor; the production build/preview path above was verified.

Open [http://localhost:5173](http://localhost:5173). Vite forwards `/api` to `127.0.0.1:8000`; the browser does not receive backend secrets. `API_PROXY_TARGET` can change the development target. Compose uses Nginx on port 3000 and the internal backend hostname instead.

## Demo accounts and documents

New registrations are the simplest way to demonstrate the full journey. All profile information and uploads must be synthetic. [docs/DEMO_WALKTHROUGH.md](docs/DEMO_WALKTHROUGH.md) gives exact values and steps.

To seed the five prepared citizens, set `DEMO_MODE=true` in `.env`, then run `python -m app.cli seed --demo` from `backend` with the activated project environment. For Compose, recreate the backend after changing its environment, then run `docker compose exec backend python -m app.cli seed --demo`. The command creates random account passwords and stores them in `runtime/demo-credentials.json`; it does not print them. In a container that file is `/app/runtime/demo-credentials.json`. Treat it as private local setup material. Repeated seeding preserves existing accounts, passwords and scheme edits.

The scheme seed runs without demo-account mode. Demo seeding supplies profiles; upload the provided PDFs through the UI to demonstrate extraction. Files in `data/synthetic_documents/` include Asha's matching identity/income/residence documents, Meera's intentional income mismatch, and honest OCR/error cases. Regenerate them using `python scripts/generate_documents.py` from the project root.

## Tests and builds

Backend commands below run from `backend`, with the project virtual environment activated. Pure tests are available without PostgreSQL; integration tests require an explicitly disposable database whose name ends in `_test` and differs from the application database.

```sh
python -m pytest tests/test_domain.py tests/test_documents.py tests/test_rag.py -q
python -m ruff check app tests
python -m pip check
```

The real retrieval test is skipped unless explicitly enabled. Prepare a separate PostgreSQL database, for example `welfare_test`, and configure `TEST_DATABASE_URL` plus `APPLICATION_DATABASE_URL` locally. The integration fixture rejects the application database before clearing test tables. It applies Alembic migrations, then cleans **only the guarded test database**. Uploads and the real retrieval index use pytest temporary directories.

PowerShell full backend suite, from `backend` (connection variables are already configured locally):

```powershell
$env:RUN_RAG_INTEGRATION='1'
$env:MODEL_CACHE_DIR=(Resolve-Path ../runtime/model).Path
$env:RAG_EVALUATION_OUTPUT='../artifacts/test-results/rag-evaluation.json'
python -m pytest -q --junitxml=../artifacts/test-results/backend.xml
```

POSIX equivalent, from `backend`:

```sh
RUN_RAG_INTEGRATION=1 MODEL_CACHE_DIR="$(cd ../runtime/model && pwd)" \
RAG_EVALUATION_OUTPUT=../artifacts/test-results/rag-evaluation.json \
python -m pytest -q --junitxml=../artifacts/test-results/backend.xml
```

Frontend commands run from `frontend`:

```sh
pnpm test
pnpm lint
pnpm build
pnpm exec playwright install chromium
pnpm test:e2e
```

Browser journeys require the actual backend, PostgreSQL, seeded schemes, model cache and UI to be running. The admin journey reads private setup credentials from `runtime/browser-admin.json`; with `DEMO_MODE=true`, run `python scripts/setup_browser_admin.py` from the project root using the project virtual environment. It creates a synthetic admin with a random password and writes that local credential file without printing secrets. Never commit that file. Set `E2E_BASE_URL` for a nondefault UI URL. The browser test creates synthetic accounts and a test scheme in the running installation, so use a disposable demo installation. Its simulated network-outage case is explicitly a frontend recovery test, not an actual outage measurement.

The combined runner is `python scripts/verify.py --real-rag --browser` from the project root with the virtual environment activated. It records commands, timestamps, exit codes and sanitized outputs. Set `PLAYWRIGHT_BROWSERS_PATH` to the same cache during both browser installation and execution; the runner defaults to `runtime/browsers`.

Review exact observations and any skipped/blocked checks in `docs/TEST_RESULTS.md`. A mocked provider adapter test is not a successful live-provider call.

## Model cache and live mode

The embedding revision is pinned to `bc57282bc374d33e0d6c4de27f12dc1c2a87f37a`. `scripts/setup_model.py` downloads the model's JSON, tokenizer, pooling and safetensors artifacts into `runtime/model` or the configured `MODEL_DIR`. Runtime loading uses `local_files_only=True` and `trust_remote_code=False`; missing artifacts produce a setup error, not fake vectors. Persistent Chroma files live in `runtime/chroma` or `CHROMA_DIR`. After installing dependencies and caching the model, normal local operation requires no runtime internet connection.

Optional live mode uses the OpenAI Responses adapter. Set `LLM_MODE=live`, `LLM_API_KEY` and `LLM_MODEL` on the server and restart it. No provider key is shipped. The adapter transmits only public retrieved passages and a locally selected question topic; it does not transmit the user's original message, profile, upload or chat history. Provider results must quote actual retrieved text using valid chunk IDs. Timeouts and provider failures are displayed as recoverable live errors. They are not reported as a successful local fallback. Actual live calls were **NOT RUN** without credentials.

## Persistence, reset and troubleshooting

`docker compose down` stops containers while retaining database, upload, vector and model volumes. Native services retain data in PostgreSQL and the configured runtime directories. Logout revokes the server session and clears the browser's refresh token. Clearing browser storage alone does not erase server data.

For a fresh non-destructive demo, use a distinct Compose project name and its separate named volumes (`docker compose -p welfare-fresh ...`) or create a new native PostgreSQL database and separate `UPLOAD_DIR`/`CHROMA_DIR`. Do not repoint a test run at your application database. Only when deliberately discarding that disposable Compose installation, `docker compose -p welfare-fresh down --volumes` removes **all four volumes for that project**, including documents and cached model artifacts.

| Symptom | Action |
| --- | --- |
| PostgreSQL connection refused | Start PostgreSQL; check host/port/role/database in `DATABASE_URL`. Containers use `postgres`, native commands use your local hostname. |
| JWT/configuration validation failure | Run `scripts/setup_env.py` for a missing environment file; preserve existing secrets and correct locally invalid values. |
| Chat says knowledge service unavailable | Run model setup once online, then `app.cli index`; check configured cache/index directory permissions. |
| Empty recommendations | Supply DOB, family income and bank-account status; UNKNOWN is an unanswered value. Review the full catalog and explicit ineligible filter. |
| Image or scanned PDF needs OCR | OCR is intentionally disabled. Use the text-based synthetic fixtures; do not mark an unreadable image as verified. |
| Unsupported manual correction | Only fields for the recognized document type can be corrected. Unrecognized or OCR-only files remain unresolved. |
| Browser cannot reach API | Check API health, proxy target and exact CORS origin. Start frontend and backend in separate terminals. |
| HTTP 429 | The local rate limiter has been reached. Wait for its window; do not bypass it using multiple backend workers. |
| Scheme disappears after editing | Edits create an unpublished revision; validate and publish it in Administration. |

## Project map

```text
welfare-ai-platform/
├── backend/
│   ├── app/                 # API, sessions, domain, documents, retrieval, CLI
│   ├── alembic/             # Authoritative migrations
│   ├── tests/               # Domain, PostgreSQL, extraction, retrieval tests
│   ├── requirements.lock    # Resolved Python versions
│   └── Dockerfile
├── frontend/
│   ├── src/                 # Connected citizen/admin React screens
│   ├── e2e/                 # Playwright journeys
│   ├── pnpm-lock.yaml
│   ├── nginx.conf
│   └── Dockerfile
├── data/                    # Fictional schemes, citizens, evaluation, PDFs
├── scripts/                 # Secret, model and synthetic fixture preparation
├── docs/                    # Contracts, architecture, evidence, report
├── artifacts/test-results/  # Sanitized reports and UI screenshots
├── docker-compose.yml
└── .env.example
```

Read [ARCHITECTURE.md](docs/ARCHITECTURE.md), [DOMAIN.md](docs/DOMAIN.md), [DECISIONS.md](docs/DECISIONS.md) and [ACADEMIC_REPORT.md](docs/ACADEMIC_REPORT.md) for implementation boundaries and evaluation methodology.

## Public website deployment

GitHub/Railway deployment configuration is prepared but no public deployment was performed. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the account connections, fresh database, persistent storage and live verification needed to obtain the final HTTPS website link. Localhost is a local preview only.

# Observed test results

Delivery evidence updated 2026-09-21T04:15:34.801722+00:00. Native Windows only. Latest full backend: **151 passed, 0 failures, 0 errors**. Frontend: **5 passed**. Browser: **5 passed**. These are observed tests of an academic prototype, not a guarantee of zero defects.

| Check | Result | Evidence |
| --- | --- | --- |
| Complete backend, actual PostgreSQL + embeddings/Chroma | PASS: 151 tests | backend.xml, backend-tests.log, backend-final.json |
| React component/contracts | PASS: 5 tests | frontend.xml, frontend-tests.log |
| Chromium real-service journeys | PASS: 5; pageerror assertions clean | browser.json, browser.log, screenshots |
| Backend Ruff / frontend ESLint | PASS | backend-lint.log, frontend-lint.log |
| Frontend production build | PASS | frontend-build.log |
| Python dependency consistency | PASS | dependencies.log |
| Frontend dependency audit | PASS: zero reported advisories | frontend-audit.json |
| Backend audit | REVIEWED: 5 entries, 4 unique Chroma server CVEs | backend-audit.json; KNOWN_LIMITATIONS.md |
| Real local RAG | 24/24 expected status; 16/16 answerable cases have supported citations | rag-evaluation.json |
| Alembic / repeated seed | PASS: real empty test DB migration, repeated safe seed in API suite; native app migration observed | test_api.py; initial schema migration |
| API restart persistence | PASS: stored session/profile, uploaded file digest, history, real retrieval | persistence.json |
| Config/static hosting routes | PASS: standard PostgreSQL URLs, SPA deep links, API/asset404, CSP | hosting.xml, complete backend suite |
| Docker Compose and combined cloud image | BLOCKED / NOT RUN: Docker absent, WSL not installed | deployment configuration only |
| Public deployment / remote GitHub CI | NOT RUN: accounts not connected; no verified public URL | DEPLOYMENT.md |
| Live provider / macOS / Linux | NOT RUN | No provider credential; those platforms not exercised |

Evidence paths are relative to `artifacts/test-results/`. Current tested versions: Python3.12.14, PostgreSQL17.11, Node24.19.0, pnpm11.19.0, React18.3.1, Router7.18.4, Vitest4.1.11, Chromium153. Runtime/dependency versions are pinned in the lockfiles and image definitions.

## Exact commands and chronology

`verification.json` records UTC start/end timestamps, working directories, full commands and exit codes for the combined runner:

```powershell
.\.venv\Scripts\python.exe scripts/verify.py --real-rag --browser --pnpm <path-to-pnpm.mjs>
```

The repeated backend run first hit Windows access-denied while pytest tried to clean an old session's temp directory. That error is retained in verification.json. The runner was fixed to allocate a new uniquely named temporary directory each run. `backend-final.json` records the subsequent successful full rerun, which supersedes the earlier backend row. Its exact pytest options were:

```text
python -m pytest tests -q -p no:cacheprovider --basetemp=../runtime/pytest-<unique-id> --junitxml=../artifacts/test-results/backend.xml --tb=short
```

The run set RUN_RAG_INTEGRATION=1, MODEL_CACHE_DIR to the project's runtime/model, and RAG_EVALUATION_OUTPUT to the retained JSON. The PostgreSQL test fixture reads the private TEST_DATABASE_URL and a distinct application URL. Database names must differ, even when hostname/port aliases differ. Secrets are not recorded.

Audits: `python -m pip_audit -r backend/requirements.lock --no-deps --disable-pip --cache-dir runtime/audit-cache --format json --output artifacts/test-results/backend-audit.json` exited1 for the retained Chroma findings; `pnpm audit --json` exited0 after Router/Vitest updates. The backend audit tool was installed separately for verification; it is not needed to run the app.

The initial PDF/browser failures (ambiguous selectors, source citation selection, and unrelated tax questions routed to personal eligibility) were investigated and fixed. The final five journeys exercise registration/incomplete-profile correction/recommendations; actual PDF mismatch/correction/readiness/export/deletion; real cited chat/unsupported/personal questions; simulated503 recovery and390px width; actual admin edit/republish/archive. Test-only503 is a browser routing stub; all normal API calls use the real backend. A known upstream Starlette/AnyIO deprecation warning remains.

The restart probe passed after a backend restart. The attempted pg_ctl graceful database stop reported operation-not-permitted; the subsequent portable PostgreSQL process recovered, then later stopped because its pid file was absent. It was started cleanly on September21 with an intact pid file before the latest real integration/browser suites. Do not treat the earlier probe as a certified graceful database/Compose restart. Chroma close/reopen persistence is separately covered by the real integration test.

RAG metrics cover the supplied narrow fictional fixture set. They are not population accuracy, official eligibility accuracy, a user study, or live-provider success. The live quote-selection adapter is tested using mocks only. Docker/container resource limits, Linux dependency resolution and an independent fresh installation remain unverified.

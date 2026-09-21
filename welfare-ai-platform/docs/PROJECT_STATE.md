# Project state

Updated 2026-09-21T04:15:34.801722+00:00. Native implementation and deliverable files are complete. Overall progress estimate: about90%, with public deployment and portable/fresh setup verification still outstanding. This estimate is not a test coverage metric.

## Completed and verified

Phases1–12 have native passing gates: PostgreSQL/Alembic; identity/sessions; profiles; twelve fictional schemes/five scenarios; typed rule engine; ranking; actual persistent local retrieval; chat; private PDF extraction/corrections; readiness/export; responsive administration. Latest complete backend151pass, frontend5pass, browser5pass; build/lint/pip-check pass. RAG24/24expectedstatus,16/16supportedcitedanswers. See TEST_RESULTS.md and machine evidence for exact scope/timestamps.

Phase13 remains BLOCKED as a whole because Docker/WSL are unavailable and the fresh Compose smoke gate cannot run. Phase14 source/docs/report/evidence/package are supplied; independent clean-install confirmation remains BLOCKED with that environment gate. No unobserved platform/provider/CI run is represented as passing.

## New user request: GitHub and public deployment

GitHub/Railway connection suggestions were offered. Neither connection was confirmed; GitHub in the available browser was signed out. No remote repository or hosting resources were created. deploy/Dockerfile, deploy/start.py, railway.toml, STATIC_DIR same-origin serving and DEPLOYMENT.md are prepared. Hosting routing/configuration tests pass; Linux container build has NOT RUN. No final public website URL exists.

The app currently has native launch processes at127.0.0.1:8000 and frontend127.0.0.1:5173, with portable PostgreSQL55432 in workspace scratch storage. These are local processes that may stop when the host/session closes. All real credentials stay in ignored .env/runtime and are excluded from delivery. Sources, locks, fixtures, setup scripts, CI and sanitized evidence are in the outputs ZIP/folder.

## Exact next action

Connect GitHub and Railway, inspect account/plan and obtain approval before new charges, then create a private repository, deploy fresh PostgreSQL plus the combined app and runtime volume, observe Linux build/startup, set exact public origin, run the actual browser journeys on the HTTPS domain, and return the verified website URL. See DEPLOYMENT.md. Do not substitute GitHub Pages or a frontend-only preview for the complete app.

Remaining limitations: four unique retained Chroma-server advisories (described paths are not exposed by this embedded topology); regex-based question routing/conflict detection; OCR unsupported; synthetic rules only; one-worker local limiter; optional live-provider call absent. Read KNOWN_LIMITATIONS.md.

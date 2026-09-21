# Requirements and acceptance evidence

Status snapshot: the native Windows implementation has passed **151 backend tests, 5 frontend tests and 5 browser journeys**, together with backend/frontend lint, Python dependency consistency and the frontend production build. Actual local retrieval recorded **24/24 expected query outcomes** and **16/16 answerable queries with resolving citations and verbatim support**. `artifacts/test-results/verification.json` records executed commands, timestamps and exit codes; later recorded regression runs supersede these counts.

**The complete specification is not fully verified.** Docker is unavailable and WSL is not installed, so the required fresh Compose startup remains BLOCKED. Phase 14 is IN PROGRESS while packaging, final evidence and fresh-setup verification are completed. Live-provider execution is an explicitly allowed NOT RUN without credentials. A successful native test is not a container or cross-platform test.

Status vocabulary: **NOT STARTED**, **IN PROGRESS**, **PASS**, **FAIL**, **BLOCKED**, **NOT RUN**. A PASS below applies to the stated scope and evidence, not to unobserved deployment environments.

## Fourteen phases

| Phase | Implementation and scope | Acceptance evidence | Status |
| --- | --- | --- | --- |
| 1. Environment, architecture, skeleton, configuration, locks, Compose definition | `backend/app/config.py`; backend/frontend source; requirements lock; pnpm lock; Dockerfiles; `docker-compose.yml` | Native imports/configuration, PostgreSQL use, production build and dependency check; architecture documented | **PASS — native**. Compose execution remains Phase 13 BLOCKED. |
| 2. Schema, migrations, disposable database and seeds | `backend/alembic/`; `app/models.py`; `app/cli.py`; guarded API test fixture | Real PostgreSQL migrations and repeat/idempotent seed checks in `test_api.py`; no `create_all`/SQLite fallback | **PASS — native PostgreSQL** |
| 3. Authentication, sessions and roles | `app/security.py`, auth routes; `frontend/src/App.jsx`, `api.js` | `test_sessions_refresh_replay_logout_and_forgery`; registration/login browser journey | **PASS** |
| 4. Profiles | `app/domain.py`, profile routes; `frontend/src/Citizen.jsx` | Profile normalization, partial/null/false/zero/invalid values in `test_domain.py`, API profile tests; missing-profile correction browser journey | **PASS** |
| 5. Catalog and provenance | `data/schemes.json`, `data/citizens.json`; catalog/seed routes; `Schemes.jsx` | Twelve valid fictional records, five labeled scenarios, pagination/category filters, source labels and repeated seed tests | **PASS — 0 real / 12 fictional** |
| 6. Typed rules and eligibility | `app/domain.py`; evaluation routes and trace UI | All operators/boundaries, nested truth tables, unknown paths, leap dates, malformed rules and coverage tests | **PASS** |
| 7. Recommendations | `app/domain.py` score/order; recommendations API/UI | Status ordering, stable ties, bounded scores and satisfied-OR support tests; explained recommendation browser journey | **PASS** |
| 8. Embeddings and persistent retrieval | `app/rag.py`; `scripts/setup_model.py`; CLI index | Actual pinned CPU model/Chroma evaluation, reopen persistence, duplicate avoidance, revision replacement and archive removal | **PASS — real local retrieval** |
| 9. Local/live chat and private histories | Chat routes, `app/rag.py`, `frontend/src/Chat.jsx` | Local cited chat/unsupported/personal browser journey; private-session API checks; provider mocks and error tests; 24-query evaluation | **PASS — local and adapter logic**. Actual live call **NOT RUN**. |
| 10. Private documents and consistency | `app/documents.py`; upload/download/correction/delete routes; `Documents.jsx`; synthetic PDFs | Real PDF evidence, mismatch/corrections, filename spoofing/limits, corrupt/encrypted/image/scanned outcomes, ownership and browser flow | **PASS** |
| 11. Readiness and export | `app/domain.py`; readiness/HTML export routes; `Schemes.jsx` | Formula/alternatives/conditions/ineligible/correction/deletion unit cases; authenticated export and browser download | **PASS** |
| 12. Admin and complete interface | Admin routes and `Admin.jsx`; responsive connected screens | Role enforcement, real aggregate metrics, publication/archive browser journey; mobile width and retained-input recovery; 5 frontend tests | **PASS — tested journeys** |
| 13. Integration/security/clean startup | Full native suites, audits, scripts and Compose definition | 151 backend + 5 frontend + 5 browser; lint/build/pip check pass. Chroma findings reviewed below. Fresh isolated Compose run cannot execute without Docker. | **BLOCKED — full phase** |
| 14. Documentation, report, delivery audit | README; architecture/domain/decisions/report/demo/requirements/limitations; evidence and CI | Documents and traceability present; final packaging/state/evidence and independent fresh setup remain in progress. Remote CI was not observed. | **IN PROGRESS** |

## Functional traceability

Test names are in the files shown. Machine-readable results are under `artifacts/test-results/`; `docs/TEST_RESULTS.md` is the final execution ledger.

| ID | Required feature | Implementation | Acceptance coverage | Status |
| --- | --- | --- | --- | --- |
| A1 | Register/login/refresh/logout/me; public citizen role | `security.py`; `main.py` auth routes; `App.jsx` | API sessions test; registration browser journey | **PASS** |
| A2 | Short access tokens, revocation, refresh replay, forged/expired rejection | Session/refresh models; `security.py` | `test_sessions_refresh_replay_logout_and_forgery` | **PASS** |
| A3 | Backend owner/role isolation for private resources | `owned`, current-user dependencies, admin dependency | API document/download/chat isolation, admin denial, authenticated profile/readiness/export | **PASS** |
| A4 | Fifteen-field profile dictionary, incomplete fields, normalization/completeness | `domain.py`; `DOMAIN.md`; `Citizen.jsx` | Profile validation and false/null/zero unit cases; API partial edits | **PASS** |
| A5 | Restricted CORS, request/expensive endpoint limits and generic errors | `main.py`; `body_limit.py`; Nginx config | API oversized/invalid/auth errors and browser recovery; one-worker boundary documented | **PASS — local topology** |
| B1 | Search/pagination/state/category catalog and detail | Catalog routes; `Schemes.jsx` | API catalog checks and real browser discovery | **PASS** |
| B2 | Source passage, title, local reference, fictional label, rule revision | `data/schemes.json`; scheme validator; catalog/citation UI | Fixture/schema unit tests and cited browser answer | **PASS — fictional corpus** |
| B3 | Admin create/edit/validate/publish/archive and invalidation | Admin routes; `Admin.jsx`; index synchronization | Admin API/browser tests; real RAG revision/archive test | **PASS** |
| B4 | Five independently expected citizen scenarios | `data/citizens.json`; synthetic PDFs | Fixed-date scenario tests and mismatch correction cases | **PASS** |
| C1 | Whitelisted typed rules, all/any and required operators | `domain.py` | Complete two-child truth tables, nested OR, operator and malformed-tree tests | **PASS** |
| C2 | Age at explicit date, leap-day policy, coverage downgrade | `domain.py`; `DOMAIN.md` | Birthday/range/leap/coverage/validity tests | **PASS** |
| C3 | Full trace, relevant unknown fields, source/revision metadata | Eligibility service and UI | Domain trace cases, API results and browser explanation | **PASS** |
| D1 | Status-first deterministic ranking with stable ties | `domain.recommendations`; score explanation UI | Ordering/bounds/OR tests and browser recommendations | **PASS** |
| E1 | Provenance chunks, real embeddings, persisted Chroma | `rag.py`; pinned model setup | `test_real_index_persistence_revision_archive_and_evaluation` | **PASS — actual model** |
| E2 | Offline cached loading; missing model is actionable | `rag.py` local-only loading; model setup | Real cached-model test and `test_question_guards_are_not_fake_retrieval` missing-cache error | **PASS** |
| E3 | Local extractive answers and resolving support | `SchemeKnowledge.answer`; Chat citation UI | 16/16 labeled answerable cases have current chunk identities and exact quoted evidence | **PASS — fixture denominator 16** |
| E4 | Unsupported/injection/conflicting evidence handling | Query/source guards; `_conflicts` | 3 unsupported + 2 injection + 1 controlled conflict cases | **PASS — tested patterns; heuristic limits documented** |
| E5 | Personal questions call deterministic service | API dispatch before RAG | Actual browser personal-eligibility journey; service routing markers in 2 evaluation cases | **PASS** |
| E6 | Citizen-owned sessions/history | Chat owner checks and stored messages | Cross-owner API checks and browser chat/history flow | **PASS** |
| E7 | Real provider adapter, bounded retry/time/output, validated quotes | OpenAI Responses adapter | `test_mock_provider_configuration_failure_invalid_citations_and_private_data` | **PASS — adapter mocks** |
| E8 | Actual live-provider call | Environment-configured adapter | No credentialed request executed | **NOT RUN — credentials absent** |
| F1 | Private bounded PDF/JPEG/PNG upload/list/download/delete | Upload routes, generated filenames, private directory, `documents.py` | API ownership/deletion/limits; real PDF browser journey | **PASS** |
| F2 | Content classification, page evidence and correct failure statuses | Synthetic content parser, Pillow/pypdf worker | Eight document tests, negative fixtures and correction flow | **PASS — documented synthetic formats** |
| F3 | Exact normalized comparisons; UNKNOWN/mismatch; separate corrections | `consistency`; correction provenance; fresh document view | Domain/document/API correction cases; browser mismatch to readiness | **PASS** |
| G1 | Document alternatives/conditions/deduplication and readiness formula | `domain.readiness` | Zero denominator, optional items, unknown conditions, OR documents, ineligible paperwork, correction/deletion tests | **PASS** |
| G2 | Authenticated printable preparation summary | HTML export route, escaped content, browser download | Export authentication/browser download; readable/escaping regressions in API suite | **PASS** |
| H1 | Connected citizen and admin screens with recoverable UI states | React screens and shared UI/API helpers | 5 frontend tests and 5 real browser journeys; mobile screenshot/width and retained values after simulated failure | **PASS — tested flows** |
| H2 | Actual aggregate analytics with metric definitions | SQL aggregate queries; `Admin.jsx` | Admin API and browser analytics | **PASS** |

## Reproducibility and delivery gates

| Requirement | Evidence / remaining action | Status |
| --- | --- | --- |
| Locked dependencies and runtime definitions | Python requirements lock, pnpm lock, Dockerfiles; `pip check`, lint and build logs | **PASS — native resolution/build** |
| Real disposable PostgreSQL test guard | Database must end `_test` and differ from application target; rejected unsafe-target tests | **PASS** |
| Native local retrieval persistence/idempotence | Real index reopen, repeat indexing, changed source and archive tests | **PASS** |
| Native whole-service restart persistence | Root verification is being completed; record the final restart command/result in TEST_RESULTS before changing this row | **IN PROGRESS** |
| Fresh isolated Compose startup and volume persistence | Docker command unavailable; WSL absent. Definitions/scripts cannot substitute for execution. | **BLOCKED** |
| Native Windows runtime | Actual PostgreSQL/FastAPI/production frontend preview and browser runs | **PASS** |
| macOS/Linux runtime | No observed execution; CI definition is not a remote run | **NOT RUN** |
| Backend dependency audit | Five reported entries represent four unique Chroma CVEs. Reviewed retained findings and deployment constraints appear in KNOWN_LIMITATIONS. Audit is not clean. | **PASS — review recorded; findings remain** |
| Frontend dependency audit | Final audited React Router 7.18.4/Vitest 4.1.11 dependency tree reports zero findings | **PASS — recorded scan** |
| CI workflow | `.github/workflows/ci.yml` exists; no remote CI execution observed | **NOT RUN — remote execution** |
| Documentation and academic evidence | README, architecture, decisions, domain, walkthrough, report, requirements and limitations present; final ledger/packaging in progress | **IN PROGRESS** |

OCR, Neo4j, multilingual support and AI-based simplification are optional and were intentionally not implemented. Their absence does not count as a required-feature failure. Unverified required gates still prevent an end-to-end fully verified completion claim.

# Execution prompt: Welfare Scheme Assistant

Build the project described below in the current coding workspace. Act as the accountable software engineer responsible for implementation, integration, testing, and delivery. Create and run the application, not merely a plan or code samples. Work until the required acceptance criteria pass or a concrete external blocker prevents further progress.

This is the complete project specification and replaces the earlier welfare-platform prompt, including its code snippets, phase numbering, and claims of completion. Follow the environment's instruction hierarchy and applicable repository instructions.

## 1. Outcome and scope

Deliver a locally runnable, demo-ready Indian welfare scheme discovery and application-preparation platform for a final-year academic project.

A citizen must be able to register, complete a profile, discover schemes, understand deterministic eligibility results, receive ranked recommendations, ask source-grounded questions, upload synthetic documents, inspect extracted information and inconsistencies, and download an application-preparation checklist. An administrator must be able to maintain scheme content and inspect aggregate analytics.

Required scope includes every Tier 1 and Tier 2 feature in this specification. OCR, Neo4j, multilingual support, and AI-based language simplification are optional and excluded from the completion criteria. Implement optional features only after all required gates pass, and only if requested.

The application provides guidance and consistency checks. It must not claim to authenticate government documents, determine official entitlement, guarantee approval, or submit applications to government systems. Use synthetic citizens and documents exclusively for demos and tests. Describe the result as a tested academic prototype; public production deployment needs separate assessment.

## 2. Execution contract

- Inspect the workspace, existing code, instructions, available tools, runtimes, Docker, and network access before editing. Preserve existing user work. Create `welfare-ai-platform/` only if an existing project root is not already evident.
- Start with a concise implementation plan, then execute it in the same task. Do not stop after planning or after completing an arbitrary phase.
- Make reasonable, reversible implementation decisions and record them in `docs/DECISIONS.md`. Ask only when missing information materially changes scope, requires credentials, or blocks safe progress. Continue independent work while waiting.
- Use tools to create files and run commands. Do not claim installation, execution, testing, or deployment that you did not perform. If tools are unavailable, state that limitation explicitly.
- Read current official documentation when an API or dependency is uncertain. Resolve compatible, published package versions and commit reproducible dependency locks. Do not copy dependency pins or code from the earlier prompt without checking them.
- Write complete core implementations. Do not leave fake endpoints, static replacement dashboards, unconditional success responses, unimplemented methods, or TODOs in required flows.
- Use the smallest maintainable design satisfying the requirements. There is no line-count quota. Avoid unnecessary services, frameworks, and abstractions.
- Test each phase and fix failures before marking it complete. Never weaken assertions, remove required tests, or substitute mocked integrations merely to obtain a passing result.
- When a tool or service is unavailable, record the attempted command and actual error, continue work that remains possible, and label dependent checks BLOCKED or NOT RUN. Such checks do not pass by assumption.
- Keep brief progress updates focused on findings, decisions, and blockers. Save durable progress in files; do not depend on conversation memory.
- Local implementation and testing are authorized. Public deployment, paid resource provisioning, external application submissions, and deletion of unrelated user data are outside this task.

## 3. Technology and reproducibility

Preserve these architectural choices:

- React 18, Vite, Tailwind CSS, and React Router for the frontend.
- FastAPI, a pinned Python version of at least 3.11, Pydantic, SQLAlchemy, and Alembic for the backend.
- PostgreSQL as the application and integration-test database.
- Locally persisted ChromaDB and `sentence-transformers/all-MiniLM-L6-v2` embeddings.
- A small retrieval pipeline; LangChain is optional if it materially simplifies implementation.
- Text extraction from text-based PDFs using a verified compatible PDF library. Image OCR is optional.
- pytest and FastAPI TestClient for backend tests; Vitest and React Testing Library for frontend tests; Playwright for browser journeys.
- Docker Compose as the primary portable startup path, with documented native development commands.

Choose compatible supporting packages and document meaningful deviations. If a locked choice proves technically blocked, explain the evidence before replacing it. Declare runtime and development dependencies, including validators, database drivers, JWT libraries, test runners, and browser tooling actually used. Use one JWT library consistently.

Use Alembic migrations as the schema authority. Make seeding idempotent. Do not silently substitute SQLite when PostgreSQL fails, or use `create_all()` to hide missing migrations. Pure unit tests may run without a database; integration tests must exercise PostgreSQL.

Provide `.env.example`, validated configuration, generated local secrets, dependency locks, Dockerfiles, a Compose configuration, health checks, persistent database/upload/vector/model-cache volumes, and scripts for setup, migration, seeding, indexing, testing, and demo verification. Align bind addresses, ports, frontend API URLs, and container hostnames. Keep secrets out of source, browser bundles, screenshots, and logs.

Pin and record the embedding model revision. Explain the initial model download and cache preparation. After dependencies and model artifacts are installed, the local demo must work without an LLM API key or runtime internet access. Missing model artifacts must produce an actionable setup error rather than invented embeddings or silent retrieval substitution.

Support Windows through Docker Desktop/WSL2, macOS, and Linux using the same Compose path. Provide PowerShell and POSIX setup instructions where they differ. Report which operating systems were actually tested; do not claim unobserved cross-platform success.

## 4. Functional contracts

### A. Identity, privacy, and citizen profiles

Implement registration, login, token refresh, logout, authenticated user lookup, citizen/admin authorization, password hashing, and server-side session revocation. Public registration always creates a citizen. Admin creation uses a protected local setup command; demo accounts are enabled only by explicit demo configuration.

Use short-lived access tokens and a documented secure refresh/session design. Logout must invalidate the session server-side. Protect refresh rotation and replay handling, and apply appropriate cookie/CSRF controls if cookies carry credentials. Restrict CORS and rate-limit authentication and expensive endpoints. Return generic authentication failures.

Every profile, document, extraction, chat, readiness result, and export must enforce ownership on the backend. Changing an ID must never reveal another citizen's data. Admin analytics should use aggregates, not expose raw citizen documents or conversations.

Profiles include full name, date of birth, gender, annual family income in INR, bank-account status, employment status, occupation, state, district, urban/rural location, social category, disability status, education level, student status, and marital status. Allow incomplete profiles. Use nullable booleans where an unanswered field must remain unknown; zero income and `false` are valid supplied values.

Normalize supported values, reject impossible dates and negative income, and use one documented field dictionary across forms, schemas, rules, and extraction. Profile completeness is the percentage of supplied valid fields in a documented fixed list; empty strings and nulls are missing. Keep completeness separate from eligibility and readiness.

### B. Scheme catalog and source integrity

Provide searchable, paginated scheme lists with state and category filters; detail pages; and admin create, edit, validate, publish, and archive operations. Store benefits, jurisdiction, application procedure/link, validity dates, rule version, required-document groups, and source metadata.

Seed 10-12 schemes and five synthetic citizen profiles covering eligible, ineligible, incomplete, state-specific, and document-mismatch cases. Prefer real schemes supported by official government sources. Record source URL, title, publisher, retrieval date, effective date when known, and the source passage or section supporting each encoded eligibility requirement. Do not invent thresholds, dates, URLs, or a successful verification date.

If official information cannot be verified, create clearly named fictional demonstration schemes or mark real entries unverified. Label fictional data in the API and UI, cite its local fixture, and never present it as an official program. Record the real/fictional split. Incomplete or stale real-world rules cannot justify an unqualified eligible result: expose rule coverage and unresolved requirements, and downgrade the result to requiring more information when necessary.

Ship redistributable local source material or attributed summaries sufficient for the offline demo. Do not require live government websites for routine tests. Track revisions and invalidate or recompute dependent eligibility, readiness, and retrieval data when schemes change. Archived content must not remain an active recommendation or current chat source.

### C. Deterministic eligibility

Implement a validated, typed rule tree with nested `all` (AND) and `any` (OR) groups. Leaf rules support `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `not_in`, and inclusive `between`. Use a whitelist of fields and operators; never evaluate arbitrary code. Reject malformed rules and empty groups at publication.

Leaf results are PASS, FAIL, or UNKNOWN. Missing citizen data produces UNKNOWN; a malformed rule produces a validation/configuration error, not a citizen rejection. Derive age from date of birth at an explicit evaluation date, including a documented leap-day convention. Use typed numerical values and arrays rather than comma-separated or range-encoded strings. Include jurisdiction and other actual prerequisites in the rule tree.

Group semantics are mandatory:

| Group | PASS | FAIL | UNKNOWN |
| --- | --- | --- | --- |
| AND | Every child passes | Any child fails | Otherwise |
| OR | Any child passes | Every child fails | Otherwise |

Map the root to ELIGIBLE, NOT_ELIGIBLE, or POTENTIALLY_ELIGIBLE respectively, subject to the rule-coverage requirement above. An unknown unused OR alternative does not prevent a passing OR group. A scheme with no valid rule tree cannot be treated as eligible.

Return the result, complete rule trace, field values used, missing information relevant to unresolved paths, plain-language explanations, source references, evaluation date, profile revision, and rule version. Explain results as matching the encoded rules. Neither an LLM nor document extraction may override the deterministic result.

### D. Recommendations and explainability

Rank active schemes by eligibility status first, then a documented deterministic relevance score, then stable scheme ID. Eligible schemes precede potentially eligible schemes. Keep ineligible schemes out of default recommendations; expose them through an explicit filter with reasons.

Define and test the scoring formula before implementation. Scores must be bounded, stable, safe for empty inputs, and explained as ranking scores, not approval probabilities. Do not let failed branches of a satisfied OR group incorrectly lower eligibility. Show decisive requirements, missing information, source freshness, and next steps. Do not infer sensitive profile attributes from names or documents.

### E. Retrieval and chat

Implement document ingestion, provenance-preserving chunks, embeddings, persistent indexing, retrieval, source display, and citizen-owned chat sessions/history. Index scheme knowledge only; do not mix private citizen uploads into a shared index.

Support two explicit modes:

1. `local`: default, no API key. Retrieve real local chunks and compose deterministic extractive/template answers with citations. Display that this is local source-based assistance.
2. `live`: a real provider adapter with environment-configured credentials/model, timeouts, bounded retries, and input/output limits. Implement at least one provider. Check current official SDK documentation. Provider mocks may test integration logic but do not count as a verified live call.

Unknown questions or inadequate evidence must produce a useful insufficient-information response, not invented benefits or procedures. Citations must resolve to retrieved content with scheme ID, source title/URL or local reference, chunk ID, and page/section where available. Validate citation identities and check answer support using an evaluation set, not just URL presence. Detect contradictory sources and expose uncertainty.

Treat retrieved content and uploads as untrusted data. Instructions inside them must not change system behavior, expose secrets, call arbitrary tools, or override eligibility. Personal eligibility questions must call the deterministic service and distinguish its output from source-based explanatory text. Send no raw citizen documents or unnecessary profile data to an external provider.

If a configured live provider fails, return a clear recoverable error or visibly identified local fallback. Never silently present local output as a successful live response.

### F. Documents and consistency checks

Provide private upload, listing, authenticated download, deletion, processing status, classification, field extraction, and consistency results. Accept PDF, JPEG, and PNG up to a configurable default of 10 MB. Validate actual file content as well as extension, use generated storage names, prevent path traversal, and apply extraction size/time limits. Clean up partial failures.

Required extraction covers text-based PDFs and documented synthetic templates. Classify from content; filename alone cannot prove document type. Preserve extracted values, page/text evidence, method, confidence where meaningful, and user corrections separately. Do not invent numerical confidence for deterministic parsing.

When OCR is disabled, images and scanned PDFs must receive an explicit `NEEDS_OCR` or `NEEDS_MANUAL_REVIEW` outcome. Encrypted, corrupt, unsupported, empty, or failed documents must never be reported as successfully checked. Support user-confirmed manual corrections with provenance, without labelling those corrections independently verified.

Compare names, birth dates, income, state, and category where applicable. Document normalization and matching tolerances. Distinguish MATCH, MISMATCH, and UNKNOWN; missing extracted data is UNKNOWN. Do not silently overwrite profile values. Recompute affected results after profile changes, corrections, replacement, or deletion. Deletion must remove private file content and related extracted data.

### G. Readiness and application preparation

Represent required documents as groups so alternatives such as one of several identity proofs are supported. Build a per-scheme checklist containing applicable required profile fields, document groups, and unresolved consistency checks. Handle conditional and unknown requirements explicitly.

Define readiness as `100 * satisfied mandatory checklist items / applicable mandatory checklist items`, rounded consistently. Optional items do not affect the denominator. Unknown conditional requirements remain unresolved blockers. If the denominator is zero, return a documented not-applicable result rather than divide by zero. Deduplicate equivalent checklist items.

Return checklist percentage and preparation status separately. READY requires an eligible result, every mandatory item satisfied, and no unresolved mismatch or unknown requirement. An ineligible citizen can have complete paperwork but cannot receive READY. Document presence alone does not satisfy a required content check. Label any accepted manual confirmation accurately.

Offer an authenticated downloadable preparation summary with scheme/source details, eligibility explanation, readiness checklist, remaining actions, and official application link when verified. A printable HTML or PDF export is sufficient. No government submission or fabricated application number is required.

### H. Frontend and admin experience

Deliver real connected screens for registration/login, dashboard, profile editing, scheme discovery/detail, eligibility/recommendations, chat/citations, document management/results, readiness/export, and admin scheme management/analytics.

Use a consistent responsive layout, clear plain-language labels, accessible form controls, keyboard navigation, visible focus, and usable contrast. Implement loading, empty, validation, unauthorized, network-error, and retry states. Preserve entered form values on recoverable errors. Sanitize untrusted rendered content.

Admin analytics must query actual stored data and define each metric, including user counts, scheme counts, evaluation status distribution, and document-processing outcomes. Do not invent impact or approval statistics. All buttons and navigation used in the demo must work.

## 5. Fourteen implementation phases

Keep this order for prerequisites. Build the UI alongside each relevant API so integration problems surface early. Establish the frontend shell in Phase 1; Phase 12 completes and polishes it.

| Phase | Deliverable | Required gate |
| --- | --- | --- |
| 1 | Workspace audit, architecture, configuration, backend/frontend skeleton, dependency locks, Compose | Backend imports, frontend builds, configuration validates, PostgreSQL connectivity checked |
| 2 | Schema, Alembic migrations, isolated test database, seed framework | Empty PostgreSQL migrates successfully; second migration and seed runs are safe |
| 3 | Authentication, sessions, role enforcement, login/register UI | Register/login/refresh/logout pass; expired, revoked, forged, and unauthorized requests fail correctly |
| 4 | Profile API/UI and validation | Partial updates, null/false/zero distinctions, invalid input, and ownership tests pass |
| 5 | Scheme catalog, official-source provenance, demo fixtures, catalog UI | 10-12 valid scheme records; filters/pagination, source labels, and repeatable seeds pass |
| 6 | Typed rule tree and deterministic eligibility | Operator, boundary, nested AND/OR, UNKNOWN, age, malformed-rule, and coverage tests pass |
| 7 | Recommendations and explanations | Status ordering, stable ties, bounded scoring, and OR-path cases pass |
| 8 | Source ingestion, embeddings, persistent Chroma retrieval | Real fixture retrieval and provenance work; re-indexing avoids duplicates and removes stale content |
| 9 | Local/live chat adapters, private histories, citations, chat UI | Local grounded answers work; unsupported/injected questions are handled; provider failures and session isolation pass |
| 10 | Private documents, extraction, classification, consistency, UI | Text PDFs work; malformed/image/scanned cases behave honestly; upload limits and ownership pass |
| 11 | Readiness and preparation export | Formula, document alternatives, unknown blockers, ineligible profiles, corrections, and deletion pass |
| 12 | Admin management/analytics and complete responsive UI | Backend role checks pass; real metrics and all required frontend states work |
| 13 | Full integration, browser journeys, security regression, clean startup | Required test suites, browser demo, builds, and Compose smoke test pass against real services |
| 14 | Documentation, academic report, evidence, delivery audit | Another developer can follow the documented fresh setup and demo; every requirement has an honest status |

For each gate, record implementation paths, tests executed, observed results, and any blocker. Creating files does not satisfy a functional gate.

## 6. Verification and delivery evidence

Maintain `docs/REQUIREMENTS.md` mapping each required feature to its implementation, acceptance test, and status: NOT STARTED, IN PROGRESS, PASS, FAIL, BLOCKED, or NOT RUN.

Use a dedicated disposable PostgreSQL test database with a guard that rejects the application database before destructive test setup. Isolate test uploads and vector stores too. Never run blanket cleanup against user data. Design expected results from these business contracts, independently of the implementation.

Include meaningful negative and boundary cases, especially:

- Another user's profile, documents, downloads, exports, and chat sessions cannot be accessed by guessing IDs; citizen requests to admin routes fail.
- JWT expiry, revoked sessions, refresh replay, duplicate registration, invalid inputs, file spoofing, oversized uploads, and path traversal are handled without leaking secrets or stack traces.
- Exact age/income boundaries, birthdays/leap-day behavior, nested rule trees, null/false/zero values, stale rule coverage, and equivalent OR alternatives produce correct results.
- Five synthetic citizen scenarios have independently specified expected eligibility and readiness outcomes. Use a fixed evaluation date for tests.
- RAG evaluation contains at least 20 labeled queries covering answerable questions, unsupported questions, conflicting evidence, prompt injection, and personal eligibility questions. Report retrieval and citation/support results with explicit denominators. Do not claim a percentage without a recorded evaluation.
- Run at least these browser journeys against real backend/PostgreSQL/local retrieval: registration to recommendation; missing-profile correction; upload mismatch to corrected readiness/export; cited chat plus unsupported query; admin edit/archive reflected in citizen results.
- Verify restart persistence, idempotent seeds/indexing, and a fresh Compose startup using isolated test volumes. A clean installation must not depend on untracked files or the developer's existing database.

Run targeted tests per phase and the complete required suites at delivery. Include frontend production build, backend/frontend lint checks, dependency consistency checks, and browser console/network inspection. Review dependency-audit findings and fix reachable high-severity issues; document unresolved findings and blocked scans. Do not repeat passing suites without a new reason.

Save exact commands, environment versions, timestamps, exit codes, test counts, and concise outputs in `docs/TEST_RESULTS.md` with sanitized logs under `artifacts/test-results/`. Distinguish mocked provider tests, actual local retrieval, and actual live-provider calls. A live-provider call may be NOT RUN when credentials are absent; this does not block the required local mode, but must be disclosed. Other required unverified gates prevent a claim of fully verified completion.

Deliver:

- Complete source, migrations, locks, safe `.env.example`, container setup, seed/source data, and synthetic documents.
- `README.md` with prerequisites, exact working directories/commands, local startup URLs, demo-account setup, reset instructions, and troubleshooting.
- `docs/ARCHITECTURE.md` with component and data-flow diagrams, schema, API conventions, and security boundaries.
- `docs/DECISIONS.md`, `docs/REQUIREMENTS.md`, `docs/TEST_RESULTS.md`, `docs/KNOWN_LIMITATIONS.md`, and `docs/DEMO_WALKTHROUGH.md`.
- `docs/ACADEMIC_REPORT.md` covering the problem, methodology, rule semantics, retrieval design, actual evaluation results, limitations, and future work. Do not invent research novelty, user studies, or citations.
- A CI workflow for reproducible core tests and builds, without claiming a remote CI run occurred unless observed.

## 7. Continuation and final response

Update `docs/PROJECT_STATE.md` after each phase and before an unavoidable interruption. Record current phase, actual completed gates, outstanding requirements, changed files, commands/results, decisions, running services, blockers, and the exact next action. Never prefill future phases as complete. If context resumes, read that file and inspect the actual repository before continuing.

Do not reserve missing phases for an unspecified future response. Continue while tools and task limits permit. If externally blocked or interrupted, give an accurate partial status and a concrete resumption step; never substitute a roadmap for an implementation or claim success based on planned tests.

At delivery, report the completion status, actual project tree, exact startup commands and URLs, test summary with evidence paths, concise demo walkthrough, and remaining limitations. Clearly identify fictional scheme data, local/live chat status, and platforms not actually tested.

Begin now with the environment audit and Phase 1, then continue through the required phases.

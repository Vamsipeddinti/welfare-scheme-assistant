# Known limitations and unverified gates

The native Windows prototype has passed the recorded backend/frontend/browser suites and real local retrieval evaluation. It is **not fully verified against every delivery gate** because a fresh Docker Compose startup could not run. Read TEST_RESULTS.md and REQUIREMENTS.md for the exact evidence and current statuses.

## External blockers and execution limits

- **Fresh Compose startup: BLOCKED.** Docker was absent (`Get-Command docker` did not find an executable), and WSL was not installed. The Dockerfiles, health checks, isolated volumes and 4 GiB/256-process backend resource limits are configuration, not proof of a successful container run. A machine with Docker must perform the isolated clean-start, migration/seed/index, browser and restart checks.
- **Other operating systems: NOT RUN.** Only native Windows execution was observed. Linux/macOS commands and CI configuration are supplied without claiming those platforms passed.
- **Native Vite development optimizer:** the sandbox reported `EACCES` during the development optimizer path. The frontend production build and production preview on port 5173 worked and were used for browser verification. This environment-specific development-server issue is separate from the tested production bundle.
- **Actual live provider: NOT RUN.** No provider credentials were available. SDK adapter logic, citation rejection, privacy payload boundaries and failure behavior were tested with mocks. Required local mode uses actual cached embeddings/Chroma and no LLM API key.
- **Final packaging/fresh developer setup:** Phase 14 remains IN PROGRESS until the final deliverable audit and setup verification are recorded. A written walkthrough is not an observed independent fresh setup. A remote CI run was not observed.

## Dependency audit findings retained

`artifacts/test-results/backend-audit.json` reports five vulnerability entries for `chromadb==1.5.9`, representing **four unique CVEs** because CVE-2026-45829 appears twice. The recorded audit supplies no fixed versions. The backend must therefore not be described as vulnerability-free.

| Unique finding | Recorded affected behavior | Why the configured application does not expose that described path |
| --- | --- | --- |
| CVE-2026-45829 / GHSA-f4j7-r4q5-qw2c | Chroma HTTP collection creation can load an attacker-selected model with `trust_remote_code=true`, enabling code injection | The app uses embedded `PersistentClient`; no Chroma HTTP server is started or exposed. Vectors are supplied explicitly with `embedding_function=None`. The separately loaded pinned model uses `trust_remote_code=False` and `local_files_only=True`. |
| CVE-2026-45833 / GHSA-36p7-vc44-83pf | Chroma HTTP collection update with remote model/trusted code can permit code injection | Citizens/admins cannot submit Chroma collection/model configuration through this app. The embedded collection is application-created with explicit embeddings and the fixed model policy. |
| CVE-2026-45831 / GHSA-xph7-9rjv-w5fr | Chroma authorization permission checks can omit tenant/database/collection scope | No multi-tenant Chroma HTTP authorization service is exposed. The shared index contains public scheme passages only; private profiles/uploads remain outside it. |
| CVE-2026-45830 / GHSA-2wm9-hf6c-p5cr | Chroma HTTP authorization can permit cross-tenant collection operations | The application provides no Chroma HTTP endpoint or user-controlled tenant/collection access. API ownership applies separately to private PostgreSQL/upload records. |

This is an assessment of the recorded advisories against the current call paths, not proof that the dependency has no other reachable issues. The findings remain open. Do not expose a Chroma server, enable remote model code or place private citizen documents in the shared index without revisiting them. Upgrade and rerun the audit when a verified compatible fixed release is available. A deployment change invalidates the present reachability assessment.

The final frontend audit recorded zero findings after the React Router 7.18.4 and Vitest 4.1.11 dependency updates (`artifacts/test-results/frontend-audit.json`). That result applies to the recorded dependency tree and advisory snapshot, not to future advisories. Python `pip check` verifies dependency consistency; it does not replace a security audit.

## Data and domain boundaries

- The real/fictional scheme split is **0 real / 12 fictional**. Local source passages are redistributable academic fixtures, with no fabricated government verification date. The application cannot provide authoritative current welfare entitlement from this corpus.
- Five synthetic citizen scenarios exercise selected conditions. They do not represent the diversity of government requirements or citizen circumstances. No user study, official document validation, approval outcome or social-impact measurement was conducted.
- Eligibility means matching the encoded rule tree at the stated evaluation date. Source correctness and completeness require human review. Structural publication validation cannot establish that a real source is current or faithfully encoded.
- February 29 birthdays advance on March 1 in non-leap years. An official scheme using another convention would need an explicit policy adaptation.
- Readiness describes preparation completeness. An ineligible citizen can have complete paperwork; only an eligible result with satisfied mandatory items produces READY. No application is submitted and no application number is generated.

## Retrieval and live-answer limits

- The recorded real RAG result is 24/24 expected behaviors and 16/16 cited answerable responses on a small, labeled local dataset. Many questions select the scheme explicitly. These figures do not estimate broad retrieval recall, general factual accuracy or adversarial robustness.
- Local answers return retrieved source passages with templates. They are intentionally limited in paraphrasing and multi-step reasoning. Valid citations show where the displayed text came from; they do not guarantee that every passage answers every possible question completely.
- Instruction detection uses known textual patterns. Conflict detection looks for differing numerical statements in matching source sections. These are useful tested checks, not universal defenses or full semantic contradiction detection.
- Personal-question detection is heuristic. The API routes recognized personal eligibility questions to deterministic logic; a new phrasing may require choosing a scheme and using its explicit eligibility action.
- Live mode selects exact quotations and rejects forged IDs/unsupported text. It sends public passages and a locally chosen topic, not the original message/profile/upload/history. This constrains the richness of live answers, and paid provider availability/latency was not measured.
- Initial model/dependency installation requires internet access. Missing pinned model artifacts produce an actionable error. Cached local-only runtime does not mean a fresh machine can install offline without separately supplied artifacts.

## Document processing limits

- Required extraction supports the documented synthetic text-PDF templates. Arbitrary official layouts remain NEEDS_MANUAL_REVIEW. A supported marker/classification is not proof of authenticity.
- OCR is disabled. Valid images and scanned/textless PDFs remain NEEDS_OCR. Encrypted, corrupt, unsupported, empty and failed files are never reported as successful checks.
- The parser has file/page/text/content/time bounds and runs in a child process. POSIX adds an address-space limit. Native Windows does not currently apply a job-object memory limit, so its protections are not identical to POSIX. The configured container memory/process limits are untested until Compose can run.
- Name/state/category normalization is conservative; comparisons are exact after normalization, with no fuzzy name matching or income tolerance. Missing/invalid fields are UNKNOWN.
- User-confirmed corrections remain distinct from original extraction and evidence. They are not independent verification. Correcting recognized fields does not authenticate a document or silently update a profile.

## Local deployment and interface limits

- The supported local topology has one API worker. Rate limiting and embedding/index locking are process-local. Multiple workers or hosts would need coordinated limits and storage/index access.
- Access tokens live in browser memory and refresh tokens in tab-local sessionStorage. JavaScript can access refresh tokens; this design relies on XSS prevention and is not a substitute for a reviewed production authentication architecture.
- Localhost HTTP is for the demo. Public hosting, TLS termination, backups, monitored operations and deployment security assessment are outside the verified prototype.
- Administrator scheme editing uses a complete JSON editor with server validation. It is intended for a technical academic maintainer, not a fully designed nontechnical authoring workflow.
- Responsive behavior, keyboard-friendly labels/focus and selected recovery states were exercised; no external accessibility certification or comprehensive assistive-technology audit was performed.
- Optional OCR, Neo4j, multilingual support and AI simplification were deliberately excluded from required completion criteria.

The next required external action is to run the supplied clean Compose verification on a Docker-capable machine and save its actual results. Retain these limitations until their corresponding checks have passed; do not replace BLOCKED/NOT RUN with PASS based on code inspection alone.

# Implementation decisions

These decisions describe the implemented prototype. Execution evidence and outstanding gates are maintained separately in TEST_RESULTS.md, REQUIREMENTS.md and PROJECT_STATE.md.

| Decision | Reason and consequence |
| --- | --- |
| Twelve fictional schemes; zero purported real programs | The project needs stable offline source material, and no unverified threshold or government source should be presented as official. Every fixture is explicitly fictional, attributed to local authors, and has no fabricated retrieval date or government application link. Replacing fixtures with verified official rules is separate content work. |
| Pure deterministic domain service | Eligibility/readiness must be reproducible and testable without a model or database. All/any rules use three-valued semantics; no arbitrary code evaluation is allowed. LLM/document output cannot override eligibility. |
| PostgreSQL with Alembic, no SQLite fallback | Integration checks must exercise the intended database and migration path. An unavailable database is an explicit blocker. Native PostgreSQL was used when Docker was unavailable, without pretending that Compose had been tested. |
| Python 3.12.14 and React 18 | These satisfy the specified architecture and provide a consistent Python runtime and React baseline. Resolved dependencies are stored in backend/requirements.lock and frontend/pnpm-lock.yaml. Container execution still requires its own clean-start check. |
| JSONB for scheme/profile/extraction records | Typed application validators handle flexible nested rule and evidence structures; relational foreign keys protect ownership and sessions. Validation is enforced before publication/use. |
| Short JWT plus server-side session | A signed token alone cannot satisfy logout/replay requirements. Every authenticated request checks the session row; refresh token hashes and used-token retention support rotation and replay rejection. |
| Access token in memory, refresh token in sessionStorage | Avoids persisting access tokens between reloads and avoids cookie/CSRF complexity in the local prototype. JavaScript can access the refresh token, so this is not a claim of production-grade XSS resilience. HTTPS and reviewed credential storage are deployment work. |
| One backend worker | The local limiter, embedding object and index lock are process-local. A multi-worker deployment would otherwise weaken the rate limit and create additional coordination problems. |
| Inactive draft after scheme edit | Every revision needs explicit publication. Current eligibility/readiness use current scheme content; retrieval synchronizes active revisions and removes stale chunks before answering. Historical evaluation snapshots are not rewritten. |
| Explicit profile nulls and a fixed 15-field denominator | Incomplete profiles are allowed. Empty/null means unanswered; zero income and false booleans are valid supplied information. Completeness never stands in for eligibility or readiness. |
| March 1 convention for leap-day birthdays in non-leap years | Removes ambiguity in age boundaries. The convention is documented and tested; an official program with a different policy would need its rule definition adapted. |
| Deterministic ranking, not approval likelihood | Rank by status, then `70*S + 20*P + 10*J`, then stable ID. OR support uses the strongest satisfied alternative, so failed unused alternatives do not penalize a passing branch. See DOMAIN.md for definitions. |
| On-demand readiness and comparisons | Results recompute after profile edits, corrections, replacements and deletion, avoiding stale readiness caches. Eligibility and paperwork percentage remain separate. |
| Synthetic-template PDF parsing | Required deterministic extraction is tractable and independently testable. The parser recognizes in-content document markers, preserves evidence and leaves unknown layouts for manual review. It does not authenticate documents. |
| Isolated parser child with bounded time/input | A parser failure should not hang the API indefinitely. POSIX memory limiting is added; native Windows still lacks a parser job-object memory limit and this limitation is recorded. |
| Exact normalized comparisons | Names use Unicode/whitespace/case normalization; DOB and income use exact parsed values. No fuzzy matching, arbitrary percentage tolerance or inferred sensitive attributes hide mismatches. |
| Real CPU MiniLM embeddings and persistent Chroma | Meets offline local retrieval requirements while keeping deployment small. The verified revision is `bc57282bc374d33e0d6c4de27f12dc1c2a87f37a`. Missing artifacts raise setup errors; no synthetic vectors are substituted. |
| Deterministic extractive local answers | The local demo needs no provider key. Returning retrieved source passages with provenance makes support checkable. This is deliberately less flexible than unconstrained generated explanation. |
| Narrow optional live quotation adapter | Current Responses structured output selects source quotations with bounded retries and server validation. Only a public topic and public passages are sent, not raw message/profile/document/history. A mock adapter test is not counted as a live call. |
| Heuristic injection/conflict checks | Known instruction patterns and differing numeric claims in the same source section are identified. The implementation does not claim universal prompt-injection or semantic contradiction detection. |
| Printable HTML preparation summary | Meets the export requirement with browser printing, avoids adding a document-rendering service and never creates a fake government application number. |
| Admin JSON editor with server validation | Supports the complete nested source/rule/document schema with limited UI complexity. It is intended for the academic maintainer; a friendlier rule builder is future work. |
| Optional features excluded | OCR, Neo4j, multilingual output and AI simplification were not necessary for the required prototype. OCR-only inputs therefore remain visibly unresolved. |

## Rule/source provenance discipline

Each fixture source has a local reference, title, publisher, supporting passage and section. Real-world retrieval/effective dates are null because none were verified. Source labels remain visible in scheme and chat screens. All invented benefit amounts and eligibility thresholds are demonstrative fixture values, not claims about government policy. Administrative publication validation enforces structure; it cannot independently establish the correctness of a human-authored source.

## Test boundaries

Pure domain tests use independently specified fixture outcomes and a fixed evaluation date. PostgreSQL tests guard the target database before clearing test records. Document tests use only local synthetic fixtures. The real RAG test uses the actual model and an isolated persistent Chroma directory; provider tests use mocks and are labeled accordingly. Browser recovery tests may simulate a temporary failure to test retained form values; other primary journeys use the running backend and database.

Docker availability is an environmental gate. Passing native tests does not verify a clean container build, Compose volumes or another operating system. The live-provider call remains NOT RUN when credentials are absent.

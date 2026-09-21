# Sahaay: a deterministic and source-grounded welfare preparation prototype

## Abstract

Sahaay demonstrates a locally runnable workflow for scheme discovery, explicit eligibility reasoning, document consistency checks and application preparation. It combines a typed deterministic rule engine with source-based semantic retrieval, while keeping private citizen data outside the shared retrieval index. The study corpus contains twelve fictional schemes, five synthetic citizen scenarios, synthetic PDFs and twenty-four labeled chat queries. The recorded real local retrieval evaluation met the expected behavior for 24/24 queries and provided resolving citations with exact source support for 16/16 answerable queries. These are narrow fixture-based correctness results, not measurements of government policy accuracy, user outcomes or production reliability. Docker clean startup and live-provider execution remain subject to their separate recorded verification status.

## Problem and scope

Citizens need to distinguish scheme requirements, missing information and unfinished paperwork. An interface that treats every unknown field as false can incorrectly reject incomplete profiles. An unconstrained generated answer can invent eligibility or confuse a document being uploaded with a document being valid. The prototype addresses these engineering problems using explicit uncertainty, traceable rules, separate consistency checks and citations.

This implementation is an academic demonstration. It does not authenticate documents, determine official entitlement, promise approval or submit applications. Real government scheme sourcing was not completed, so every scheme is labeled fictional and its invented values remain local fixtures. No survey, field trial, causal impact study or research novelty is claimed.

## Methodology

The specification was implemented as a small React/FastAPI application backed by PostgreSQL, with Alembic migrations as the schema authority. Unit tests isolate deterministic logic. Integration tests use a guarded disposable PostgreSQL database. Document processing uses synthetic text-based PDFs and negative fixtures. Retrieval tests use actual CPU embeddings and persistent Chroma, separately from provider mocks. Browser journeys exercise the running services and inspect core user flows.

Independent fixture expectations use evaluation date 2026-09-20. The five cases cover an eligible citizen, an income-based rejection, missing information, a state-specific candidate and a document mismatch. Validation treats null/empty as unknown and preserves false/zero as supplied values. Every field is defined in `docs/DOMAIN.md`.

## Deterministic eligibility

Leaves support equality, inequality, ordered comparisons, membership and inclusive ranges. Rules are validated typed data; they are never executed as arbitrary code. Missing profile information yields UNKNOWN. Invalid rules are configuration errors, not citizen rejections.

| Group | PASS | FAIL | UNKNOWN |
| --- | --- | --- | --- |
| AND | All children pass | Any child fails | Otherwise |
| OR | Any child passes | All children fail | Otherwise |

The root maps to ELIGIBLE, NOT_ELIGIBLE or POTENTIALLY_ELIGIBLE. Incomplete or stale rule coverage cannot establish an unqualified eligible result. Age is derived at an explicit date, with March 1 used for leap-day birthdays in a non-leap year. Every result includes a full trace, relevant missing information and profile/rule revision metadata.

Recommendations sort by eligibility status, then a bounded score, then stable scheme ID. The score is `70*S + 20*P + 10*J`: rule support, required-profile coverage and jurisdiction relevance. AND support averages child support; OR takes the maximum. This avoids penalizing a valid alternative because another OR branch failed. The score ranks suggestions and is not an approval probability.

## Retrieval and answer support

The embedding model is `sentence-transformers/all-MiniLM-L6-v2`, pinned at revision `bc57282bc374d33e0d6c4de27f12dc1c2a87f37a`. First-time setup downloads the artifacts; runtime loading is local-only and disables remote code. Chroma stores normalized vectors with source metadata. A content/provenance hash identifies each chunk, and synchronization removes archived or superseded content.

Local answers quote retrieved passages and include scheme ID, source title/reference, section/page and chunk identity. Inadequate evidence receives an insufficient-information result. Personal eligibility questions route to the deterministic service. Known instruction patterns are rejected, and differing numeric statements for the same scheme section trigger uncertainty. These limited checks do not amount to universal semantic contradiction or injection detection.

The optional live adapter uses current OpenAI Responses structured output to select exact public source quotations. It transmits only those public passages and a locally selected topic. Returned IDs and quoted text must match retrieved passages. Provider timeouts, unavailable configuration and invalid output return visible errors. Tests of mocked providers cover adapter behavior; no live call was verified without credentials.

## Documents and preparation

Private uploads accept bounded PDF/PNG/JPEG content only when actual content agrees with the extension. A separate parser process enforces a timeout, bounded pages/text and content limits. Text-based synthetic forms are classified from content markers and parsed into fields with page evidence. Images and textless PDFs require OCR; encrypted/corrupt/spoofed inputs do not pass processing. The parser does not assign invented confidence percentages.

Consistency compares normalized names, dates, income, state/category and type-relevant fields. A missing value is UNKNOWN; a difference is MISMATCH. Confirmed manual corrections retain separate provenance and never silently overwrite the profile. Preparation is recomputed using current profile, document values and checks.

Readiness percentage is `100 * satisfied mandatory items / applicable mandatory items`, rounded to two decimals. Equivalent items are deduplicated, optional items do not change the denominator, and an unknown conditional requirement remains unresolved. Zero applicable mandatory items yields a documented not-applicable result. READY additionally requires ELIGIBLE and no unresolved mandatory item; complete paperwork alone cannot make an ineligible person ready.

## Recorded evaluation

The final native suite recorded **151 tests, zero failures/errors, zero skips** on September 21, 2026. It combines pure domain, real PostgreSQL API, PDF extraction, real local retrieval and hosting route tests. `docs/TEST_RESULTS.md` and the retained machine-readable artifacts are the exact execution ledger.

The actual embedding/Chroma evaluation artifact contains these denominators:

| Category | Cases | Observed expected behavior |
| --- | ---: | ---: |
| Answerable source questions | 16 | 16 answers with resolving chunk citations and exact excerpt support |
| Unsupported questions | 3 | 3 insufficient-information responses |
| Prompt injection questions | 2 | 2 rejected instruction attempts |
| Personal eligibility questions | 2 | 2 deterministic-service routing markers |
| Deliberately conflicting evidence | 1 | 1 uncertainty response |
| All labeled queries | 24 | 24 expected status outcomes |

The answerable checks require the correct scoped scheme, valid current chunk IDs, expected answer terms and verbatim cited excerpts. Their denominator is 16, not all 24 questions. The personal cases in this service-level artifact verify the dispatch marker only; actual profile evaluation belongs to API/browser integration checks. Persistence tests reopen the Chroma collection, verify repeat indexing adds no duplicates, change a source version and remove archived content.

Most answerable cases explicitly select a scheme, and the corpus is small. These results do not measure broad cross-scheme retrieval recall, free-form factual completeness or general language understanding. Verbatim support checks prevent unsupported quoted text, but they do not establish that every selected passage fully answers every possible question. The conflicting test uses controlled numeric differences in matching sections; this does not validate detection of arbitrary natural-language contradictions.

Frontend contract tests, production builds, browser journeys and security regressions have separate evidence. Browser screenshots show interface rendering but do not replace assertions or prove security. Provider mocks are not included as live model usage. Docker availability prevented the fresh Compose startup check in this environment, and neither macOS nor Linux runtime success was observed.

## Privacy and security analysis

The server derives citizen ownership from authenticated sessions for profiles, documents, chat, readiness and exports. Administrator analytics expose aggregate stored-record counts, not private conversations or uploads. Short-lived JWTs are checked against revocable sessions; refresh rotation retains used token hashes to reject replay. Passwords use Argon2. Rate limits, bounded request bodies, restricted CORS, escaped HTML and safe URL rendering reduce common local-web risks.

The documented deployment is a single backend worker. The process-local limiter/index lock must not be assumed to provide distributed coordination. Refresh tokens in sessionStorage remain accessible to JavaScript, so XSS protection is significant. Native Windows parsing has time/input bounds but lacks an OS job-object memory cap. Public production deployment would need dedicated threat modeling, secure transport, operational controls and review of privacy obligations.

## Limitations and future work

The highest-value next step is audited official-source onboarding, with program-specific rule coverage and version review. Other separate work includes broader retrieval evaluation, adversarial source testing, a reviewed production credential design, distributed rate limiting, operational monitoring, an accessible form-based admin rule builder and clean cross-platform container verification. OCR and multilingual assistance could follow only with explicit uncertainty/evidence handling and new evaluation data.

No user study or welfare outcome assessment was performed. Twelve fictional schemes and five synthetic profiles demonstrate engineering behavior; they cannot establish social benefit or policy correctness. The full honest completion status remains in the requirements and evidence documents.

## Sources and implementation references

- Project contract: `docs/SPECIFICATION.md`; executable business semantics: `backend/app/domain.py` and `docs/DOMAIN.md`.
- Local source corpus: `data/schemes.json`; synthetic cases: `data/citizens.json`; evaluation labels: `data/evaluation.json`.
- Observed results: `artifacts/test-results/backend.xml` and `artifacts/test-results/rag-evaluation.json`.
- Sentence Transformers API: https://sbert.net/docs/package_reference/sentence_transformer/SentenceTransformer.html — local-only loading, pinned revision and embedding interface.
- Pinned model repository: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/bc57282bc374d33e0d6c4de27f12dc1c2a87f37a — verified model revision.
- Chroma documentation: https://docs.trychroma.com/docs/collections/add-data — collection data interface.
- OpenAI structured outputs documentation: https://developers.openai.com/api/docs/guides/structured-outputs — Responses SDK structured parsing; consulted for the optional adapter, not evidence of a paid live call.

These are implementation references and local project evidence. They are not fabricated academic citations or official sources for the fictional scheme amounts.

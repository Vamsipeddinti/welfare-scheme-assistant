# Deterministic domain contract

`backend/app/domain.py` is pure Python, without database, network, model, or provider dependencies. It produces preparation guidance against encoded rules. It does not determine official entitlement, authenticate documents, or submit applications.

## Profile dictionary

Exactly 15 fields form the completeness denominator. Every field is nullable, and omission means unknown. Empty or whitespace-only strings normalize to null. Zero income and false booleans are supplied values. No name or document inference supplies sensitive attributes.

| Field | Type and normalization |
| --- | --- |
| `full_name` | Non-empty string, internal whitespace collapsed, case retained |
| `date_of_birth` | ISO `YYYY-MM-DD`, real date from 1900-01-01 through today |
| `gender` | `female`, `male`, `non_binary`, `other`, `prefer_not_to_say` |
| `annual_family_income` | Nonnegative finite numeric INR amount; strings and booleans rejected |
| `has_bank_account` | Boolean or null |
| `employment_status` | `employed`, `unemployed`, `self_employed`, `retired`, `student`, `homemaker` |
| `occupation` | Whitespace normalized, case folded; user-supplied free text |
| `state` | One of the 28 states or 8 union territories in the `STATES` constant; casing normalized |
| `district` | User-supplied whitespace-normalized text; no inferred location |
| `location_type` | `urban`, `rural` |
| `social_category` | `general`, `obc`, `sc`, `st`, `ews` |
| `disability_status` | Boolean or null |
| `education_level` | `none`, `primary`, `secondary`, `higher_secondary`, `diploma`, `graduate`, `postgraduate`, `other` |
| `student_status` | Boolean or null |
| `marital_status` | `single`, `married`, `widowed`, `divorced`, `separated` |

Enum input is case-insensitive; spaces and hyphens normalize to underscores. Text is limited to 200 characters. An optional nonnegative integer `revision` is preserved as metadata and excluded from completeness. The backend owns revision increments. Unknown keys and malformed values raise `ValueError`; no implicit numeric or boolean coercion occurs.

`validate_profile(data, partial=True)` returns only supplied normalized keys. `partial=False` fills missing profile fields with null; it does not require citizens to complete the profile. The API merges partial updates and explicitly supplied nulls clear values. `completeness(profile)` returns `round(100 * supplied_fields / 15, 2)`.

## Rule tree, age, and explanation

A leaf is `{field, op, value, source?}`. A group is exactly `{all: [rules]}` or `{any: [rules]}`, optionally with source metadata. Publication must validate the rule tree and source record. Unknown operators/fields, empty groups, unsupported comparisons, reversed ranges, wrong value types, and excessively nested trees raise configuration errors. They never become citizen rejections. Groups have 1–100 children; maximum nesting depth is 20.

All operators are supported: `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `not_in`, and inclusive `between`. Ordered comparisons are only valid for numbers, derived age, and dates. Membership uses nonempty typed arrays; ranges use exactly two ascending typed bounds. Null rule values are invalid. Boolean and numeric values are distinct.

Age is derived from DOB at an explicit `date` passed as `on`; default is the server's current date. February 29 birthdays reach their next age on March 1 in non-leap years. DOB after the evaluation date is invalid. Citizens cannot supply an `age` profile field.

AND fails if any child fails, passes when all pass, and is otherwise unknown. OR passes if any child passes, fails when all fail, and is otherwise unknown. Evaluation always retains every child trace. Determinate PASS/FAIL groups expose no unresolved missing fields; their child traces still preserve unknown alternatives. An unknown OR alternative never blocks a passing OR. Unknown derived age requests `date_of_birth`.

`evaluate(rule, profile, on=None)` returns `result`, `children`, `missing_fields`, `reason`, and source; leaf traces also include `field`, `op`, `value`, and `expected`. `eligibility(scheme, profile, on=None)` maps PASS/FAIL/UNKNOWN to ELIGIBLE/NOT_ELIGIBLE/POTENTIALLY_ELIGIBLE and returns the trace, relevant missing information, rule version, profile revision, evaluation date, coverage, and guidance disclaimer. Incomplete or stale coverage cannot produce ELIGIBLE. A date outside a provided scheme validity window also requires more information. Missing coverage is treated as incomplete. A missing or invalid rule raises an error.

## Recommendation formula

Only active schemes appear. Default results exclude NOT_ELIGIBLE; an explicit filter includes them. Sort order is eligibility status (eligible first, then potential, then not eligible), descending score, then ascending stable scheme ID.

The bounded 0–100 score is `70 * S + 20 * P + 10 * J`:

- `S`: leaf PASS=1, UNKNOWN=0.5, FAIL=0. AND is the arithmetic mean of child support; OR is the maximum child support. Failed unused OR branches cannot lower a satisfied OR's support.
- `P`: fraction of distinct scheme-required profile fields supplied. No required profile fields means 1.
- `J`: 1 for a matching state jurisdiction, 0.5 for national jurisdiction (`India`, `national`, or `all india`), otherwise 0. Eligibility jurisdiction restrictions must still appear in the actual rule tree.

Scores are rounded to two decimals and explain ranking, not approval probability. `recommendations(schemes, profile, include_ineligible=False, on=None)` returns each scheme, scheme ID, full eligibility result, status, score components, explanation, and next steps. The optional evaluation date makes fixture tests reproducible.

## Document and readiness contract

Required document groups are `{id, any_of: [document_type], fields: [profile_field], mandatory: bool, condition?: rule}`. Supported fixtures use `identity_proof`, `birth_certificate`, `income_certificate`, `residence_proof`, `student_certificate`, `category_certificate`, `disability_certificate`, `employment_certificate`, and `bank_statement`.

Readiness consumes private server-owned document dictionaries with `id`, `document_type`, `status`, `fields`, `corrections`, and `checks`. Fields contain extracted scalar values. Corrections contain either scalar accepted values or `{value, ...provenance}`. The API must require user confirmation before persisting corrections. Extraction evidence and original values remain separate from corrections. Checks are a list of `{field, status: MATCH|MISMATCH|UNKNOWN, reason, profile_value?, document_value?}` generated against the current profile; the server must recompute them after relevant changes. The domain does not trust a correction alone to change a MISMATCH to MATCH.

A required document is satisfied only when a recognized alternative has status PROCESSED, every required field exists in extracted/corrected values, every required field has an explicit MATCH check, and no check on that document is unresolved. NEEDS_OCR, NEEDS_MANUAL_REVIEW, FAILED, and other unprocessed statuses cannot satisfy the group. The filename is irrelevant. One acceptable alternative satisfies the group, while another relevant document's unresolved consistency result remains separately visible until corrected or removed. User corrections are labeled as user-confirmed, not independently verified.

Profile fields and equivalent document groups are deduplicated. If identical optional and mandatory document requirements both exist, mandatory takes precedence. False conditional document requirements are excluded. Unknown conditions remain mandatory unresolved items when their underlying requirement is mandatory; they cannot disappear from the denominator. Invalid conditional rule/document definitions raise configuration errors even when the condition would be false.

The checklist includes required profile fields, applicable document groups, and unresolved consistency results for applicable mandatory document types. Percentage is `round(100 * satisfied_mandatory / applicable_mandatory, 2)`. Optional items do not affect the denominator. Zero denominator returns `percentage: null, status: NOT_APPLICABLE`. Eligibility and percentage remain separate: complete paperwork for an ineligible citizen can be 100% and NOT_ELIGIBLE. READY requires ELIGIBLE and every mandatory item satisfied. Unknown rules/requirements produce NEEDS_INFORMATION; missing documents and mismatches produce INCOMPLETE unless eligibility takes precedence. Remaining actions and document-authentication/submission disclaimers are returned.

`readiness(scheme, profile, documents, on=None)` is computed afresh, so deletion, replacement, corrected checks, profile changes, and scheme edits can change the result without stale cached outcomes.

## Fixture provenance and independent expectations

The real/fictional split is **0 real / 12 fictional**. Each name starts with “Demo”, `is_fictional` is true, the publisher is the academic demo authors, and the source is `data/schemes.json#<id>`. No government URL, source verification date, actual entitlement, or application link is invented. All sources have null `url`, `retrieved_at`, and `effective_date`; their local passages describe every invented threshold and required document. Benefit values are illustrative and no money is paid. This is an offline local source corpus, not research on government programs.

Five citizens in `data/citizens.json` are synthetic and use reserved `example.test` email addresses. Their independent expected outcomes use fixed evaluation date 2026-09-20:

| Citizen scenario | Family support eligibility | Readiness | Percentage |
| --- | --- | --- | --- |
| Asha, eligible and matching documents | ELIGIBLE | READY | 100 |
| Ravi, income above threshold but complete paperwork | NOT_ELIGIBLE | NOT_ELIGIBLE | 100 |
| Noor, missing income and bank answer/documents | POTENTIALLY_ELIGIBLE | NEEDS_INFORMATION | 37.5 |
| Kiran, Karnataka-specific candidate | ELIGIBLE | READY | 100 |
| Meera, income certificate mismatch | ELIGIBLE | INCOMPLETE | 77.78 |

Kiran additionally matches Demo Karnataka Skills and does not match Demo Telangana Student. Meera's income certificate contains 120000 while the profile contains 150000. A confirmed correction to 150000 followed by server recomputation changes readiness to READY / 100%; preserving the original extracted value is required. Her initial denominator includes five required profile fields, three document groups, and one unresolved consistency item.

`data/evaluation.json` contains 24 labeled chat/retrieval cases: 16 answerable, 3 unsupported, 2 injection, 2 personal eligibility, and 1 conflicting-evidence case. The conflict case includes two deliberately conflicting test chunks; ordinary published fixture content is internally consistent. Dataset existence is not a retrieval evaluation result. Actual model/retrieval/provider results must be recorded separately with denominators.

## Observed domain verification

On the Windows workspace, the parent-provided Python virtual environment executed these commands from `welfare-ai-platform/backend`:

```powershell
..\.venv\Scripts\python.exe -m compileall -q app/domain.py
..\.venv\Scripts\python.exe -m pytest tests/test_domain.py -q
..\.venv\Scripts\python.exe -m ruff check app/domain.py tests/test_domain.py
```

Initial observed result: compilation exit 0; **124 domain tests passed**; Ruff exit 0. A pytest iterable deprecation in the test parameter list was corrected and the suite re-run. Tests cover the full two-child truth tables, all operators, numeric boundaries, leap days, false/null/zero, malformed input, coverage, score order/OR semantics, readiness alternatives/conditions/mismatch/corrections/deletion/deduplication, and all five citizen scenarios. These are pure unit tests; they make no claim about PostgreSQL, extraction, actual embeddings, browser journeys, containers, or a live provider.

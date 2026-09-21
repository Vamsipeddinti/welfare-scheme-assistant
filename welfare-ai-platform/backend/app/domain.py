"""Deterministic, dependency-free welfare guidance contracts.

No function determines official entitlement or authenticates a document.
See docs/DOMAIN.md for normalization, age, score, and readiness policies.
"""

from __future__ import annotations

import json
import math
from datetime import date
from typing import Any


STATES = (
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
)

PROFILE_FIELDS = (
    "full_name", "date_of_birth", "gender", "annual_family_income",
    "has_bank_account", "employment_status", "occupation", "state", "district",
    "location_type", "social_category", "disability_status", "education_level",
    "student_status", "marital_status",
)
BOOLEAN_FIELDS = {"has_bank_account", "disability_status", "student_status"}
NUMBER_FIELDS = {"annual_family_income", "age"}
ENUMS = {
    "gender": ("female", "male", "non_binary", "other", "prefer_not_to_say"),
    "employment_status": ("employed", "unemployed", "self_employed", "retired", "student", "homemaker"),
    "location_type": ("urban", "rural"),
    "social_category": ("general", "obc", "sc", "st", "ews"),
    "education_level": ("none", "primary", "secondary", "higher_secondary", "diploma", "graduate", "postgraduate", "other"),
    "marital_status": ("single", "married", "widowed", "divorced", "separated"),
}
OPERATORS = {"==", "!=", "<", "<=", ">", ">=", "in", "not_in", "between"}


def _date(value: Any, label: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO YYYY-MM-DD date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid ISO YYYY-MM-DD date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{label} must be an ISO YYYY-MM-DD date")
    return parsed


def _value(field: str, value: Any, *, rule: bool = False) -> Any:
    if field in BOOLEAN_FIELDS:
        if type(value) is not bool:
            raise ValueError(f"{field} must be a boolean, not a string or number")
        return value
    if field in NUMBER_FIELDS:
        if type(value) not in (int, float) or (isinstance(value, int) and value.bit_length() > 1023) or not math.isfinite(value):
            raise ValueError(f"{field} must be a finite number")
        if value < 0:
            raise ValueError(f"{field} cannot be negative")
        if field == "age" and (type(value) is not int or value > 130):
            raise ValueError("age must be an integer between 0 and 130")
        return value
    if field == "date_of_birth":
        parsed = _date(value, field)
        if not rule and (parsed > date.today() or parsed < date(1900, 1, 1)):
            raise ValueError("date_of_birth must be between 1900-01-01 and today")
        return parsed.isoformat()
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError(f"{field} must be a non-empty string of at most 200 characters")
    value = " ".join(value.split())
    if field in ENUMS:
        value = value.casefold().replace("-", "_").replace(" ", "_")
        if value not in ENUMS[field]:
            raise ValueError(f"Unsupported {field}; choose one of {', '.join(ENUMS[field])}")
    elif field == "state":
        normalized_states = {s.casefold(): s for s in STATES}
        if value.casefold() not in normalized_states:
            raise ValueError("state must be a supported Indian state or union territory")
        value = normalized_states[value.casefold()]
    elif field == "occupation":
        value = value.casefold()
    return value


def validate_profile(profile: dict, partial: bool = True) -> dict:
    """Normalize supplied profile fields; explicit nulls clear values.

    With partial=False return every field, filling absent fields with None.
    The integer revision is optional metadata and never counts as completeness.
    """
    if not isinstance(profile, dict):
        raise ValueError("profile must be an object")
    if not all(isinstance(key, str) for key in profile):
        raise ValueError("Profile field names must be strings")
    unknown = set(profile) - set(PROFILE_FIELDS) - {"revision"}
    if unknown:
        raise ValueError(f"Unknown profile fields: {', '.join(sorted(unknown))}")
    result = {} if partial else dict.fromkeys(PROFILE_FIELDS)
    for field, value in profile.items():
        if field == "revision":
            if type(value) is not int or value < 0:
                raise ValueError("revision must be a nonnegative integer")
            result[field] = value
        elif value is None or (isinstance(value, str) and not value.strip()):
            result[field] = None
        else:
            result[field] = _value(field, value)
    return result


def completeness(profile: dict) -> float:
    normalized = validate_profile(profile)
    return round(100 * sum(normalized.get(field) is not None for field in PROFILE_FIELDS) / len(PROFILE_FIELDS), 2)


def validate_rule(rule: dict, _depth: int = 0) -> dict:
    """Return normalized rule or raise configuration error before evaluation."""
    if not isinstance(rule, dict) or _depth > 20:
        raise ValueError("Rule must be an object with nesting depth at most 20")
    groups = [key for key in ("all", "any") if key in rule]
    if groups:
        if len(groups) != 1 or set(rule) - {groups[0], "source"}:
            raise ValueError("Rule groups must contain exactly one of all/any")
        key = groups[0]
        if not isinstance(rule[key], list) or not rule[key] or len(rule[key]) > 100:
            raise ValueError("Rule groups require 1 to 100 child rules")
        result = {key: [validate_rule(child, _depth + 1) for child in rule[key]]}
    else:
        if set(rule) - {"field", "op", "value", "source"} or not {"field", "op", "value"} <= set(rule):
            raise ValueError("Leaf rules require field, op, value and optional source")
        field, op = rule["field"], rule["op"]
        if not isinstance(field, str) or field not in {*PROFILE_FIELDS, "age"}:
            raise ValueError("Rule field is not in the profile field dictionary")
        if not isinstance(op, str) or op not in OPERATORS:
            raise ValueError("Unsupported rule operator")
        ordered = field in NUMBER_FIELDS or field == "date_of_birth"
        if not ordered and op not in {"==", "!=", "in", "not_in"}:
            raise ValueError(f"Operator {op} is not supported for {field}")
        if op in {"in", "not_in", "between"}:
            raw = rule["value"]
            if not isinstance(raw, list) or not raw or (op == "between" and len(raw) != 2):
                raise ValueError("Membership requires a non-empty array; between requires exactly two bounds")
            values = [_value(field, item, rule=True) for item in raw]
            if op == "between" and values[0] > values[1]:
                raise ValueError("between lower bound cannot exceed upper bound")
            result = {"field": field, "op": op, "value": values}
        else:
            result = {"field": field, "op": op, "value": _value(field, rule["value"], rule=True)}
    if "source" in rule:
        if not isinstance(rule["source"], (str, dict)) or not rule["source"]:
            raise ValueError("Rule source must be a non-empty reference or metadata object")
        result["source"] = rule["source"]
    return result


def age_on(birth_date: str, on: date) -> int:
    """In a non-leap year, a 29 February birthday is observed on 1 March."""
    born = _date(birth_date, "date_of_birth")
    if born > on:
        raise ValueError("date_of_birth cannot be after the evaluation date")
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def _evaluate(rule: dict, profile: dict, on: date) -> dict:
    group = "all" if "all" in rule else "any" if "any" in rule else None
    if group:
        children = [_evaluate(child, profile, on) for child in rule[group]]
        outcomes = [child["result"] for child in children]
        if group == "all":
            result = "FAIL" if "FAIL" in outcomes else "PASS" if all(s == "PASS" for s in outcomes) else "UNKNOWN"
        else:
            result = "PASS" if "PASS" in outcomes else "FAIL" if all(s == "FAIL" for s in outcomes) else "UNKNOWN"
        missing = sorted({field for child in children for field in child["missing_fields"]}) if result == "UNKNOWN" else []
        return {"result": result, "group": group, "children": children, "missing_fields": missing,
                "reason": {"PASS": "The encoded requirement group is satisfied.", "FAIL": "The encoded requirement group is not satisfied.", "UNKNOWN": "More profile information is needed for this requirement group."}[result],
                "source": rule.get("source")}
    field, op, expected = rule["field"], rule["op"], rule["value"]
    value = profile.get(field)
    if field == "age":
        value = age_on(profile["date_of_birth"], on) if profile.get("date_of_birth") is not None else None
    if value is None:
        result, reason = "UNKNOWN", f"Provide {field.replace('_', ' ')} to evaluate this requirement."
    else:
        if op == "==":
            passed = value == expected
        elif op == "!=":
            passed = value != expected
        elif op == "<":
            passed = value < expected
        elif op == "<=":
            passed = value <= expected
        elif op == ">":
            passed = value > expected
        elif op == ">=":
            passed = value >= expected
        elif op == "in":
            passed = value in expected
        elif op == "not_in":
            passed = value not in expected
        else:
            passed = expected[0] <= value <= expected[1]
        result = "PASS" if passed else "FAIL"
        reason = f"{field.replace('_', ' ')} {op} {expected!r}: {'matches' if passed else 'does not match'} the encoded rule."
    return {"result": result, "field": field, "op": op, "value": value, "expected": expected,
            "children": [], "missing_fields": [("date_of_birth" if field == "age" else field)] if result == "UNKNOWN" else [],
            "reason": reason, "source": rule.get("source")}


def evaluate(rule: dict, profile: dict, on: date | None = None) -> dict:
    day = on or date.today()
    if type(day) is not date:
        raise ValueError("Evaluation date must be a date object")
    return _evaluate(validate_rule(rule), validate_profile(profile), day)


def eligibility(scheme: dict, profile: dict, on: date | None = None) -> dict:
    day = on or date.today()
    trace = evaluate(scheme.get("rules"), profile, day)
    status = {"PASS": "ELIGIBLE", "FAIL": "NOT_ELIGIBLE", "UNKNOWN": "POTENTIALLY_ELIGIBLE"}[trace["result"]]
    missing = list(trace["missing_fields"])
    coverage = scheme.get("coverage", "incomplete")
    if not isinstance(coverage, str) or coverage not in {"complete", "incomplete", "stale"}:
        raise ValueError("Scheme coverage must be complete, incomplete, or stale")
    if coverage != "complete" and status != "NOT_ELIGIBLE":
        status = "POTENTIALLY_ELIGIBLE"
        missing.append("scheme_rule_coverage")
    for key in ("valid_from", "valid_until"):
        if scheme.get(key):
            boundary = _date(scheme[key], key)
            if (key == "valid_from" and day < boundary) or (key == "valid_until" and day > boundary):
                status = "POTENTIALLY_ELIGIBLE" if status != "NOT_ELIGIBLE" else status
                missing.append("scheme_validity")
    return {"status": status, "trace": trace, "missing_information": sorted(set(missing)),
            "rule_version": scheme.get("version", 1), "profile_revision": profile.get("revision", 0),
            "evaluation_date": day.isoformat(), "coverage": coverage,
            "explanation": "This result describes matching the encoded rules, not official entitlement or approval."}


def _support(trace: dict) -> float:
    if not trace["children"]:
        return {"PASS": 1.0, "UNKNOWN": 0.5, "FAIL": 0.0}[trace["result"]]
    scores = [_support(child) for child in trace["children"]]
    return max(scores) if trace["group"] == "any" else sum(scores) / len(scores)


def _required_fields(scheme: dict) -> list:
    fields = scheme.get("required_fields", [])
    if not isinstance(fields, list) or not all(isinstance(field, str) and field in PROFILE_FIELDS for field in fields):
        raise ValueError("Scheme required_fields must be an array of known profile fields")
    return sorted(set(fields))


def recommendations(schemes: list, profile: dict, include_ineligible: bool = False, on: date | None = None) -> list:
    profile = validate_profile(profile)
    result = []
    order = {"ELIGIBLE": 0, "POTENTIALLY_ELIGIBLE": 1, "NOT_ELIGIBLE": 2}
    for scheme in schemes:
        if not scheme.get("active", False):
            continue
        outcome = eligibility(scheme, profile, on)
        if outcome["status"] == "NOT_ELIGIBLE" and not include_ineligible:
            continue
        fields = _required_fields(scheme)
        field_fraction = sum(profile.get(field) is not None for field in fields) / len(fields) if fields else 1.0
        jurisdiction = scheme.get("jurisdiction", "India")
        if isinstance(jurisdiction, dict):
            jurisdiction = jurisdiction.get("state") or jurisdiction.get("level", "India")
        jurisdiction = str(jurisdiction)
        local_match = 1.0 if profile.get("state") == jurisdiction else 0.5 if jurisdiction.casefold() in {"india", "national", "all india"} else 0.0
        support = _support(outcome["trace"])
        score = round(70 * support + 20 * field_fraction + 10 * local_match, 2)
        result.append({"scheme": scheme, "scheme_id": scheme["id"], "eligibility": outcome,
                       "status": outcome["status"], "score": score,
                       "score_components": {"rule_support": round(70 * support, 2), "required_profile_fields": round(20 * field_fraction, 2), "jurisdiction_relevance": 10 * local_match},
                       "score_explanation": "Ranking score (0–100), not approval probability: 70 rule support + 20 required profile coverage + 10 jurisdiction relevance.",
                       "next_steps": outcome["missing_information"] or ["Review the preparation checklist and source before applying."]})
    return sorted(result, key=lambda item: (order[item["status"]], -item["score"], str(item["scheme_id"])))


def _effective_fields(document: dict) -> dict:
    values = dict(document.get("fields") or {})
    for field, correction in (document.get("corrections") or {}).items():
        values[field] = correction.get("value") if isinstance(correction, dict) else correction
    return values


def _document_item(group: dict, documents: list) -> dict:
    types, fields = group.get("any_of", []), group.get("fields", [])
    if not isinstance(types, list) or not types or not all(isinstance(t, str) and t for t in types):
        raise ValueError("Required document groups need at least one document type")
    if not isinstance(fields, list) or not all(isinstance(field, str) and field in PROFILE_FIELDS for field in fields):
        raise ValueError("Required document content fields must be profile fields")
    candidates = [doc for doc in documents if doc.get("document_type") in types]
    best = None
    rank = {"SATISFIED": 0, "MISMATCH": 1, "UNKNOWN": 2, "MISSING": 3}
    for doc in candidates:
        effective = _effective_fields(doc)
        raw_checks = doc.get("checks") or []
        checks = {check["field"]: check.get("status", "UNKNOWN") for check in raw_checks if isinstance(check, dict) and "field" in check}
        if doc.get("status") != "PROCESSED":
            status, reason = "UNKNOWN", "Document processing or manual review is unresolved."
        elif any(check == "MISMATCH" for check in checks.values()):
            status, reason = "MISMATCH", "Document data differs from the current profile."
        elif any(effective.get(field) is None or effective.get(field) == "" or checks.get(field) != "MATCH" for field in fields):
            status, reason = "UNKNOWN", "Required content or a matching consistency check is missing."
        elif any(check not in {"MATCH"} for check in checks.values()):
            status, reason = "UNKNOWN", "Document consistency checks remain unresolved."
        else:
            status, reason = "SATISFIED", "Required document content matches the current profile."
        item = {"status": status, "reason": reason, "document_id": doc.get("id"),
                "manual_confirmation": bool(doc.get("corrections")),
                "evidence_label": "Includes user-confirmed corrections; not independently verified." if doc.get("corrections") else "Extracted content consistency only; not document authentication."}
        if best is None or rank[status] < rank[best["status"]]:
            best = item
    return best or {"status": "MISSING", "reason": f"Provide one of: {', '.join(types)}.", "document_id": None, "manual_confirmation": False}


def readiness(scheme: dict, profile: dict, documents: list, on: date | None = None) -> dict:
    profile = validate_profile(profile)
    outcome = eligibility(scheme, profile, on)
    if not isinstance(documents, list) or not all(isinstance(doc, dict) for doc in documents):
        raise ValueError("documents must be an array of document objects")
    items = []
    required_fields = _required_fields(scheme)
    for field in required_fields:
        supplied = profile.get(field) is not None
        items.append({"id": f"profile:{field}", "kind": "profile", "field": field,
                      "label": field.replace("_", " "), "mandatory": True,
                      "status": "SATISFIED" if supplied else "MISSING",
                      "reason": "Profile field supplied." if supplied else "Complete this profile field."})
    groups = scheme.get("required_documents", [])
    if not isinstance(groups, list):
        raise ValueError("required_documents must be an array")
    unique_groups = {}
    for group in groups:
        if not isinstance(group, dict) or type(group.get("mandatory", True)) is not bool:
            raise ValueError("Document requirements must be objects with boolean mandatory")
        _document_item(group, [])  # Validate even an inactive conditional branch.
        normalized = dict(group)
        if group.get("condition") is not None:
            normalized["condition"] = validate_rule(group["condition"])
        identity = (tuple(sorted(set(group.get("any_of", [])))), tuple(sorted(set(group.get("fields", [])))), json.dumps(normalized.get("condition"), sort_keys=True))
        if identity in unique_groups:
            unique_groups[identity]["mandatory"] = unique_groups[identity].get("mandatory", True) or group.get("mandatory", True)
        else:
            unique_groups[identity] = normalized
    applicable_types = set()
    for group in unique_groups.values():
        item = {"id": f"document:{group.get('id', len(items))}", "kind": "document",
                "label": " or ".join(group.get("any_of", [])), "mandatory": group.get("mandatory", True),
                "any_of": group.get("any_of", []), "fields": group.get("fields", [])}
        if group.get("condition") is not None:
            condition = evaluate(group["condition"], profile, on)
            if condition["result"] == "FAIL":
                continue
            if condition["result"] == "UNKNOWN":
                item.update(status="UNKNOWN", reason="Provide information to determine whether this document is required.", condition=condition)
                items.append(item)
                continue
        item.update(_document_item(group, documents))
        if item["mandatory"]:
            applicable_types.update(group.get("any_of", []))
        items.append(item)
    # Independent unresolved discrepancies must remain visible even if a second
    # document satisfies a document alternative. Removal/correction resolves them.
    for index, doc in enumerate(documents):
        if doc.get("document_type") not in applicable_types:
            continue
        for check in doc.get("checks") or []:
            if not isinstance(check, dict) or check.get("status") == "MATCH":
                continue
            field = check.get("field", "unknown")
            identifier = f"consistency:{doc.get('id', index)}:{field}"
            if any(item["id"] == identifier for item in items):
                continue
            items.append({"id": identifier, "kind": "consistency", "label": f"Resolve {field.replace('_', ' ')} consistency",
                          "mandatory": True, "status": "MISMATCH" if check.get("status") == "MISMATCH" else "UNKNOWN",
                          "reason": check.get("reason", "Document consistency must be resolved."), "document_id": doc.get("id")})
    mandatory = [item for item in items if item["mandatory"]]
    satisfied = sum(item["status"] == "SATISFIED" for item in mandatory)
    denominator = len(mandatory)
    percentage = round(100 * satisfied / denominator, 2) if denominator else None
    if not denominator:
        status = "NOT_APPLICABLE"
    elif outcome["status"] == "NOT_ELIGIBLE":
        status = "NOT_ELIGIBLE"
    elif outcome["status"] != "ELIGIBLE" or any(item["status"] == "UNKNOWN" for item in mandatory):
        status = "NEEDS_INFORMATION"
    elif satisfied == denominator:
        status = "READY"
    else:
        status = "INCOMPLETE"
    return {"percentage": percentage, "status": status, "items": items, "eligibility": outcome,
            "satisfied_mandatory": satisfied, "applicable_mandatory": denominator,
            "remaining_actions": [item["reason"] for item in mandatory if item["status"] != "SATISFIED"],
            "disclaimer": "Application preparation guidance only; no documents are authenticated and no government application has been submitted."}

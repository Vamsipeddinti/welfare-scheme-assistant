"""Business-contract tests without a database, model, network, or provider."""

import copy
import itertools
import json
from datetime import date
from pathlib import Path

import pytest

from app.domain import (
    PROFILE_FIELDS,
    age_on,
    completeness,
    eligibility,
    evaluate,
    readiness,
    recommendations,
    validate_profile,
    validate_rule,
)


DAY = date(2026, 9, 20)
DATA = Path(__file__).resolve().parents[2] / "data"
SCHEMES = json.loads((DATA / "schemes.json").read_text(encoding="utf-8"))
CITIZENS = json.loads((DATA / "citizens.json").read_text(encoding="utf-8"))


def rule(field="annual_family_income", op="<=", value=200000):
    return {"field": field, "op": op, "value": value, "source": "test://fixture"}


def scheme(tree=None, **kwargs):
    result = {"id": "test", "name": "Fictional test", "active": True,
              "coverage": "complete", "version": 3, "rules": tree or rule(),
              "jurisdiction": "India", "required_fields": [], "required_documents": []}
    result.update(kwargs)
    return result


def document(value="Asha Rao", status="MATCH", **kwargs):
    result = {"id": "doc-a", "document_type": "identity_proof", "status": "PROCESSED",
              "fields": {"full_name": value}, "corrections": {},
              "checks": [{"field": "full_name", "status": status, "reason": "Fixture consistency."}]}
    result.update(kwargs)
    return result


def group(**kwargs):
    result = {"id": "identity", "any_of": ["identity_proof", "birth_certificate"],
              "fields": ["full_name"], "mandatory": True}
    result.update(kwargs)
    return result


def test_profile_normalization_and_fixed_completeness_denominator():
    value = validate_profile({"full_name": "  Asha   Rao ", "state": " telangana ",
                              "location_type": " RURAL ", "annual_family_income": 0,
                              "has_bank_account": False, "student_status": None,
                              "occupation": " Tailor ", "revision": 9})
    assert value["full_name"] == "Asha Rao"
    assert value["state"] == "Telangana"
    assert value["occupation"] == "tailor"
    assert value["location_type"] == "rural"
    assert value["annual_family_income"] == 0
    assert value["has_bank_account"] is False
    assert completeness(value) == 40.0  # Six supplied fields / fifteen, not truthiness.
    assert len(PROFILE_FIELDS) == 15
    assert completeness({"full_name": "  ", "student_status": None, "revision": 2}) == 0


def test_profile_all_fields_can_be_cleared_and_full_mode_preserves_missing():
    assert validate_profile({"state": ""}) == {"state": None}
    assert validate_profile({}, partial=False) == dict.fromkeys(PROFILE_FIELDS)


@pytest.mark.parametrize("profile", [
    [], None, {"extra": 1}, {1: "name"}, {"has_bank_account": "false"},
    {"has_bank_account": 0}, {"student_status": 1}, {"disability_status": "yes"},
    {"annual_family_income": True}, {"annual_family_income": "100"},
    {"annual_family_income": -1}, {"annual_family_income": float("inf")},
    {"annual_family_income": float("nan")}, {"date_of_birth": "2025-02-29"},
    {"date_of_birth": "2099-01-01"}, {"date_of_birth": "1899-12-31"},
    {"date_of_birth": "20200101"}, {"gender": "invented"}, {"state": "Atlantis"},
    {"revision": True}, {"revision": -1}, {"full_name": "a" * 201},
])
def test_profile_rejects_invalid_values(profile):
    with pytest.raises(ValueError):
        validate_profile(profile)


@pytest.mark.parametrize("op,expected,value,result", [
    ("==", 10, 10, "PASS"), ("!=", 10, 10, "FAIL"),
    ("<", 10, 10, "FAIL"), ("<", 10, 9, "PASS"),
    ("<=", 10, 10, "PASS"), (">", 10, 10, "FAIL"),
    (">", 10, 11, "PASS"), (">=", 10, 10, "PASS"),
    ("in", [0, 10], 0, "PASS"), ("not_in", [0, 10], 0, "FAIL"),
    ("between", [10, 20], 10, "PASS"), ("between", [10, 20], 20, "PASS"),
    ("between", [10, 20], 9.99, "FAIL"), ("between", [10, 20], 20.01, "FAIL"),
])
def test_all_operators_and_inclusive_boundaries(op, expected, value, result):
    trace = evaluate(rule(op=op, value=expected), {"annual_family_income": value}, DAY)
    assert trace["result"] == result
    assert trace["value"] == value
    assert trace["expected"] == expected
    assert trace["source"] == "test://fixture"


@pytest.mark.parametrize("field,value", [("has_bank_account", False), ("student_status", False), ("annual_family_income", 0)])
def test_false_and_zero_are_known_values(field, value):
    assert evaluate(rule(field, "==", value), {field: value}, DAY)["result"] == "PASS"
    assert evaluate(rule(field, "==", value), {field: None}, DAY)["result"] == "UNKNOWN"


@pytest.mark.parametrize("kind,left,right", list(itertools.product(["all", "any"], ["PASS", "FAIL", "UNKNOWN"], ["PASS", "FAIL", "UNKNOWN"])))
def test_full_three_valued_group_truth_tables(kind, left, right):
    values = {"PASS": True, "FAIL": False, "UNKNOWN": None}
    tree = {kind: [rule("has_bank_account", "==", True), rule("student_status", "==", True)]}
    trace = evaluate(tree, {"has_bank_account": values[left], "student_status": values[right]}, DAY)
    states = [left, right]
    if kind == "all":
        expected = "FAIL" if "FAIL" in states else "PASS" if states == ["PASS", "PASS"] else "UNKNOWN"
    else:
        expected = "PASS" if "PASS" in states else "FAIL" if states == ["FAIL", "FAIL"] else "UNKNOWN"
    assert trace["result"] == expected
    assert len(trace["children"]) == 2
    if expected != "UNKNOWN":
        assert trace["missing_fields"] == []


def test_nested_or_unknown_unused_branch_does_not_block():
    tree = {"all": [rule("age", ">=", 18), {"any": [rule("student_status", "==", True), rule("employment_status", "==", "unemployed")]}]}
    profile = {"date_of_birth": "2000-01-01", "employment_status": "unemployed"}
    trace = evaluate(tree, profile, DAY)
    assert trace["result"] == "PASS"
    assert trace["missing_fields"] == []
    assert trace["children"][1]["children"][0]["result"] == "UNKNOWN"


def test_unknown_age_requests_birth_date_not_editable_age():
    assert evaluate(rule("age", ">=", 18), {}, DAY)["missing_fields"] == ["date_of_birth"]


@pytest.mark.parametrize("birthday,on,expected", [
    ("2008-09-20", date(2026, 9, 19), 17), ("2008-09-20", DAY, 18),
    ("2004-02-29", date(2025, 2, 28), 20), ("2004-02-29", date(2025, 3, 1), 21),
    ("2004-02-29", date(2024, 2, 29), 20),
])
def test_age_and_march_first_leap_day_policy(birthday, on, expected):
    assert age_on(birthday, on) == expected


def test_birth_after_evaluation_is_invalid():
    with pytest.raises(ValueError):
        evaluate(rule("age", ">=", 18), {"date_of_birth": "2020-01-01"}, date(2019, 1, 1))


@pytest.mark.parametrize("tree", [
    None, {}, [], {"all": []}, {"any": []}, {"all": [rule()], "any": [rule()]},
    {"all": [rule()], "field": "age"}, {"all": "bad"},
    {"field": "__import__", "op": "==", "value": "os"},
    rule(op="eval"), rule(value="200000"), rule(value=True),
    rule(op="between", value="10-20"), rule(op="between", value=[20, 10]),
    rule(op="between", value=[10, 20, 30]), rule(op="in", value=[]),
    rule("age", ">=", 18.0), rule("age", ">=", 131),
    rule("gender", "<", "female"), rule("has_bank_account", "==", 1),
    rule("student_status", "==", None), rule("state", "==", "Atlantis"),
    {"field": "age", "op": ">=", "value": 18, "source": ""},
    {"field": "age", "op": ">=", "value": 18, "unexpected": True},
])
def test_invalid_rules_are_configuration_errors(tree):
    with pytest.raises(ValueError):
        evaluate(tree, {}, DAY)


def test_rule_depth_and_group_size_are_bounded():
    tree = rule()
    for _ in range(22):
        tree = {"all": [tree]}
    with pytest.raises(ValueError):
        validate_rule(tree)
    with pytest.raises(ValueError):
        validate_rule({"all": [rule()] * 101})


def test_date_rules_are_typed_and_inclusive():
    tree = rule("date_of_birth", "between", ["2000-01-01", "2005-12-31"])
    assert evaluate(tree, {"date_of_birth": "2005-12-31"}, DAY)["result"] == "PASS"


@pytest.mark.parametrize("coverage", ["incomplete", "stale"])
def test_coverage_cannot_give_unqualified_eligibility(coverage):
    outcome = eligibility(scheme(coverage=coverage), {"annual_family_income": 1, "revision": 7}, DAY)
    assert outcome["status"] == "POTENTIALLY_ELIGIBLE"
    assert outcome["missing_information"] == ["scheme_rule_coverage"]
    assert outcome["rule_version"] == 3
    assert outcome["profile_revision"] == 7
    assert outcome["evaluation_date"] == "2026-09-20"
    assert eligibility(scheme(coverage=coverage), {"annual_family_income": 300000}, DAY)["status"] == "NOT_ELIGIBLE"


@pytest.mark.parametrize("key,value", [("valid_from", "2026-09-21"), ("valid_until", "2026-09-19")])
def test_outside_validity_requires_more_information(key, value):
    outcome = eligibility(scheme(**{key: value}), {"annual_family_income": 0}, DAY)
    assert outcome["status"] == "POTENTIALLY_ELIGIBLE"
    assert "scheme_validity" in outcome["missing_information"]


def test_recommendations_order_status_then_score_then_stable_id():
    values = [scheme(id="z"), scheme(id="a"), scheme(rule("student_status", "==", True), id="unknown"),
              scheme(rule(value=1), id="fail"), scheme(id="archived", active=False)]
    profile = {"annual_family_income": 100}
    result = recommendations(values, profile, on=DAY)
    assert [item["scheme_id"] for item in result] == ["a", "z", "unknown"]
    with_fail = recommendations(values, profile, include_ineligible=True, on=DAY)
    assert with_fail[-1]["scheme_id"] == "fail"
    assert all(0 <= item["score"] <= 100 for item in with_fail)
    assert recommendations([], {}, on=DAY) == []


def test_satisfied_or_branches_receive_identical_full_support():
    single = rule("has_bank_account", "==", True)
    alternative = {"any": [single, rule("student_status", "==", True)]}
    profile = {"has_bank_account": True, "student_status": False}
    result = recommendations([scheme(single, id="single"), scheme(alternative, id="or")], profile, on=DAY)
    assert result[0]["score"] == result[1]["score"] == 95
    assert all(item["eligibility"]["status"] == "ELIGIBLE" for item in result)


def test_readiness_zero_denominator_is_not_applicable():
    value = readiness(scheme(), {"annual_family_income": 0}, [], on=DAY)
    assert value["percentage"] is None
    assert value["status"] == "NOT_APPLICABLE"


def test_readiness_optional_items_do_not_reduce_percentage():
    value = readiness(scheme(required_fields=["annual_family_income"], required_documents=[group(mandatory=False)]),
                      {"annual_family_income": 0}, [], on=DAY)
    assert value["percentage"] == 100
    assert value["status"] == "READY"


def test_document_alternative_and_missing_checks():
    item = scheme(required_documents=[group()])
    profile = {"annual_family_income": 0, "full_name": "Asha Rao"}
    alternate = document(document_type="birth_certificate")
    assert readiness(item, profile, [alternate], on=DAY)["status"] == "READY"
    assert readiness(item, profile, [document(checks=[])], on=DAY)["status"] == "NEEDS_INFORMATION"
    assert readiness(item, profile, [document(fields={})], on=DAY)["status"] == "NEEDS_INFORMATION"


@pytest.mark.parametrize("status", ["NEEDS_OCR", "NEEDS_MANUAL_REVIEW", "FAILED", "PROCESSING", "UPLOADED"])
def test_unprocessed_documents_never_satisfy_a_content_requirement(status):
    value = readiness(scheme(required_documents=[group()]), {"annual_family_income": 0}, [document(status=status)], on=DAY)
    assert value["status"] == "NEEDS_INFORMATION"
    assert value["percentage"] == 0


def test_unknown_condition_blocks_and_false_condition_is_not_applicable():
    item = scheme(required_fields=["annual_family_income"], required_documents=[group(condition=rule("student_status", "==", True))])
    unknown = readiness(item, {"annual_family_income": 0}, [], on=DAY)
    assert unknown["status"] == "NEEDS_INFORMATION"
    assert unknown["percentage"] == 50
    false = readiness(item, {"annual_family_income": 0, "student_status": False}, [], on=DAY)
    assert false["status"] == "READY"
    assert false["percentage"] == 100


def test_complete_paperwork_does_not_override_ineligibility():
    value = readiness(scheme(required_fields=["annual_family_income"]), {"annual_family_income": 900000}, [], on=DAY)
    assert value["percentage"] == 100
    assert value["status"] == "NOT_ELIGIBLE"


def test_corrections_are_not_independently_verified_and_must_be_rechecked():
    item = scheme(required_documents=[group()])
    profile = {"annual_family_income": 0, "full_name": "Asha Rao"}
    correction = document("Wrong Person", "MISMATCH", corrections={"full_name": {"value": "Asha Rao", "confirmed": True}})
    assert readiness(item, profile, [correction], on=DAY)["status"] == "INCOMPLETE"
    correction["checks"][0]["status"] = "MATCH"
    value = readiness(item, profile, [correction], on=DAY)
    assert value["status"] == "READY"
    assert value["items"][0]["manual_confirmation"] is True
    assert "not independently verified" in value["items"][0]["evidence_label"]
    assert readiness(item, profile, [], on=DAY)["status"] == "INCOMPLETE"


def test_another_matching_document_does_not_hide_unresolved_mismatch():
    docs = [document(), document("Wrong Person", "MISMATCH", id="doc-b")]
    value = readiness(scheme(required_documents=[group()]), {"annual_family_income": 0, "full_name": "Asha Rao"}, docs, on=DAY)
    assert value["status"] == "INCOMPLETE"
    assert any(item["kind"] == "consistency" for item in value["items"])


def test_equivalent_checklist_items_deduplicate_with_mandatory_taking_precedence():
    item = scheme(required_fields=["annual_family_income", "annual_family_income"],
                  required_documents=[group(mandatory=False), group(id="duplicate", mandatory=True)])
    value = readiness(item, {"annual_family_income": 0}, [], on=DAY)
    assert value["applicable_mandatory"] == 2
    assert value["percentage"] == 50
    assert value["status"] == "INCOMPLETE"


@pytest.mark.parametrize("requirement", [group(any_of=[]), group(any_of="identity_proof"), group(fields=["bad"]), group(fields=[{}]), group(mandatory="yes")])
def test_invalid_document_requirements_raise_configuration_error(requirement):
    with pytest.raises(ValueError):
        readiness(scheme(required_documents=[requirement]), {}, [], on=DAY)


def test_seed_catalog_has_twelve_explicitly_fictional_valid_schemes():
    assert len(SCHEMES) == 12
    assert len({item["id"] for item in SCHEMES}) == 12
    for item in SCHEMES:
        assert item["is_fictional"] is True
        assert item["name"].startswith("Demo ")
        assert item["source"]["url"] is None
        assert item["source"]["retrieved_at"] is None
        assert item["source"]["reference"] == f"data/schemes.json#{item['id']}"
        assert "FICTIONAL" in item["source"]["passage"]
        assert validate_rule(item["rules"])


@pytest.mark.parametrize("citizen", CITIZENS, ids=lambda citizen: citizen["scenario"])
def test_five_independently_labeled_citizen_scenarios(citizen):
    expected = citizen["expected"]
    item = next(s for s in SCHEMES if s["id"] == expected["scheme_id"])
    profile = citizen["profile"]
    assert eligibility(item, profile, DAY)["status"] == expected["eligibility"]
    prepared = readiness(item, profile, citizen["documents"], on=DAY)
    assert prepared["status"] == expected["readiness"]
    assert prepared["percentage"] == expected["readiness_percentage"]
    for identifier, status in expected.get("additional_eligibility", {}).items():
        assert eligibility(next(s for s in SCHEMES if s["id"] == identifier), profile, DAY)["status"] == status
    if "after_income_correction" in expected:
        documents = copy.deepcopy(citizen["documents"])
        income = next(doc for doc in documents if doc["document_type"] == "income_certificate")
        income["corrections"] = {"annual_family_income": {"value": 150000, "confirmed": True}}
        next(check for check in income["checks"] if check["field"] == "annual_family_income")["status"] = "MATCH"
        corrected = readiness(item, profile, documents, on=DAY)
        assert corrected["status"] == "READY"
        assert corrected["percentage"] == 100


def test_evaluation_dataset_has_labeled_coverage_not_a_claim_of_execution():
    queries = json.loads((DATA / "evaluation.json").read_text(encoding="utf-8"))
    assert len(queries) >= 20
    assert {query["type"] for query in queries} == {"answerable", "unsupported", "prompt_injection", "personal_eligibility", "conflicting_evidence"}
    assert len({query["id"] for query in queries}) == len(queries)
    assert all(query["expected_behavior"] for query in queries)


def test_extreme_numeric_input_is_validation_error():
    with pytest.raises(ValueError):
        validate_profile({'annual_family_income': 10 ** 400})

"""Tests for OR (disjunction) in Euclid-IR rule bodies.

A rule body with ``OR`` is expanded into pure Horn rules at parse time
(``language._expand_or_rules``), so the solvers only ever see Horn clauses.
Semantics: ``AND`` binds tighter than ``OR``; parenthesized groups
``(a OR b)`` expand distributively. ``NOT`` over a group is rejected in v1.

Expansion happens inside ``language.parse``, so the Prolog and native
backends, ``check_kb``, ``explain``, ``diagnose`` and ``what_if`` all see the
same expanded clauses.
"""

import shutil

import pytest

from euclid_mcp.language import parse
from euclid_mcp.server import check_kb, explain, reason

# ── parse-time expansion to pure Horn clauses ────────────────────────────────


def test_simple_or_expands_to_two_rules():
    kb = parse(
        "human(socrates)\n"
        "mortal($x) IF human($x) OR hero($x)\n"
        "hero(achilles)"
    )
    assert kb.rules == [
        "mortal($x) if human($x)",
        "mortal($x) if hero($x)",
    ]


def test_and_binds_tighter_than_or():
    kb = parse("p($x) IF a($x) OR b($x) AND c($x)")
    assert kb.rules == [
        "p($x) if a($x)",
        "p($x) if b($x), c($x)",
    ]


def test_group_expands_distributively():
    kb = parse("p($x) IF (a($x) OR b($x)) AND c($x)")
    assert kb.rules == [
        "p($x) if a($x), c($x)",
        "p($x) if b($x), c($x)",
    ]


def test_group_in_middle_keeps_shared_conjuncts():
    kb = parse("p($x) IF a($x) AND (b($x) OR c($x)) AND d($x)")
    assert kb.rules == [
        "p($x) if a($x), b($x), d($x)",
        "p($x) if a($x), c($x), d($x)",
    ]


def test_two_groups_cartesian_product():
    kb = parse("p($x) IF (a($x) OR b($x)) AND (c($x) OR d($x))")
    assert kb.rules == [
        "p($x) if a($x), c($x)",
        "p($x) if a($x), d($x)",
        "p($x) if b($x), c($x)",
        "p($x) if b($x), d($x)",
    ]


def test_nested_group():
    kb = parse("p($x) IF a($x) OR (b($x) AND c($x))")
    assert kb.rules == [
        "p($x) if a($x)",
        "p($x) if b($x), c($x)",
    ]


def test_duplicate_or_branches_are_deduplicated():
    kb = parse("p($x) IF a($x) OR a($x)")
    assert kb.rules == ["p($x) if a($x)"]


def test_zero_arity_atoms():
    kb = parse("p IF rainy OR sunny")
    assert kb.rules == ["p if rainy", "p if sunny"]


def test_string_literals_with_or_and_and_are_not_split():
    kb = parse('p($x) IF name($x, "now or never") AND q($x)')
    assert kb.rules == ['p($x) if name($x, "now or never"), q($x)']


def test_atoms_containing_and_or_not_split():
    kb = parse("p($x) IF band($x) OR color($x)")
    assert kb.rules == [
        "p($x) if band($x)",
        "p($x) if color($x)",
    ]


# ── rule ids and provenance ──────────────────────────────────────────────────


def test_rule_id_propagates_to_every_expanded_branch():
    kb = parse("p($x) IF a($x) OR b($x)  # RULE: ACC-1")
    assert kb.rule_ids == {0: "ACC-1", 1: "ACC-1"}


def test_rule_sources_track_the_original_rule():
    kb = parse("p($x) IF a($x) OR b($x) OR c($x)\nq($x) IF d($x)")
    # first three indices come from source rule 0; the last from source rule 1
    assert kb.rule_sources == {0: 0, 1: 0, 2: 0, 3: 1}


def test_rules_without_or_pass_through_unchanged():
    kb = parse("p($x) IF a($x) AND b($x)")
    assert kb.rules == ["p($x) if a($x), b($x)"]
    assert kb.rule_sources == {0: 0}


# ── negation ─────────────────────────────────────────────────────────────────


def test_not_on_single_literal_survives_expansion():
    kb = parse("p($x) IF a($x) OR NOT b($x)")
    assert kb.rules == [
        "p($x) if a($x)",
        "p($x) if not b($x)",
    ]


def test_not_on_single_literal_inside_group():
    kb = parse("p($x) IF (a($x) OR b($x)) AND NOT c($x)")
    assert kb.rules == [
        "p($x) if a($x), not c($x)",
        "p($x) if b($x), not c($x)",
    ]


def test_not_over_group_is_rejected():
    with pytest.raises(ValueError, match="NOT over a parenthesized group"):
        parse("p($x) IF a($x) OR NOT (b($x) OR c($x))")


# ── multi-line OR continuation ───────────────────────────────────────────────


def test_trailing_or_continuation():
    kb = parse("p($x) IF a($x) OR\n    b($x)")
    assert kb.rules == [
        "p($x) if a($x)",
        "p($x) if b($x)",
    ]


def test_leading_or_continuation():
    kb = parse("p($x) IF a($x)\n    OR b($x)")
    assert kb.rules == [
        "p($x) if a($x)",
        "p($x) if b($x)",
    ]


def test_multiline_mixed_and_or():
    kb = parse(
        "can_access($u) IF\n"
        "    admin($u) OR\n"
        "    member($u) AND\n"
        "    active($u)"
    )
    assert kb.rules == [
        "can_access($u) if admin($u)",
        "can_access($u) if member($u), active($u)",
    ]


# ── YAML ────────────────────────────────────────────────────────────────────


def test_yaml_rule_with_or_expands():
    kb = parse(
        "rules:\n"
        "  - 'mortal($x) IF human($x) OR hero($x)'"
    )
    assert kb.rules == [
        "mortal($x) if human($x)",
        "mortal($x) if hero($x)",
    ]


# ── check_kb ────────────────────────────────────────────────────────────────


def test_check_kb_accepts_or_rule_without_duplicate_id_warning():
    c = check_kb(knowledge=(
        "admin(bob)\ndev(bob)\n"
        "p($x) IF admin($x) OR dev($x)  # RULE: ACC-1\n"
        "q($x) IF p($x)"
    ))
    assert c.valid is True
    assert c.errors == []
    assert [w.type for w in c.warnings] == []
    assert c.rules_count == 3  # expanded count


def test_check_kb_still_flags_distinct_sources_with_same_id():
    c = check_kb(knowledge=(
        "a(1)\nb(1)\n"
        "p($x) IF a($x)  # RULE: X\n"
        "q($x) IF b($x)  # RULE: X"
    ))
    assert c.valid is True
    assert [w.type for w in c.warnings] == ["duplicate_rule_id"]


def test_check_kb_reports_not_over_group_as_parse_error():
    c = check_kb(knowledge="p($x) IF a($x) OR NOT (b($x) OR c($x))")
    assert c.valid is False
    assert c.errors[0].type == "parse_error"
    assert "NOT over a parenthesized group" in c.errors[0].message


# ── backend parity: Prolog and native must agree ────────────────────────────


def _backends() -> list[str]:
    backends = ["native"]
    if shutil.which("swipl"):
        backends.append("prolog")
    return backends


@pytest.mark.parametrize("backend", _backends())
def test_parity_simple_or(backend, monkeypatch):
    monkeypatch.setenv("EUCLID_BACKEND", backend)
    res = reason(knowledge=(
        "human(socrates)\nhero(achilles)\n"
        "mortal($x) IF human($x) OR hero($x)\n"
        "? mortal($who)"
    ))
    assert res.error is None, f"{backend}: {res.error}"
    assert sorted(s.substitutions["who"] for s in res.solutions) == [
        "achilles", "socrates",
    ]
    assert all(s.proof.type == "rule" for s in res.solutions)


@pytest.mark.parametrize("backend", _backends())
def test_parity_group_with_not(backend, monkeypatch):
    monkeypatch.setenv("EUCLID_BACKEND", backend)
    res = reason(knowledge=(
        "a(1)\nb(2)\nc(3)\nd(4)\n"
        "p($x) IF (a($x) OR b($x)) AND NOT c($x)\n"
        "? p($x)"
    ))
    assert res.error is None, f"{backend}: {res.error}"
    assert [s.substitutions["x"] for s in res.solutions] == [1, 2]


@pytest.mark.parametrize("backend", _backends())
def test_parity_arithmetic_or(backend, monkeypatch):
    # Arithmetic conditions on the OR branches need a bound variable, so the
    # branch is reached through a domain fact (an unbound comparison is a
    # backend-error, exactly as without OR).
    monkeypatch.setenv("EUCLID_BACKEND", backend)
    res = reason(knowledge=(
        "num(1)\nnum(2)\nnum(3)\nnum(7)\n"
        "p($x) IF num($x) AND ($x > 5 OR $x < 2)\n"
        "? p($v)"
    ))
    assert res.error is None, f"{backend}: {res.error}"
    assert [s.substitutions["v"] for s in res.solutions] == [1, 7]


@pytest.mark.parametrize("backend", _backends())
def test_parity_expanded_rule_id_in_proofs(backend, monkeypatch):
    monkeypatch.setenv("EUCLID_BACKEND", backend)
    res = reason(knowledge=(
        "admin(bob)\ndev(bob)\n"
        "p($x) IF admin($x) OR dev($x)  # RULE: ACC-1\n"
        "? p($who)"
    ))
    assert res.error is None, f"{backend}: {res.error}"
    assert all(s.proof.rule_id == "ACC-1" for s in res.solutions)


# ── explain and what_if over OR rules ───────────────────────────────────────


def test_explain_cites_the_expanded_rule_id_on_every_branch():
    e = explain(
        knowledge=(
            "human(socrates)\nhero(achilles)\n"
            "mortal($x) IF human($x) OR hero($x)  # RULE: M-1"
        ),
        query="mortal($who)",
    )
    cited = [
        step.rule_id
        for ex in e.explanations
        for step in ex.structured_steps
        if step.rule_id
    ]
    assert cited == ["M-1", "M-1"]


def test_what_if_works_with_or_rules(monkeypatch):
    monkeypatch.setenv("EUCLID_BACKEND", "native")
    from euclid_mcp.server import what_if

    scenario = what_if(
        base_knowledge="human(socrates)\nmortal($x) IF human($x) OR hero($x)\n? mortal($who)",
        modifications="+ hero(achilles)",
        query="mortal($who)",
    )
    assert scenario.error is None
    assert scenario.before_count == 1
    assert scenario.after_count == 2
    assert scenario.delta == "more"


def test_what_if_without_or_branch_still_counts():
    from euclid_mcp.server import what_if

    scenario = what_if(
        base_knowledge="human(socrates)\nmortal($x) IF human($x) OR hero($x)\n? mortal($who)",
        modifications="+ human(plato)",
        query="mortal($who)",
    )
    assert scenario.error is None
    assert scenario.before_count == 1
    assert scenario.after_count == 2

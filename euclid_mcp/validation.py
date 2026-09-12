"""KB validation logic — shared by MCP server and LSP server.

Extracted from ``server.py`` so both entry points use the same code.
"""

from __future__ import annotations

import re
import time
from typing import Any

from euclid_mcp.engine import kb_fingerprint
from euclid_mcp.ir_parser import VarCounter, parse_goals, parse_term
from euclid_mcp.language import parse
from euclid_mcp.linter import lint_rule
from euclid_mcp.models import KBCheckResult, KBError, PredicateInfo

_IF_SPLIT = re.compile(r"\s+IF\s+", re.IGNORECASE)


def _split_rule(rule: str) -> tuple[str, str]:
    """Split a rule into head and body on 'IF' (case-insensitive)."""
    parts = _IF_SPLIT.split(rule, maxsplit=1)
    return (parts[0], parts[1]) if len(parts) == 2 else (parts[0], "")


def _is_not_goal(goal: str) -> bool:
    """Check if a goal is a NOT-prefixed negation (case-insensitive)."""
    return goal.strip().upper().startswith("NOT ")


def _extract_predicate(text: str) -> tuple[str, str] | None:
    """Extract predicate name and args from a term like 'parent(tom, bob)'."""
    text = text.strip()
    match = re.match(r"([^\W\d_]\w*)\s*\((.*)\)\s*$", text)
    if match:
        return match.group(1), match.group(2)
    # Zero-arity fact
    match = re.match(r"([^\W\d_]\w*)\s*$", text)
    if match:
        return match.group(1), ""
    return None


def _arity(args: str) -> int:
    """Arity of a predicate argument string: top-level commas + 1.

    Commas inside nested parentheses or quoted strings don't count, so
    nested compound arguments (e.g. ``cfg(run, tape(cell(1, blank)))``)
    and string literals containing commas report the correct arity.
    """
    if not args.strip():
        return 0
    depth = 0
    quote: str | None = None
    commas = 0
    for ch in args:
        if quote is not None:
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            commas += 1
    return commas + 1


def _split_conjunction(body: str) -> list[str]:
    """Split a rule body on AND, respecting parentheses."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    if current:
        tail = "".join(current).strip()
        if tail:
            parts.append(tail)
    return parts


def _body_predicates(body: str) -> set[str]:
    """Extract predicate names referenced in a rule body."""
    preds: set[str] = set()
    for goal in _split_conjunction(body):
        goal = goal.strip()
        if _is_not_goal(goal):
            goal = goal[4:].strip()
        parsed = _extract_predicate(goal)
        if parsed:
            preds.add(parsed[0])
    return preds


def run_check_kb(knowledge: str) -> KBCheckResult:
    """Core KB validation, independent of the MCP server.

    Returns a ``KBCheckResult`` with errors, warnings, and predicate inventory.
    Shared by both the MCP ``check_kb`` tool and the LSP diagnostics provider.
    """
    start = time.monotonic()
    errors: list[KBError] = []
    warnings: list[KBError] = []

    # Parse the KB
    try:
        kb = parse(knowledge)
    except Exception as exc:
        return KBCheckResult(
            valid=False,
            errors=[KBError(type="parse_error", message=str(exc))],
            elapsed_ms=(time.monotonic() - start) * 1000,
            content_hash=kb_fingerprint(knowledge),
            version=None,
        )

    # Collect all defined predicates
    predicates: dict[str, dict[str, Any]] = {}

    def _add_predicate(name: str, arity: int, kind: str) -> None:
        entry = predicates.setdefault(
            name, {"arities": set(), "facts": 0, "rules": 0}
        )
        entry["arities"].add(arity)
        entry[kind] += 1

    for fact in kb.facts:
        parsed = _extract_predicate(fact)
        if parsed:
            name, args = parsed
            arity = _arity(args)
            _add_predicate(name, arity, "facts")

    for rule in kb.rules:
        head, _ = _split_rule(rule)
        parsed = _extract_predicate(head.strip())
        if parsed:
            name, args = parsed
            arity = _arity(args)
            _add_predicate(name, arity, "rules")

    defined: dict[str, set[int]] = {
        name: entry["arities"] for name, entry in predicates.items()
    }

    # Check 1: engine-parseable statements. language.parse is deliberately
    # line-lenient, but both inference backends re-parse every fact and
    # rule with the strict term parser — a statement they reject would turn
    # a green :check into a runtime engine error. Validate against the same
    # parser so a green check guarantees the KB runs on either backend.
    counter = VarCounter()
    try:
        for fact in kb.facts:
            parse_term(fact, counter)
        for rule in kb.rules:
            head, body = _split_rule(rule)
            parse_term(head.strip(), counter)
            parse_goals(body, counter)
        if kb.query:
            parse_goals(kb.query, counter)
    except ValueError as exc:
        errors.append(KBError(type="parse_error", message=str(exc)))

    # Check 2: duplicate facts
    seen_facts: dict[str, int] = {}
    for fact in kb.facts:
        normalized = fact.strip().rstrip(".")
        if normalized in seen_facts:
            warnings.append(KBError(
                type="duplicate_fact",
                message=f"Duplicate fact: {normalized}",
                predicate=normalized.split("(")[0] if "(" in normalized else normalized,
            ))
        seen_facts[normalized] = seen_facts.get(normalized, 0) + 1

    # Check 3: undefined predicates in rule bodies
    for rule in kb.rules:
        _, body = _split_rule(rule)
        body_goals = _split_conjunction(body)

        for goal in body_goals:
            goal = goal.strip()
            if _is_not_goal(goal):
                goal = goal[4:].strip()

            goal_pred = _extract_predicate(goal)
            if goal_pred:
                goal_name, goal_args = goal_pred
                if goal_name.startswith("$") or goal_name in (
                    "true", "false", "is", ">", ">=", "<", "<=", "=<", "==", "=\\=", "!="
                ):
                    continue
                goal_arity = _arity(goal_args)
                if goal_name not in defined:
                    errors.append(KBError(
                        type="undefined_predicate",
                        message=(
                            "Rule body references undefined predicate "
                            f"'{goal_name}/{goal_arity}'"
                        ),
                        predicate=f"{goal_name}/{goal_arity}",
                    ))

    # Check 4: circular rules
    rule_heads: dict[str, list[str]] = {}
    for rule in kb.rules:
        head, _ = _split_rule(rule)
        parsed = _extract_predicate(head.strip())
        if parsed:
            name, _ = parsed
            rule_heads.setdefault(name, []).append(rule)

    # Facts count as base cases too: e.g. a reachability predicate may have
    # a variable-bearing fact (final(cfg(done, $t), cfg(done, $t))) plus a
    # single recursive rule.
    fact_names = {
        parsed[0]
        for fact in kb.facts
        if (parsed := _extract_predicate(fact.strip().rstrip(".")))
    }

    for pred_name, rules in rule_heads.items():
        for rule in rules:
            _, body = _split_rule(rule)
            if pred_name in _body_predicates(body):
                has_base = pred_name in fact_names or any(
                    pred_name not in _body_predicates(_split_rule(r)[1])
                    for r in rules
                )
                if not has_base:
                    errors.append(KBError(
                        type="circular_rule",
                        message=f"Recursive rule for '{pred_name}' without base case",
                        predicate=pred_name,
                    ))

    # Check 5: query referenced but not defined
    if kb.query:
        query_pred = _extract_predicate(kb.query)
        if query_pred:
            name, args = query_pred
            if name not in defined:
                errors.append(KBError(
                    type="undefined_predicate",
                    message=f"Query references undefined predicate '{name}'",
                    predicate=name,
                ))

    # Check 6: unsafe negation
    for rule in kb.rules:
        lint_warnings = lint_rule(rule)
        for w in lint_warnings:
            warnings.append(KBError(type="unsafe_negation", message=w))

    # Check 7: duplicate rule IDs. A single source rule with an OR expands into
    # sibling rules sharing one ID (kb.rule_sources records the origin), so
    # only an ID shared by rules with DIFFERENT origins is a real duplicate.
    seen_rule_ids: dict[str, int] = {}
    for idx, rule in enumerate(kb.rules):
        rid = kb.rule_ids.get(idx)
        if not rid:
            continue
        origin = kb.rule_sources.get(idx, idx)
        prev_origin = seen_rule_ids.get(rid)
        if prev_origin is not None and prev_origin != origin:
            warnings.append(KBError(
                type="duplicate_rule_id",
                message=f"Duplicate rule ID: {rid}",
                predicate=rid,
            ))
        else:
            seen_rule_ids[rid] = origin

    # Check 8: inconsistent arity
    predicate_infos: list[PredicateInfo] = []
    for name in sorted(predicates):
        entry = predicates[name]
        arities = sorted(entry["arities"])
        if len(arities) > 1:
            warnings.append(KBError(
                type="inconsistent_arity",
                message=(
                    f"Predicate '{name}' used with multiple arities: "
                    + ", ".join(str(a) for a in arities)
                ),
                predicate=name,
            ))
        predicate_infos.append(PredicateInfo(
            name=name,
            arities=arities,
            facts=entry["facts"],
            rules=entry["rules"],
        ))

    valid = len(errors) == 0

    elapsed = (time.monotonic() - start) * 1000
    return KBCheckResult(
        valid=valid,
        errors=errors,
        warnings=warnings,
        facts_count=len(kb.facts),
        rules_count=len(kb.rules),
        predicates_count=len(predicates),
        predicates=predicate_infos,
        elapsed_ms=elapsed,
        content_hash=kb_fingerprint(knowledge),
        version=kb.version,
    )

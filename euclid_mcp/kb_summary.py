"""Generic knowledge-base digest for the MCP server instructions.

Builds a compact markdown summary (fact/rule/predicate counts, predicate
inventory with arities, rules with their IDs) so an agent that connects to a
server with a preloaded KB (EUCLID_KB_PATH) can see what it may reason about
without extra tool calls.

This digest is intentionally generic — example 10 keeps its specialized
markdown (examples/10_llm_vs_euclid/kb_utils.py).
"""

import re

from .language import parse
from .validation import _arity

# Predicate name: a letter (Unicode-aware) followed by word characters.
_PREDICATE_RE = re.compile(r"([^\W\d_]\w*)\s*(?:\((.*)\))?\s*$", re.UNICODE)


def _split_predicate(term: str) -> tuple[str, int] | None:
    """Return (name, arity) for a term like 'parent(tom, bob)' or 'rainy'."""
    match = _PREDICATE_RE.match(term.strip())
    if not match:
        return None
    name, args = match.group(1), match.group(2)
    arity = _arity(args) if args is not None else 0
    return name, arity


def _rule_head(rule: str) -> str:
    """Return the head of a rule, e.g. 'ancestor($x, $y) IF parent(...)' → head."""
    return re.split(r"\s+if\s+", rule, maxsplit=1, flags=re.IGNORECASE)[0].strip()


def _display_rule(rule: str) -> str:
    """Humanize the canonical rule form: 'if' → IF, ',' → AND (depth-aware)."""
    parts = re.split(r"\s+if\s+", rule, maxsplit=1, flags=re.IGNORECASE)
    head = parts[0].strip()
    if len(parts) == 1:
        return head
    body = parts[1].strip()
    depth = 0
    conjuncts: list[str] = []
    current: list[str] = []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            conjuncts.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    conjuncts.append("".join(current).strip())
    return f"{head} IF " + " AND ".join(c for c in conjuncts if c)


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    """Return '1 fact' / '2 facts'."""
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def build_kb_summary(knowledge: str) -> str:
    """Return a compact markdown digest of a Euclid-IR knowledge base."""
    kb = parse(knowledge)

    # name -> {"facts": int, "rules": int, "arities": set[int]}
    predicates: dict[str, dict] = {}
    for fact in kb.facts:
        parsed = _split_predicate(fact)
        if parsed:
            name, arity = parsed
            entry = predicates.setdefault(name, {"facts": 0, "rules": 0, "arities": set()})
            entry["facts"] += 1
            entry["arities"].add(arity)
    for rule in kb.rules:
        parsed = _split_predicate(_rule_head(rule))
        if parsed:
            name, arity = parsed
            entry = predicates.setdefault(name, {"facts": 0, "rules": 0, "arities": set()})
            entry["rules"] += 1
            entry["arities"].add(arity)

    lines: list[str] = []
    lines.append("## Preloaded Knowledge Base")
    lines.append("")
    lines.append(
        f"Statistics: {_plural(len(kb.facts), 'fact')}, "
        f"{_plural(len(kb.rules), 'rule')}, "
        f"{_plural(len(predicates), 'predicate')}."
    )
    lines.append("")
    lines.append("Predicates (name/arity: facts, rules):")
    for name in sorted(predicates):
        entry = predicates[name]
        arities = "/".join(str(a) for a in sorted(entry["arities"])) or "?"
        lines.append(
            f"- {name}/{arities}: {entry['facts']} facts, {entry['rules']} rules"
        )
    lines.append("")

    if kb.rules:
        lines.append("Rules:")
        shown_origins: set[int] = set()
        for idx, rule in enumerate(kb.rules):
            display = _display_rule(rule)
            rule_id = kb.rule_ids.get(idx)
            origin = kb.rule_sources.get(idx, idx)
            if rule_id and origin not in shown_origins:
                display = f"{display}  # rule: {rule_id}"
                shown_origins.add(origin)
            lines.append(f"- {display}")
        lines.append("")

    if kb.query:
        lines.append(f"Query: {kb.query}")
        lines.append("")

    return "\n".join(lines).rstrip()

"""Positioned parser: wraps ``euclid_mcp.language.parse`` to track line/column."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from euclid_mcp.language import (
    _TRAILING_AND_OR,
    VERSION_PATTERN,
    _extract_rule_id,
    _extract_strings,
    _fold_ascii,
    _split_body,
)


@dataclass
class LocatedItem:
    """A fact, rule, or query with source location."""
    kind: str  # "fact" | "rule" | "query" | "version" | "comment"
    text: str
    start_line: int  # 0-based
    start_col: int  # 0-based
    end_line: int  # 0-based (inclusive)
    end_col: int  # 0-based (exclusive on that line)
    rule_id: Optional[str] = None
    head: Optional[str] = None  # for rules: the head predicate
    body_goals: list[str] = field(default_factory=list)  # for rules: body goals


@dataclass
class PositionedKB:
    """Parsed knowledge base with source locations for every item."""
    items: list[LocatedItem] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    query: Optional[str] = None
    version: Optional[str] = None
    rule_ids: dict[int, str] = field(default_factory=dict)
    errors: list[dict] = field(default_factory=list)  # parse-time errors


def parse_positioned(text: str) -> PositionedKB:
    """Parse a Euclid-IR document and track source locations for each item.

    Returns a PositionedKB with both the normalized KB (for validation)
    and located items (for LSP features like go-to-definition, hover).
    """
    text_stripped = text.strip()
    kb = PositionedKB()
    if not text_stripped:
        return kb

    lines = text.split("\n")
    i = 0
    facts: list[str] = []
    rules: list[str] = []
    rule_ids: dict[int, str] = {}
    query: Optional[str] = None
    version: Optional[str] = None

    while i < len(lines):
        raw_line = lines[i]
        start_line = i
        start_col = 0

        # Extract strings before stripping comments
        raw_line_cleaned, line_strings = _extract_strings(raw_line)
        rule_id = _extract_rule_id(raw_line_cleaned)

        # Strip comments
        line = re.sub(r"(?<!\S)\s*(#|//|%).*$", "", raw_line_cleaned).strip()
        i += 1

        if not line:
            continue

        # Version directive
        m = VERSION_PATTERN.match(line)
        if m:
            version = m.group(1)
            kb.items.append(LocatedItem(
                kind="version",
                text=raw_line.strip(),
                start_line=start_line,
                start_col=start_col,
                end_line=start_line,
                end_col=len(raw_line),
            ))
            continue

        # Find end line for multi-line constructs
        end_line = start_line
        line_r = _fold_ascii(line.rstrip("."))

        if line_r.startswith("?"):
            # Query
            q_text = _fold_ascii(line_r.lstrip("? ").strip())
            from euclid_mcp.language import _restore_strings
            q_text = _restore_strings(q_text, line_strings)
            query = q_text
            kb.items.append(LocatedItem(
                kind="query",
                text=q_text,
                start_line=start_line,
                start_col=start_col,
                end_line=start_line,
                end_col=len(raw_line),
            ))
        elif " if " in line_r or line_r.endswith(" if"):
            # Rule — may be multi-line
            if " if " in line_r:
                head_str, body_str = line_r.split(" if ", 1)
            else:
                head_str = line_r[:-3]
                body_str = ""
            body_str = body_str.strip()

            # Multi-line continuation
            while body_str == "" or _TRAILING_AND_OR.search(body_str):
                if i >= len(lines):
                    break
                next_raw = lines[i]
                next_raw_cleaned, next_strings = _extract_strings(next_raw)
                line_strings.extend(next_strings)
                next_rule_id = _extract_rule_id(next_raw_cleaned)
                if next_rule_id:
                    rule_id = next_rule_id
                next_line = re.sub(r"(?<!\S)\s*(#|//|%).*$", "", next_raw_cleaned).strip()
                i += 1
                end_line = i - 1
                if not next_line:
                    continue
                next_line = _fold_ascii(next_line.rstrip("."))
                if body_str == "":
                    body_str = next_line
                elif body_str.endswith("and"):
                    body_str = body_str + " " + next_line
                else:
                    body_str = body_str + " " + next_line

            body_goals = []
            for branch in _split_body(body_str, is_or=True):
                body_goals.extend(_split_body(branch, is_or=False))
            body_goals = [p for p in body_goals if p.strip()]

            rule_text = _fold_ascii(f"{head_str.strip()} if {body_str}")
            from euclid_mcp.language import _restore_strings
            rule_text = _restore_strings(rule_text, line_strings)

            rule_index = len(rules)
            rules.append(rule_text)
            if rule_id:
                rule_ids[rule_index] = rule_id

            kb.items.append(LocatedItem(
                kind="rule",
                text=rule_text,
                start_line=start_line,
                start_col=start_col,
                end_line=end_line,
                end_col=len(lines[end_line]) if end_line < len(lines) else 0,
                rule_id=rule_id,
                head=head_str.strip(),
                body_goals=body_goals,
            ))
        else:
            # Fact
            fact_text = _fold_ascii(line_r)
            from euclid_mcp.language import _restore_strings
            fact_text = _restore_strings(fact_text, line_strings)
            facts.append(fact_text)
            kb.items.append(LocatedItem(
                kind="fact",
                text=fact_text,
                start_line=start_line,
                start_col=start_col,
                end_line=start_line,
                end_col=len(raw_line),
            ))

    kb.facts = facts
    kb.rules = rules
    kb.query = query
    kb.version = version
    kb.rule_ids = rule_ids
    return kb

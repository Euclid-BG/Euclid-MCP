import re
import unicodedata

from .models import KB
from .sanitizer import sanitize

VERSION_PATTERN = re.compile(r"^@version\s+(\d+\.\d+)", re.IGNORECASE)

# Trailing comment reserved for rule IDs:  # rule: <id>
_RULE_ID_PATTERN = re.compile(r"(?<!\S)\s*#\s*rule:\s*(.+?)\s*$", re.IGNORECASE)

# Variable names: "$" + one Unicode letter, then Unicode letters/digits/
# underscores — e.g. $x, $città, $кто. Single source of truth shared by the
# native parser (ir_parser), the Prolog translator and the linter, so all
# three agree on what a variable is regardless of script or accents.
VAR_NAME_RE = re.compile(r"\$([^\W\d_]\w*)", re.UNICODE)

# Continuation markers for multi-line rule bodies: a piece that ends with a
# bare ` and`/` or` (trailing style), or a next line that opens with
# `and`/`or` (leading style). Word boundaries keep predicates like `band` or
# `color` from being misread as continuation markers.
_TRAILING_AND_OR = re.compile(r"\s+(?:and|or)$")
_LEADING_AND_OR = re.compile(r"(?:and|or)(?:\s|$)")

_RESERVED_KEYWORDS = {"if", "and", "or", "not", "is", "true", "false"}


def _fold_ascii(s: str) -> str:
    """Lowercase ASCII A-Z only; leave non-ASCII letters untouched.

    Preserves the __STR_N__ placeholders used for quoted strings so they
    survive case folding (kept uppercase for _restore_strings).
    """
    folded = "".join(c.lower() if "A" <= c <= "Z" else c for c in s)
    return re.sub(r"__str_(\d+)__", lambda m: f"__STR_{m.group(1)}__", folded)


# Regex for quoted strings (double or single quote, with escape support)
_STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'')


def _extract_strings(text: str) -> tuple[str, list[str]]:
    """Extract quoted strings, replace with placeholders, return mapping."""
    strings: list[str] = []
    def _replace(m: re.Match) -> str:
        strings.append(m.group(0))
        return f"__STR_{len(strings) - 1}__"
    cleaned = _STRING_RE.sub(_replace, text)
    return cleaned, strings


def _restore_strings(text: str, strings: list[str]) -> str:
    """Restore quoted strings from placeholders."""
    for i, s in enumerate(strings):
        text = text.replace(f"__STR_{i}__", s)
    return text


def strip_query_prefix(text: str) -> str:
    """Strip the optional ``?`` / ``?-`` query prefix and surrounding whitespace.

    Query lines inside a KB text carry a leading ``?`` (stripped by the
    parser), but the same documented prefix is also accepted on the
    ``query`` parameter of the tools, CLI, and HTTP API; the engines
    need the bare goal, so normalize at every entry point.

    The result is also NFC-normalized: queries may arrive from clients that
    emit decomposed (NFD) spellings, and the two backends must see byte
    identical atoms to unify them symmetrically.
    """
    normalized = text.strip()
    if normalized.startswith("?-"):
        normalized = normalized[2:]
    elif normalized.startswith("?"):
        normalized = normalized[1:]
    return unicodedata.normalize("NFC", normalized.strip())


def _normalize_term(term: str) -> str:
    """Normalize identifiers in a term to lowercase.

    Preserves $variables, quoted strings, numbers, and raises on
    reserved keywords used as predicate names.
    """
    cleaned, strings = _extract_strings(term)
    result = _fold_ascii(cleaned)
    for i, s in enumerate(strings):
        result = result.replace(f"__STR_{i}__", s)
    return result


def _validate_no_keywords(term: str) -> None:
    """Check that predicate names are not reserved keywords."""
    m = re.match(r"([^\W\d_]\w*)\s*\(", term.strip())
    if m and m.group(1) in _RESERVED_KEYWORDS:
        raise ValueError(
            f"Reserved keyword '{m.group(1)}' cannot be used as predicate name"
        )


def _validate_no_bare_literal(statement: str, kind: str) -> None:
    """Reject a bare ``true``/``false`` used as a fact or rule head.

    The two words are boolean literals for rule bodies; as standalone
    statements they are meaningless and would break the Prolog backend
    (asserting a clause over a built-in). Vocabulary declarations for
    expected-input predicates use ``pred($x) IF false`` instead.
    """
    stripped = statement.strip()
    if stripped in ("true", "false"):
        raise ValueError(
            f"Reserved keyword '{stripped}' cannot be used as {kind}; "
            "use it only inside a rule body (e.g. 'pred($x) IF false')"
        )


def parse(text: str) -> KB:
    text = text.strip()
    if not text:
        return KB()

    # Canonical equivalence: normalize decomposed (NFD) spellings to NFC so
    # identifiers unify symmetrically on every backend (SWI-Prolog compares
    # raw code points; the native tokenizer rejects combining marks).
    text = unicodedata.normalize("NFC", text)

    # Security: reject dangerous Prolog patterns before parsing
    sanitize(text)

    version = _extract_version(text)
    if _is_yaml(text):
        kb = _parse_yaml(text)
        kb.version = version
        _normalize_kb(kb)
        _expand_or_rules(kb)
        return kb
    kb = _parse_text(text)
    kb.version = version
    _normalize_kb(kb)
    _expand_or_rules(kb)
    return kb


def _extract_version(text: str) -> str | None:
    """Extract @version directive from the first line(s)."""
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # Skip comments (#, //, %)
        if stripped.startswith(("#", "//", "%")):
            continue
        m = VERSION_PATTERN.match(stripped)
        if m:
            return m.group(1)
        # First non-comment, non-empty line is not @version
        break
    return None


def _is_yaml(text: str) -> bool:
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("---"):
        return True
    # Skip @version line for YAML detection
    lines = text.split("\n")
    for line in lines:
        s = line.strip()
        if not s or s.startswith(("#", "//", "%")):
            continue
        if VERSION_PATTERN.match(s):
            continue
        stripped = s
        break
    if stripped.startswith("{") or stripped.startswith("---"):
        return True
    try:
        import yaml
        data = yaml.safe_load(text)
        if isinstance(data, dict):
            keys = {_fold_ascii(k) for k in data}
            if keys & {"facts", "rules", "query"}:
                return True
    except Exception:
        pass
    return False


def _parse_yaml(text: str) -> KB:
    import yaml
    # Strip @version line before YAML parsing
    lines = text.split("\n")
    filtered = []
    for line in lines:
        if VERSION_PATTERN.match(line.strip()):
            continue
        filtered.append(line)
    data = yaml.safe_load("\n".join(filtered))
    if not isinstance(data, dict):
        return _parse_text(text)

    facts = _ensure_list(data.get("facts", []))
    rules = _ensure_list(data.get("rules", []))
    query = data.get("query")
    if isinstance(query, str):
        query = query.strip().rstrip(".")
    # Re-scan the parsed statements: YAML string values were masked by the
    # raw-text sanitize() above, so a real directive can only be caught here.
    for stmt in facts + rules:
        sanitize(stmt)
    if query:
        sanitize(query)
    return KB(facts=facts, rules=rules, query=query)


def _extract_rule_id(raw_line: str) -> str | None:
    """Extract a rule ID from a trailing `# rule: <id>` comment.

    Case-preserving (like string literals); returns None when the line has
    no reserved `# rule:` comment. Applied to the raw line after string
    extraction and before lowercasing.
    """
    m = _RULE_ID_PATTERN.search(raw_line)
    return m.group(1) if m else None


def _strip_statement_line(raw: str) -> tuple[str, list[str], str | None]:
    """Comment-strip, fold and rule-id-extract one raw source line.

    Returns ``(line, strings, rule_id)``; ``line`` is ``""`` for blank or
    comment-only lines. Shared by the statement loop and the rule-body
    continuation logic so both treat source lines identically.
    """
    raw, strings = _extract_strings(raw)
    rule_id = _extract_rule_id(raw)
    line = re.sub(r"(?<!\S)\s*(#|//|%).*$", "", raw).strip()
    if not line:
        return "", strings, rule_id
    return _fold_ascii(line.rstrip(".")), strings, rule_id


def _parse_text(text: str) -> KB:
    facts: list[str] = []
    rules: list[str] = []
    rule_ids: dict[int, str] = {}
    query: str | None = None

    lines = text.split("\n")
    idx = 0

    def next_line() -> tuple[str | None, list[str], str | None]:
        """Next meaningful (non-blank) processed line, or None at EOF."""
        nonlocal idx
        while idx < len(lines):
            line, strings, rid = _strip_statement_line(lines[idx])
            idx += 1
            if line:
                return line, strings, rid
        return None, [], None

    while True:
        line, line_strings, rule_id = next_line()
        if line is None:
            break
        # Skip @version directive
        if VERSION_PATTERN.match(line):
            continue

        if line.startswith("?"):
            if rule_id:
                raise ValueError(
                    "`# rule:` is not allowed on a query. "
                    "It applies only to rules."
                )
            query = _restore_strings(line.lstrip("? ").strip(), line_strings)
        elif " if " in line or line.endswith(" if"):
            if " if " in line:
                head, body_str = line.split(" if ", 1)
            else:
                head = line[:-3]  # Remove trailing " if"
                body_str = ""
            body_str = body_str.strip()
            # Multi-line rule bodies. A line is a continuation when the
            # body so far is empty or ends with `and`/`or` (trailing
            # style), or when the NEXT meaningful line opens with
            # `and`/`or` (leading style — the common Prolog habit):
            #
            #     p($x) IF $x > 0
            #           AND $y is $x - 1
            #           OR $z is $x
            #
            # A non-continuation line is pushed back for the main loop.
            pieces: list[str] = [body_str] if body_str else []
            while True:
                if not pieces or _TRAILING_AND_OR.search(pieces[-1]):
                    nxt, nxt_strings, nxt_rid = next_line()
                    if nxt is None:
                        break
                    line_strings.extend(nxt_strings)
                    if nxt_rid:
                        rule_id = nxt_rid  # last body line wins
                    pieces.append(nxt)
                    continue
                mark = idx
                nxt, nxt_strings, nxt_rid = next_line()
                if nxt is not None and _LEADING_AND_OR.match(nxt):
                    line_strings.extend(nxt_strings)
                    if nxt_rid:
                        rule_id = nxt_rid
                    pieces.append(nxt)
                    continue
                idx = mark  # not a continuation: unread it
                break
            body_parts = re.split(r"\s+and\s+", " ".join(pieces))
            body = ", ".join(p.strip() for p in body_parts)
            rule_index = len(rules)
            rules.append(_restore_strings(f"{head.strip()} if {body}", line_strings))
            if rule_id:
                rule_ids[rule_index] = rule_id
        else:
            if rule_id:
                raise ValueError(
                    "`# rule:` is not allowed on a fact. "
                    "It applies only to rules."
                )
            if line == "and" or line.startswith("and ") or line == "or" or line.startswith("or "):
                raise ValueError(
                    "Statement starts with 'and'/'or': continuation lines belong "
                    "to a rule written above them."
                )
            facts.append(_restore_strings(line, line_strings))

    return KB(facts=facts, rules=rules, query=query, rule_ids=rule_ids)


def _normalize_kb(kb: KB) -> KB:
    """Normalize all identifiers in a KB to lowercase."""
    kb.facts = [_normalize_term(f) for f in kb.facts]
    kb.rules = [_normalize_term(r) for r in kb.rules]
    if kb.query:
        kb.query = _normalize_term(kb.query)
    for f in kb.facts:
        _validate_no_keywords(f)
        _validate_no_bare_literal(f, "a fact")
    for r in kb.rules:
        head = re.split(r"\s+if\s+", r, maxsplit=1)[0].strip()
        _validate_no_keywords(head)
        _validate_no_bare_literal(head, "a rule head")
    if kb.query:
        _validate_no_keywords(kb.query)
    return kb


# ── OR (disjunction) expansion ───────────────────────────────────────────────

# Splits a rule body on ``IF`` (case-insensitive), mirroring the backends.
_IF_RE = re.compile(r"\s+if\s+", re.IGNORECASE)


def _split_body(text: str, *, is_or: bool) -> list[str]:
    """Split a rule body on top-level ``or`` (is_or=True) or ``and``/``,``
    (is_or=False) separators.

    Parens and quoted strings are tracked, so separators inside
    ``parent(ann, "Adams, and the rest")`` or grouped ``(a OR b)`` never
    split. ``and``/``or`` only act as separators at word boundaries (whitespace
    around), so atoms like ``band`` or ``color`` are left intact.
    """
    word = "or" if is_or else "and"
    parts: list[str] = []
    cur: list[str] = []
    depth = 0
    in_str: str | None = None
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if in_str is not None:
            cur.append(ch)
            if ch == "\\" and i + 1 < n:
                cur.append(text[i + 1])
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in "\"'":
            in_str = ch
            cur.append(ch)
            i += 1
            continue
        if ch == "(":
            depth += 1
            cur.append(ch)
            i += 1
            continue
        if ch == ")":
            depth -= 1
            cur.append(ch)
            i += 1
            continue
        if depth == 0:
            if ch == "," and not is_or:
                parts.append("".join(cur).strip())
                cur = []
                i += 1
                continue
            if text[i : i + len(word)].lower() == word:
                # word separator: whitespace before and after (or line ends)
                before_ok = (not cur) or cur[-1].isspace()
                after = i + len(word)
                after_ok = after >= n or text[after].isspace()
                if before_ok and after_ok:
                    parts.append("".join(cur).strip())
                    cur = []
                    i = after
                    continue
        cur.append(ch)
        i += 1
    if cur:
        parts.append("".join(cur).strip())
    return [p for p in parts if p]


def _unwrap_group(seg: str) -> str | None:
    """Inner text when ``seg`` is a fully parenthesized group ``( ... )``.

    Returns ``None`` when the segment is not exactly one balanced group (e.g.
    ``a($x)`` or ``(a) AND (b)``), so non-group literals pass through.
    """
    seg = seg.strip()
    if not seg.startswith("("):
        return None
    depth = 0
    in_str: str | None = None
    i, n = 0, len(seg)
    while i < n:
        ch = seg[i]
        if in_str is not None:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in "\"'":
            in_str = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return seg[1:i].strip() if i == n - 1 else None
        i += 1
    return None


def _dedup_conjunctions(conjunctions: list[list[str]]) -> list[list[str]]:
    """Drop duplicate disjuncts preserving first-seen order (e.g. ``a OR a``)."""
    seen: set[tuple[str, ...]] = set()
    out: list[list[str]] = []
    for conj in conjunctions:
        key = tuple(conj)
        if key not in seen:
            seen.add(key)
            out.append(conj)
    return out


def _dnf(body: str) -> list[list[str]]:
    """Convert a (possibly grouped) body into disjunctive normal form.

    Returns a list of conjunctions, each a list of goal strings. The rule
    ``H IF body`` then becomes one pure Horn rule per conjunction — the
    solver never sees an ``OR``.

    Semantics: ``AND`` binds tighter than ``OR`` (logic convention), so
    ``a OR b AND c`` is ``a OR (b AND c)`` and yields the rules ``H IF a``
    and ``H IF b, c``. Parenthesized groups ``(...)`` are expanded
    distributively: ``(a OR b) AND c`` yields ``H IF a, c`` and ``H IF b, c``.
    """
    conjunctions: list[list[str]] = []
    for branch in _split_body(body, is_or=True):
        branch = branch.strip()
        if not branch:
            continue
        partial: list[list[str]] = [[]]
        for seg in _split_body(branch, is_or=False):
            seg = seg.strip()
            if not seg:
                continue
            if seg.lower().startswith("not ("):
                raise ValueError(
                    "NOT over a parenthesized group is not supported "
                    f"(got {seg!r}); negate single goals instead"
                )
            inner = _unwrap_group(seg)
            if inner is not None:
                sub = _dnf(inner)
                partial = [c + list(g) for c in partial for g in sub]
            else:
                partial = [c + [seg] for c in partial]
        conjunctions.extend(partial)
    return _dedup_conjunctions(conjunctions)


def _contains_or(text: str) -> bool:
    """True when the text has a word-boundary ``or`` outside quoted strings.

    Group depth is irrelevant: an ``or`` inside ``(a OR b)`` still needs
    expansion. Atoms like ``color`` or string literals like ``"now or never"``
    must not count.
    """
    in_str: str | None = None
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if in_str is not None:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in "\"'":
            in_str = ch
            i += 1
            continue
        if text[i : i + 2].lower() == "or":
            before_ok = i == 0 or text[i - 1].isspace()
            after_ok = i + 2 >= n or text[i + 2].isspace()
            if before_ok and after_ok:
                return True
        i += 1
    return False


def _expand_rule(rule: str, rule_id: str | None) -> list[tuple[str, str | None]]:
    """Expand one rule with OR in its body into pure Horn rules.

    Returns ``(rule_text, rule_id)`` pairs; rules without OR pass through
    unchanged so ``parse()`` output always consists of Horn clauses only.
    """
    parts = _IF_RE.split(rule, maxsplit=1)
    head, body = parts[0].strip(), (parts[1].strip() if len(parts) == 2 else "")
    if not _contains_or(body):
        return [(rule, rule_id)]
    conjunctions = _dnf(body) or [[body]]
    return [
        (f"{head} if {', '.join(conj)}", rule_id) for conj in conjunctions
    ]


def _expand_or_rules(kb: KB) -> KB:
    """Expand OR in rule bodies into pure Horn rules, in place.

    Each expanded branch keeps the source rule's ``rule_id`` (so every proof
    path cites it) and ``rule_sources`` records provenance (expanded index →
    original index) so ``check_kb`` never misreads siblings as duplicate IDs.
    """
    new_rules: list[str] = []
    new_ids: dict[int, str] = {}
    new_sources: dict[int, int] = {}
    for idx, rule in enumerate(kb.rules):
        source = kb.rule_sources.get(idx, idx)
        rule_id = kb.rule_ids.get(idx)
        for expanded, rid in _expand_rule(rule, rule_id):
            new_rules.append(expanded)
            out_idx = len(new_rules) - 1
            if rid:
                new_ids[out_idx] = rid
            new_sources[out_idx] = source
    kb.rules = new_rules
    kb.rule_ids = new_ids
    kb.rule_sources = new_sources
    return kb


def _ensure_list(val):
    if isinstance(val, list):
        return [str(v).strip().rstrip(".") for v in val]
    if isinstance(val, str):
        return [val.strip().rstrip(".")]
    return []

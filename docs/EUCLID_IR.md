# Euclid-IR Language Reference

**Version 1.0**

Euclid-IR (Intermediate Representation) is a declarative language for logical inference. It provides a clean, human-readable syntax for expressing facts, rules, and queries — without requiring knowledge of Prolog.

Euclid-MCP translates Euclid-IR into Prolog, executes the deduction, and returns structured results with proof trees.

## Design Principles

1. **Readability** — Syntax optimized for both humans and LLMs
2. **Minimalism** — Only the essential constructs of Horn-clause logic
3. **Determinism** — Every query has a finite, traceable proof
4. **Backend-agnostic** — Euclid-IR is an intermediate layer; today it targets Prolog, tomorrow it could target other engines

## Quick Start

```
# Facts
parent(tom, bob)
parent(bob, ann)

# Rules
ancestor($x, $y) IF parent($x, $y)
ancestor($x, $y) IF parent($x, $z) AND ancestor($z, $y)

# Query
? ancestor(tom, $who)
```

Output: `$who = bob`, `$who = ann` (with full proof trees).

---

## Quick Reference

| Syntax | Meaning | Example |
|--------|---------|---------|
| `predicate(args)` | Fact | `parent(tom, bob)` |
| `$name` | Variable | `$x`, `$who` |
| `head IF body` | Rule | `mortal($x) IF human($x)` |
| `a AND b` | Conjunction | `p($x) AND q($x)` |
| `NOT a` | Negation | `NOT active($user)` |
| `a OR b` | Disjunction | `admin($u) OR dev($u)` |
| `(...)` | Grouping | `is_admin($u) OR (dev($u) AND env($u, staging))` |
| `true` / `false` | Boolean body literals | `declared($x) IF false` |
| `? goal` | Query | `? mortal($who)` |
| `# RULE: <id>` | Rule ID (trailing comment) | `mortal($x) IF human($x)  # RULE: BIO-001` |
| `a != b` | Inequality | `$x != 0` |
| `a > b` | Arithmetic | `$days > 90` |
| `"text"` | String literal | `"alice@example.com"` |
| `# comment` | Comment | `# this is ignored` |
| `% comment` | Comment (Prolog style) | `% also ignored` |
| `_` | Wildcard | `parent($x, _)` |

---

## Version Directive

The first line of a knowledge base can declare a version:

```
@version 1.0

parent(tom, bob)
? parent($x, $y)
```

- **Optional** — if omitted, version `1.0` is assumed
- **Retrocompatible** — future versions will maintain backward compatibility
- **Parsed as a directive** — not treated as a fact or comment
- **Surfaced in results** — every tool result (`reason`, `explain`, `diagnose`,
  `what_if`, `check_kb`) exposes `version` (the value of `@version`) together
  with `content_hash` (sha256 of the KB text payload), on success and on error
  branches. Anyone holding the `.euclid` text and Euclid-MCP can recompute the
  hash and verify that a result was computed from that exact knowledge base.

---

## Named Knowledge Bases (`kb_id` + `delta_knowledge`)

A KB can be registered once under a `kb_id` (`register_kb`) and then referenced
on every tool call instead of resending the text. Registration validates the
KB with `check_kb` first. The registry is **in-memory per instance** (max 32
KBs, overwrite allowed), so replicas re-register on startup.

All reasoning tools accept `kb_id` plus an optional `delta_knowledge` overlay
(session-specific facts appended to the registered base):

```
# Register once (validated with check_kb)
register_kb(kb_id="policies", knowledge="...")

# Reference it, with a session overlay
? can_deploy($user, $env)
# → via the tool: kb_id="policies", delta_knowledge="has_role(alice, dev)"
```

Resolution precedence on every reasoning tool: explicit
`knowledge`/`base_knowledge` wins → `kb_id` (`Unknown kb_id` when absent) →
preloaded KB (`EUCLID_KB_PATH`) → "No knowledge provided". `delta_knowledge`
requires a `kb_id`. With `kb_id` + `delta_knowledge`, `content_hash`/`version`
are computed from the effective merged source.

---

## Lexical Rules

| Rule | Detail |
|------|--------|
| **Case sensitivity** | Identifiers are case-insensitive. `Human(ALICE)` normalizes to `human(alice)`. Keywords (`IF`, `AND`, `OR`, `NOT`) are also case-insensitive. |
| **Variables** | Start with `$` followed by a lowercase letter: `$x`, `$who`, `$user_name` |
| **Atoms** | Lowercase identifiers: `tom`, `admin_role`, `us_east_1` |
| **String literals** | UTF-8 strings in double or single quotes: `"Alice Smith"`, `'http://example.com'` |
| **Numbers** | Decimal integers and floats: `42`, `-7`, `0`, `999`, `3.14`. Scientific notation (`1e3`), hex/binary/octal (`0x10`), digit separators (`1_000`) and trailing name characters (`12abc`) are parse errors. A leading-dot token like `.5` is an **atom**, not a number — write `0.5` |
| **Comments** | `#`, `//`, or `%` at line start or inline |
| **Trailing dots** | Optional, ignored (for Prolog familiarity) |
| **Whitespace** | Newlines separate statements; spaces separate tokens |

---

## Syntax Reference

### Facts

Ground assertions about the world.

```
parent(tom, bob)
color(apple, red)
active(user_42)
rainy
```

**Rules:**
- Predicate name: lowercase, no spaces
- Arguments: strictly comma-separated (atoms, numbers, strings, or variables); adjacent terms without a comma (`p(a b)`, `p(1-2)`) are parse errors
- No arguments → zero-arity fact: `rainy`
- Zero-arity facts can also be written as bare atoms: `rainy` (equivalent to `rainy.`)

### Variables

Variables represent unknown or generic values. They start with `$`:

```
$person
$x
$resource_name
$level
```

**Naming rules:**
- Must start with `$` + lowercase letter
- Can contain letters, digits, underscores
- Case-sensitive: `$x` ≠ `$X` (only `$x` is valid)
- Convention: use descriptive names for LLM readability (`$user`, `$count`)

**Translation to Prolog:** `$varname` → `Varname` (capitalized)

### String Literals

UTF-8 strings for real-world data (emails, URLs, addresses):

```
user(alice, "alice@example.com")
address(bob, 'Via Roma, 15')
url(charlie, "https://example.com/path?q=1 AND foo")
```

**Rules:**
- Both `"..."` and `'...'` syntax supported
- Choose whichever minimizes escaping
- Strings preserve whitespace and case (not normalized to lowercase)
- Strings containing `IF`, `AND`, `NOT`, or `OR` are handled correctly
- Escape characters: `\"`, `\'`, `\\`, `\n`, `\t`

**Translation to Prolog:** Passed through as Prolog strings.

### Rules (Implication)

Rules define logical relationships. The head is implied by the body.

```
mortal($x) IF human($x)
```

**Syntax:** `<head> IF <body>`

- `IF` separates head from body (case-insensitive)
- Head: a predicate (possibly with variables)
- Body: one or more conditions connected by `AND` and/or `OR`
  (case-insensitive); see [Conjunction](#conjunction-and) and
  [Disjunction](#disjunction-or)

**Multiple conditions:**

```
grandparent($x, $y) IF parent($x, $z) AND parent($z, $y)
```

### Conjunction (AND)

Connects multiple conditions in a rule body or query:

```
rule($x) IF condition1($x) AND condition2($x) AND condition3($x)
```

**In queries:**

```
? can_access_resource($who, $res) AND resource($res, _, _, _, _, secret)
```

Both conditions must be satisfied simultaneously.

### Negation (NOT)

Closed-world negation — "it is not the case that":

```
blocked($user) IF NOT active($user)
eligible($user) IF registered($user) AND NOT blocked($user)
```

**Semantics:** `NOT predicate` succeeds when `predicate` cannot be proven (Prolog's `\+`).

**Warning:** Negation as failure is not logical negation. `NOT mortal(socrates)` succeeds if `mortal(socrates)` cannot be derived — not if it is "false."

### Disjunction (OR)

A rule body can express alternatives with `OR` (case-insensitive). The rule
is expanded into one pure Horn clause per alternative at parse time, so the
engine still reasons over Horn clauses only:

```
can_access($u, $r) IF is_admin($u) OR has_role($u, auditor)
```

is equivalent to:

```
can_access($u, $r) IF is_admin($u)
can_access($u, $r) IF has_role($u, auditor)
```

**Precedence:** `AND` binds tighter than `OR` (logic convention), so
`a OR b AND c` means `a OR (b AND c)`:

```
can_deploy($u) IF is_admin($u) OR has_role($u, dev) AND env_ok($u)
# == can_deploy($u) IF is_admin($u)
# == can_deploy($u) IF has_role($u, dev) AND env_ok($u)
```

**Grouping:** parenthesized groups mix `AND` and `OR` arbitrarily and expand
distributively:

```
can($u) IF (is_admin($u) OR support($u)) AND active($u)
# == can($u) IF is_admin($u) AND active($u)
# == can($u) IF support($u) AND active($u)
```

Rules:
- `OR` applies to rule **bodies** (and multi-line bodies); it is not
  supported in queries or facts.
- Negation applies to single goals: `NOT a($x)` is fine; `NOT (a OR b)`
  (De Morgan) is rejected with a clear parse error.
- A rule with a `# RULE: <id>` carries the same ID on every expanded branch,
  so each proof path is still auditable against the source rule.
- `rules_count` (in `check_kb`, `register_kb`, `list_kbs`) counts the
  **expanded** Horn clauses that are actually loaded — `content_hash` stays
  computed on the exact source text, unchanged.

### Boolean Literals (`true` / `false`)

The two reserved words are boolean literals for rule bodies:

```
always($x) IF true      # body always satisfied — the rule proves like a fact
never($x) IF false      # body never satisfied — the rule can prove nothing
```

**Semantics** (identical on both engines):

- `true` in a body always succeeds; a rule whose only body goal is `true`
  proves exactly like a fact (proof node `fact`, or `rule` when it carries
  a Rule ID).
- `false` in a body always fails: the rule can never contribute a solution.
  Under negation it behaves as an empty relation —
  `NOT declared($x)` holds.

**Reserved:** `true` and `false` cannot be used as predicate names, as bare
facts, or as rule heads. As *arguments* they are plain atom data:
`parent(false, x)` is fine. A query goal may use them directly
(`? false` simply returns zero solutions).

**Vocabulary declarations** — the main use of `IF false`. Knowledge bases
that follow the load-once/query-many lifecycle keep rules and input facts in
separate layers: the stable KB declares every predicate whose facts arrive at
query time via `delta_knowledge`, so it validates green on its own while the
declarations can never contribute solutions:

```
# ── Vocabulary declarations (facts arrive via delta_knowledge) ──
merchant($m) IF false  # RULE: VOCAB-MERCHANT
annual_txn_volume($m, $n) IF false  # RULE: VOCAB-TXN-VOL
```

### Query

The `?` prefix marks a query — what you want to prove:

```
? mortal(socrates)
? ancestor(tom, $who)
? can_access_resource($user, $resource) AND resource($resource, _, _, _, _, secret)
```

**Rules:**
- One query per knowledge base (or override via `query` parameter)
- Can include variables (to find bindings) or be ground (boolean check)
- Can use `AND` for conjunctions
- Ground queries return empty substitution `{}` if true

#### Unbound query variables

A solution may leave some query variables unbound — e.g. rules whose head
variable does not occur in the body (*non-range-restricted*), or negation
over an empty declared predicate:

```
report($user) IF system_compromised
system_compromised
unflagged($m) IF NOT merchant($m)

? report($who)
```

Both engines keep such solutions and surface the unbound variable as an
explicit `null` binding instead of dropping the answer:

```json
{"substitutions": {"who": null}, "proof": {"type": "rule", "goal": "report(_)"}}
```

Unbound variables inside proof-tree goals render as the wildcard `_`, so
proof trees are identical across backends and deterministic across runs.
Treat `null` as "proved regardless of this value" — combine with a bound
query (e.g. `? report(alice)`) when you need per-value answers.

### Arithmetic Comparisons

Compare numeric values in rule bodies:

```
stale($user) IF last_login($user, $days) AND $days > 90
adult($person) IF age($person, $age) AND $age >= 18
active($user) IF status($user, $s) AND $s != "inactive"
```

**Supported operators:**

| Operator | Prolog equivalent | Meaning | Example |
|----------|-------------------|---------|---------|
| `!=` | `=\=` | Not equal | `$x != 0` |
| `<=` | `=<` | Less or equal | `$x <= 50` |
| `>` | `>` | Greater than | `$x > 0` |
| `>=` | `>=` | Greater or equal | `$x >= 18` |
| `<` | `<` | Less than | `$x < 100` |
| `==` | `=:=` | Arithmetic equal | `$x == 42` |
| `is` | `is` | Assignment/evaluation | `$x is $y + 1` |

**Note:** `==`, `!=` and `<=` are Euclid-IR convenience operators. The translator maps them to the Prolog equivalents `=:=`, `=\=` and `=<`. The raw Prolog forms (`=:=`, `=\=`, `=<`) are still accepted.

### Multi-line Rules

Rules can span multiple lines for readability:

```
can_deploy($user, $env) IF
    user($user) AND
    has_role($user, $role) AND
    deploy_requires_level($env, $min) AND
    deploy_role_level($role, $level) AND
    $level >= $min AND
    user_has_permission($user, deploy_code)
```

**Parsing rules:**
- If a line ends with `IF`, `AND`, or `OR`, the parser continues to the next
  line (*trailing* style)
- If a line starts with `AND` or `OR`, it continues the rule written above it
  (*leading* style — the common Prolog habit):

  ```
  dimmi($x) IF $x > 0
            AND $y is $x - 1
            AND dimmi($y)
  ```

- OR branches can span lines too:

  ```
  can_deploy($u, $env) IF
      is_admin($u) OR
      (has_role($u, dev) AND env_approved($u, $env))
  ```

- All parts are joined into a single rule statement
- Indentation is ignored (cosmetic only)

A leading `AND` / `OR` without a preceding rule is a parse error.

### Wildcard Arguments

Use `_` for arguments you want to ignore:

```
# "What is the color of apple?" — ignore category and season
resource(apple, $color, _, _, _, _)
```

Wildcards are translated to Prolog anonymous variables (`_`).

### Comments

Two styles, both supported:

```
# This is a comment
// This is also a comment
% Prolog-style comment

parent(tom, bob)  # inline comment
active(user_42)   // inline comment
```

Comments are stripped during parsing.

### Rule IDs

Rules can carry an audit-trail identifier via a trailing `# RULE: <id>` comment.
The ID is surfaced as `rule_id` on the `rule` nodes of the proof tree, so a
decision can be cited ("this derives from rule RBAC-0043").

```
can_access($u, $r) IF has_role($u, $role) AND role_perm($role, $r)  # RULE: RBAC-0043
```

For multi-line rules, place the `# RULE:` comment on the **last body line**:

```
can_deploy($user, $env) IF
    user($user) AND
    has_role($user, $role) AND
    deploy_requires_level($env, $min) AND
    $level >= $min  # RULE: DEPLOY-POL-1
```

**Rules:**
- `# RULE:` is reserved. A plain trailing comment (e.g. `# important rule`)
  stays an ordinary comment. A standalone line `# RULE: X` is ignored.
- `# RULE:` on a fact or query is a **parse error**.
- IDs preserve case (extracted before lowercasing), like string literals.
- `check_kb` warns on duplicate rule IDs.
- Backward compatible: rules without an ID behave exactly as before and their
  proofs omit the `rule_id` field.

**Proof output:**

```json
{
  "type": "rule",
  "goal": "can_access(alice, db_1)",
  "body": "has_role(alice,admin), role_perm(admin,db_1)",
  "rule_id": "RBAC-0043",
  "subproof": {"type": "and", "left": {...}, "right": {...}}
}
```

**Security:** the ID is re-emitted as an escaped Prolog string — hostile input
like `# RULE: '); halt.` cannot break out of the engine.

### YAML Format

Euclid-IR also supports YAML input:

```yaml
facts:
  - parent(tom, bob)
  - parent(bob, ann)
rules:
  - ancestor($x, $y) IF parent($x, $y)
  - ancestor($x, $y) IF parent($x, $z) AND ancestor($z, $y)
query: ancestor(tom, $who)
```

**Recommendation:** Use the text format — it is more concise and less error-prone.

---

## Examples

### 1. Simple fact query

```
red(apple)
blue(sky)
? red($x)
```

**Result:** `$x = apple`

### 2. Rule with variable

```
human(socrates)
mortal($x) IF human($x)
? mortal($who)
```

**Result:** `$who = socrates` (deduced from rule)

### 3. Recursive rules (ancestry)

```
parent(tom, bob)
parent(bob, ann)
parent(tom, liz)

ancestor($x, $y) IF parent($x, $y)
ancestor($x, $y) IF parent($x, $z) AND ancestor($z, $y)

? ancestor(tom, $who)
```

**Result:** `$who = bob`, `$who = ann`, `$who = liz`

### 4. Negation

```
active(alice)
active(bob)
blocked(charlie)

eligible($user) IF active($user) AND NOT blocked($user)
? eligible($who)
```

**Result:** `$who = alice`, `$who = bob`

### 5. Arithmetic

```
user(alice)
user(bob)
user(charlie)
last_login(alice, 5)
last_login(bob, 45)
last_login(charlie, 120)

stale($user) IF user($user) AND last_login($user, $days) AND $days > 90
? stale($who)
```

**Result:** `$who = charlie`

### 6. Multi-line rule with conjunction query

```
user(alice)
role(alice, admin)
role_level(admin, 5)
env_requires_level(prod, 3)
permission(alice, deploy_code)

can_deploy($user, $env) IF
    user($user) AND
    role($user, $role) AND
    role_level($role, $level) AND
    env_requires_level($env, $min) AND
    $level >= $min AND
    permission($user, deploy_code)

? can_deploy(alice, prod)
```

**Result:** `{}` (empty substitution = true)

### 7. Boolean query (no variables)

```
grass_is_green
sky_is_blue
? grass_is_green
```

**Result:** `{}` if true (no variable bindings)

### 8. Multi-tool workflow

Start with a knowledge base and use different tools to analyze it:

```
human(socrates)
human(plato)
mortal($x) IF human($x)
```

**Step 1 — Validate** with `check_kb`:
```json
{"valid": true, "errors": [], "warnings": [], "facts_count": 2, "rules_count": 1, "predicates_count": 2}
```

**Step 2 — Reason** with `reason` (`? mortal($who)`):
```json
{"solutions": [
  {"substitutions": {"who": "plato"}, "proof": {...}},
  {"substitutions": {"who": "socrates"}, "proof": {...}}
]}
```

**Step 3 — Diagnose** a failing query with `diagnose` (`mortal(aristotle)`, mode `why_not`):
```json
{"holds": false, "findings": [
  {"type": "satisfied", "predicate": "human", "detail": "Facts exist for 'human' (2 facts)"}
], "conclusion": "The query fails. Check rule conditions."}
```

**Step 4 — What-if** adding a fact with `what_if` (`+ human(aristotle)`):
```json
{"before_count": 2, "after_count": 3, "delta": "more"}
```

**Step 5 — Explain** the solutions in natural language with `explain`
(`? mortal($who)`):
```json
{"explanations": [
  {"substitutions": {"who": "socrates"}, "steps": [
    "mortal(socrates) is derived by a rule from: human(socrates).",
    "human(socrates) is asserted as a fact in the knowledge base."
  ], "structured_steps": [
    {"kind": "rule", "goal": "mortal(socrates)", "rule_id": null,
     "body": ["human(socrates)"]},
    {"kind": "fact", "goal": "human(socrates)", "rule_id": null, "body": []}
  ]}
]}
```

The `structured_steps` are language-independent: typed steps (`kind`,
`goal`, `rule_id`, `body` conjuncts) from which the English `steps` are
derived, so a UI can render them with localized templates.

If the rules carry `# RULE:` IDs, `explain` cites them: *"mortal(socrates) is
derived by rule BIO-001 from: human(socrates)."* and the `structured_steps`
`rule_id` fields carry the ID.

---

## Comparison with Prolog

| Euclid-IR | Prolog equivalent |
|-----------|-------------------|
| `parent(tom, bob)` | `parent(tom, bob).` |
| `$x` | `X` (capitalized) |
| `mortal($x) IF human($x)` | `mortal(X) :- human(X).` |
| `a($x) AND b($x)` | `a(X), b(X)` |
| `NOT active($x)` | `\+ active(X)` |
| `? ancestor(tom, $who)` | `?- ancestor(tom, Who).` |
| `$x != 0` | `X =\= 0` |
| `$x <= 10` | `X =< 10` |
| `$x == 42` | `X =:= 42` |
| `$days > 90` | `Days > 90` |
| `"Alice Smith"` | `"Alice Smith"` |

**Key differences:**
- `$` prefix for variables (vs. uppercase first letter in Prolog)
- `IF` instead of `:-`
- `AND` instead of `,`
- `NOT` instead of `\+`
- `?` prefix for queries
- `!=` instead of `=\=`, `<=` instead of `=<`, `==` instead of `=:=`
- No cut (`!`), no `;` (use `OR` — it's desugared to Horn clauses), no list syntax

---

## Known Limitations

Euclid-IR is a **simplified subset of Horn-clause logic** — the core of Prolog without unnecessary features:

| Feature | Status | Notes |
|---------|--------|-------|
| Horn clauses | ✅ Supported | Facts + rules with conjunction |
| Negation (NOT) | ✅ Supported | Closed-world assumption |
| Arithmetic | ✅ Supported | `!=`, `<=`, `>`, `>=`, `<`, `==`, `is` |
| Number literals | ✅ Supported | Decimal integers and floats only — no scientific notation (`1e3`), hex/binary/octal, or digit separators (`1_000`) |
| Multi-line rules | ✅ Supported | Body spans multiple lines |
| Conjunction queries | ✅ Supported | `AND` in query |
| String literals | ✅ Supported | UTF-8 strings in `"..."` or `'...'` |
| Rule IDs | ✅ Supported | `# RULE: <id>` trailing comment, surfaced as `rule_id` in proofs |
| Boolean literals | ✅ Supported | `true` / `false` in rule bodies; reserved as predicate names |
| Case-insensitive | ✅ Supported | `Human(ALICE)` → `human(alice)` |
| Disjunction (OR) | ✅ Supported | In rule bodies; expanded to Horn clauses at parse time. `AND` binds tighter than `OR`; groups `(...)` supported; `NOT (group)` rejected |
| Cut (!) | ❌ Not supported | No backtracking control |
| Lists `[H\|T]` | ❌ Not supported | No pattern matching on lists |
| findall/bagof | ❌ Not supported | No collection of solutions |
| Assert/retract | ❌ Not supported | No dynamic facts at runtime |
| Modules | ❌ Not supported | Single knowledge base |

**Workarounds:**

- **OR:** write it directly — the parser expands it for you:
  ```
  mortal($x) IF human($x) OR god($x)
  ```

- **Lists:** Represent as facts:
  ```
  item(list_1, apple)
  item(list_1, banana)
  item(list_2, carrot)
  ```

---

## Best Practices for LLMs

When writing Euclid-IR knowledge for LLM consumption:

1. **One concept per predicate** — Don't overload predicates with multiple meanings
2. **Descriptive variable names** — `$user` instead of `$u`; `$resource_name` instead of `$r`
3. **Separate data from rules** — Load facts from external sources, keep rules in `.euclid` files
4. **Use comments** — Document the intent of complex rules
5. **Place query at the end** — The `?` line should be the last statement
6. **Limit rule depth** — Keep `max_depth` reasonable (default 30) to prevent infinite loops
7. **Test incrementally** — Start with simple facts, add rules one by one

### Example: LLM-friendly format

```
# User directory
user(alice)
user(bob)
user(charlie)

# Role assignments
has_role(alice, admin)
has_role(bob, developer)
has_role(charlie, viewer)

# Role hierarchy
role_level(admin, 5)
role_level(developer, 3)
role_level(viewer, 1)

# Access policy: admin can do everything
can_access($user, $resource) IF
    user($user) AND
    has_role($user, $role) AND
    role_level($role, $level) AND
    $level >= 4

# Query: who can access anything?
? can_access($who, $resource)
```

---

## File Extension

Euclid-IR files use the `.euclid` extension:

```
my_policies.euclid
```

This is a convention, not enforced. The parser accepts any text input.

---

## Error Handling

Common parsing errors and fixes:

| Error | Cause | Fix |
|-------|-------|-----|
| "No query found" | Missing `?` line | Add `? predicate(...)` at the end |
| "Invalid variable" | `$X` or `$123` | Use `$x` or `$name` (lowercase after `$`) |
| "Unterminated rule" | Missing body after `IF` | Add at least one condition |
| "Unknown keyword" | A reserved keyword used as a predicate name | Rename the predicate (`if`, `and`, `or`, `not`, `is`, `true`, `false` are reserved) |

---

## Glossary

| Term | Definition |
|------|------------|
| **Atom** | A lowercase identifier representing a constant: `tom`, `admin_role` |
| **Variable** | A `$`-prefixed identifier representing an unknown: `$x`, `$who` |
| **Fact** | A ground assertion: `parent(tom, bob)` |
| **Rule** | A logical implication: `mortal($x) IF human($x)` |
| **Query** | A goal to prove: `? mortal($who)` |
| **Proof tree** | The logical derivation path for a solution |
| **Substitution** | Variable bindings that make the query true |
| **Knowledge base** | The complete set of facts, rules, and query |
| **Backtracking** | Prolog's search mechanism for finding all solutions |
| **Closed-world assumption** | What cannot be proven is assumed false (basis of NOT) |

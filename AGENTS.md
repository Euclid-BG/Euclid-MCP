# Euclid-MCP — Agent Guide

Deterministic logical reasoning engine. Write facts/rules in **Euclid IR**, engine translates to Prolog, returns solutions with **proof trees**.

Tools: `euclid-mcp_reason`, `euclid-mcp_explain`, `euclid-mcp_diagnose`, `euclid-mcp_what_if`, `euclid-mcp_check_kb`, `euclid-mcp_register_kb`, `euclid-mcp_unregister_kb`, `euclid-mcp_list_kbs`

## Workflow

```
1. check_kb    → validate before reasoning (catch syntax errors, undefined predicates)
2. reason      → run deduction, get solutions + proof trees
3. explain     → turn solutions into readable, auditable reasoning steps
4. diagnose    → if result unexpected: mode="why_not" to find missing facts/rules
5. what_if     → test modifications before applying them
```

Always call `check_kb` first on new or modified knowledge bases.

`knowledge`/`base_knowledge` are optional on all reasoning tools: an empty
value falls back to `kb_id` (if given) and then to the preloaded KB
(`EUCLID_KB_PATH` / `--kb-path`). For repeated sessions, `register_kb` once
and pass `kb_id` (+ an optional `delta_knowledge` overlay for session facts)
instead of resending the KB text.

## Tools

### `reason`
Main deduction. Returns solutions with variable bindings and proof trees.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `knowledge` | `string?` | — | Facts & rules (falls back to `kb_id`, then preloaded KB) |
| `kb_id` | `string?` | — | Reference a KB registered via `register_kb` |
| `delta_knowledge` | `string?` | — | Session facts appended to the `kb_id` base |
| `query` | `string?` | — | Override query (optional) |
| `max_solutions` | `int` | `5` | Max solutions |
| `max_depth` | `int` | `30` | Max proof tree depth |

### `explain`
Deterministic proof-tree → natural-language reasoning steps. Cites `rule_id`
when a rule has one. Each explanation also carries `structured_steps`: typed,
language-independent steps (`kind`/`goal`/`rule_id`/`body`) from which the
English `steps` are derived — use them for localized rendering.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `knowledge` | `string?` | — | Facts & rules (falls back to `kb_id`, then preloaded KB) |
| `kb_id` | `string?` | — | Reference a KB registered via `register_kb` |
| `delta_knowledge` | `string?` | — | Session facts appended to the `kb_id` base |
| `query` | `string?` | — | Override query (optional) |
| `max_solutions` | `int` | `5` | Max solutions |
| `max_depth` | `int` | `30` | Max proof tree depth |

### `diagnose`
Why a query succeeds or fails.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `knowledge` | `string?` | — | Facts & rules (falls back to `kb_id`, then preloaded KB) |
| `kb_id` | `string?` | — | Reference a KB registered via `register_kb` |
| `delta_knowledge` | `string?` | — | Session facts appended to the `kb_id` base |
| `query` | `string` | — | Query to diagnose |
| `mode` | `string` | `why` | `why` / `why_not` / `what_needs` |
| `max_solutions` | `int` | `5` | Max solutions |
| `max_depth` | `int` | `30` | Max proof depth |

### `what_if`
Test modifications before applying. `+` prefix to add, `-` to remove.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_knowledge` | `string?` | — | Base facts & rules (falls back to `kb_id`, then preloaded KB) |
| `kb_id` | `string?` | — | Reference a KB registered via `register_kb` |
| `delta_knowledge` | `string?` | — | Session facts appended to the `kb_id` base |
| `modifications` | `string` | — | `+ fact(...)` or `- fact(...)` |
| `query` | `string` | — | Query to evaluate |
| `max_solutions` | `int` | `5` | Max solutions |
| `max_depth` | `int` | `30` | Max proof depth |

### `check_kb`
Validate knowledge base for errors before reasoning. Returns also the
predicate inventory (name → arities, facts, rules counts) — the derived
contract for LLM extraction.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `knowledge` | `string?` | — | Facts & rules (falls back to `kb_id`, then preloaded KB) |
| `kb_id` | `string?` | — | Reference a KB registered via `register_kb` |
| `delta_knowledge` | `string?` | — | Session facts appended to the `kb_id` base |

### `register_kb`
Register a named KB once, then reference it by `kb_id` on later calls.
Validates `kb_id` (allowlist `[a-z0-9_-]{1,64}`) and the KB (`check_kb`);
**overwrites** an existing `kb_id`. Returns `registered`, `kb_id`,
`content_hash`, `version`, `facts`, `rules`, `predicates`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `kb_id` | `string` | — | Name (1-64 lowercase letters, digits, `_`, `-`) |
| `knowledge` | `string` | — | Facts & rules to store |

### `unregister_kb`
Remove a named KB. Returns `removed: true/false`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `kb_id` | `string` | — | Name of the KB to remove |

### `list_kbs`
List registered named KBs (metadata only — `kb_id`, `content_hash`, `version`,
`facts`, `rules`, `predicates`; no source text).

## Euclid IR Syntax

```
# Facts
parent(tom, bob)
active(user_42)
rainy

# Rules
mortal($x) IF human($x)  # RULE: BIO-001
ancestor($x, $y) IF parent($x, $z) AND ancestor($z, $y)

# Disjunction (expanded into one Horn clause per branch at parse time)
can_access($u) IF is_admin($u) OR has_role($u, auditor)
can_deploy($u) IF (is_admin($u) OR support($u)) AND active($u)   # groups + AND > OR

# Negation
blocked($user) IF NOT active($user)

# Arithmetic
stale($user) IF user($user) AND last_login($user, $days) AND $days > 90

# Query (? prefix required)
? mortal($who)
? can_access_resource($user, $res) AND resource($res, _, _, _, _, secret)
```

### Rules
- Variables: `$name` (lowercase after `$`)
- Implication: `IF` (case-insensitive)
- Conjunction: `AND` (case-insensitive)
- Disjunction: `OR` (case-insensitive) — expands to one rule per branch;
  `AND` binds tighter than `OR`; parenthesized groups `(a OR b) AND c` expand
  distributively; `NOT` applies to single goals only (`NOT (group)` rejected)
- Negation: `NOT` (case-insensitive)
- Query prefix: `?` on a separate line
- Predicates: lowercase with args in `()`
- Wildcards: `_` (anonymous variable)
- Comments: `#` or `//`
- Rule IDs: trailing `# RULE: <id>` → surfaced as `rule_id` in proofs, cited by `explain`
- Multi-line rules: continuation implied after `IF` or `AND`, and for lines starting with `AND` (also after `OR` and lines starting with `OR`)

### Supported operators
`>`, `>=`, `<`, `<=`, `==`, `is`, `!=`

### String literals
UTF-8 strings for real-world data (emails, URLs, addresses):
```
user(alice, "alice@example.com")
address(bob, 'Via Roma, 15')
```

## Proof Tree Nodes

- `fact` — goal proved from a fact (leaf)
- `rule` — goal proved by rule application (has `goal`, `body`, `subproof`)
- `and` — conjunction of two sub-goals (has `left`, `right`)

## Common Patterns

**Boolean check** (no variables): `? grass_is_green` → `{}` if true

**Multi-hop reasoning**: chain rules with `AND`
```
can_deploy($user, $env) IF
    user($user) AND
    has_role($user, $role) AND
    deploy_requires_level($env, $min) AND
    deploy_role_level($role, $level) AND
    $level >= $min
```

**Diagnostic flow**:
1. `reason` returns unexpected → `diagnose(mode="why_not")` → find missing facts
2. `diagnose(mode="what_needs")` → suggest what to add

**KB identity**: every result carries `content_hash` (sha256 of the KB text
payload) and `version` (from the `@version` directive) — on every return path,
including error branches. With a `kb_id` + `delta_knowledge`, both are computed
from the effective source (base + delta). Use the hash to pin a result to the
exact KB text it was computed from (e.g. before storing it in an audit log).

**Named KB precedence** on all reasoning tools: explicit `knowledge`/
`base_knowledge` wins → `kb_id` (`Unknown kb_id` when absent) → preloaded KB →
"No knowledge provided". `delta_knowledge` is appended to the registered base
and requires a `kb_id`.

## Development

Standard verification commands (run before committing changes):

```bash
ruff check .                       # lint
mypy euclid_mcp integrations       # type check
pytest --cov=euclid_mcp --cov=integrations   # tests + coverage (fail_under 80)
```

The CI workflow (`.github/workflows/ci.yml`) runs these on every push/PR.
Optional local hooks are provided via `.pre-commit-config.yaml`
(`pre-commit install`).

## Limitations

- Predicate/fact names: **lowercase only** (case-insensitive: `Human(ALICE)` → `human(alice)`)
- Variables: `$` + lowercase (`$x`, `$who`)
- No cut, list syntax, findall/bagof, dynamic assert/retract, modules
- Horn-clause logic only (disjunction `OR` in rule bodies is expanded into Horn clauses at parse time)

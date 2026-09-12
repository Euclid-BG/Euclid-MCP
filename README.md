# Euclid-MCP

[![Euclid-MCP MCP server](https://glama.ai/mcp/servers/Euclid-BG/Euclid-MCP/badges/score.svg)](https://glama.ai/mcp/servers/Euclid-BG/Euclid-MCP)
[![PyPI version](https://img.shields.io/pypi/v/euclid-mcp?color=blue)](https://pypi.org/project/euclid-mcp/)
[![Python versions](https://img.shields.io/pypi/pyversions/euclid-mcp)](https://pypi.org/project/euclid-mcp/)
[![License](https://img.shields.io/github/license/Euclid-BG/Euclid-MCP?cacheSeconds=86400)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/Euclid-BG/Euclid-MCP/ci.yml?branch=main&label=CI)](https://github.com/Euclid-BG/Euclid-MCP/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/codecov/c/github/Euclid-BG/Euclid-MCP)](https://codecov.io/gh/Euclid-BG/Euclid-MCP)

**MCP server for logical reasoning** — turns facts into formal proofs.

<!-- mcp-name: io.github.Euclid-BG/euclid-mcp -->

Euclid-MCP is a hybrid cognitive architecture: a lightweight LLM describes the world in facts, and a deterministic engine performs the actual deduction. The LLM never needs to reason — it only needs to describe.

With Euclid-MCP, an 8B model can solve reasoning tasks that stump even 400B+ cloud models — because the engine handles deduction deterministically. Every answer comes with a proof tree, so you can trace *why* a conclusion holds, not just *what* it is. Use it to enforce RBAC policies, audit cloud compliance, validate loan eligibility rules, or reason over any domain where answers must be explainable and verifiable.

Euclid-MCP is written in Python and uses **Euclid-IR**, a human-readable intermediate language designed for both AI agents and humans. It uses **SWI-Prolog** as its primary inference engine — and, where SWI-Prolog is not available (e.g. minimal containers), a pure-Python **native engine** that interprets Euclid-IR directly (see [`docs/NATIVE_ENGINE.md`](docs/NATIVE_ENGINE.md)).
It can be consumed in multiple ways: via **MCP** by AI agents (OpenCode, Claude, Cursor), via **HTTP** by tools and automation platforms (n8n, Zapier, Make), and via **Python API** for direct integration. Euclid-IR rules can also be used to **augment RAG** pipelines with deterministic policy enforcement.


## How it works

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  LLM/Agent   │────▶│  Euclid-MCP      │────▶│  Translator  │────▶│  SWI-Prolog     │
│  (MCP Client)│◀────│  (MCPServer)     │◀────│  + Meta-IP   │◀────│  (persistent)   │
└──────────────┘     └──────────────────┘     └──────────────┘     └─────────────────┘
```

1. Receive facts, rules, and a query in a simple intermediate language
2. Translate into Prolog with a meta-interpreter for proof tree capture
3. Execute via a persistent SWI-Prolog engine process (JSON-lines protocol on stdin/stdout; the workspace is reloaded per call, no process spawn overhead)
4. Return solutions + proof trees as structured JSON

Additional tools (`explain`, `diagnose`, `what_if`, `check_kb`) extend this core flow with natural-language explanations, analysis, scenario testing, and validation.

LLMs describe. Euclid MCP proves.  


### Knowledge Base

For small knowledge bases, facts and rules can be provided with each request.

A knowledge base can be loaded at server startup and reused across
calls, so agents only pass the session-specific facts for the current query.
This minimizes token usage, improves performance, and allows small LLMs to reason over large rule sets without reconstructing the entire knowledge base for every request.


## Intermediate Language

Even if currently Euclid-MCP uses a Prolog Engine, no Prolog syntax is required.  
**Euclid-IR** (Intermediate Representation) is a declarative intermediate representation for logical inference.
Variables use `$name`, implication is `IF`, conjunction is `AND`.

**Text format:**
```
human(socrates)
mortal($x) IF human($x)

? mortal($who)
```

**YAML format:**
```yaml
facts:
  - parent(tom, bob)
  - parent(bob, ann)
  - parent(tom, liz)
rules:
  - ancestor($x, $y) IF parent($x, $y)
  - ancestor($x, $y) IF parent($x, $z) AND ancestor($z, $y)

query: ancestor(tom, $who)
```

Full language reference: [`docs/EUCLID_IR.md`](docs/EUCLID_IR.md)


### Euclid-IR Syntax Reference

| Element | Syntax | Example |
|---------|--------|---------|
| Facts | `predicate(args)` | `parent(tom, bob)` |
| Variables | `$name` (lowercase) | `$who`, `$x`, `$count` |
| Implication | `IF` | `mortal($x) IF human($x)` |
| Conjunction | `AND` | `p($x) AND q($x)` |
| Disjunction | `OR` | `can($u) IF is_admin($u) OR has_role($u, auditor)` |
| Grouping | `(...)` | `(is_admin($u) OR support($u)) AND active($u)` |
| Negation | `NOT` | `NOT active($user)` |
| Boolean literals | `true` / `false` in rule bodies | `merchant($m) IF false` |
| Query | `? predicate` | `? ancestor(tom, $who)` |
| String literals | `"..."` or `'...'` | `"alice@example.com"` |
| Multi-line rules | Body on next line | `rule($x) IF\n    body($x)` |

### Arithmetic Comparisons

Rules support arithmetic comparisons that are evaluated during deduction:

```
# Stale access: users who haven't logged in for 90+ days
stale_access($user) IF
    user($user) AND last_login_days($user, $days) AND $days > 90

# Excessive permissions: more than 15 direct permissions
excessive_permissions($user, $count) IF
    user($user) AND permission_count($user, $count) AND $count > 15

# Clearance check: user clearance >= resource classification
can_access($user, $resource) IF
    user($user) AND resource($resource, _, _, _, _, $cls) AND
    classification($cls, $cls_level, _) AND
    user_clearance($user, $user_level) AND $user_level >= $cls_level
```

**Supported operators:** `>`, `>=`, `<`, `<=`, `==`, `is`, `!=`

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

### Conjunctions in Queries

Queries can combine multiple predicates:

```
? can_access_resource($who, $res) AND resource($res, _, _, _, _, secret)
```

This returns solutions where both conditions are satisfied simultaneously.

### Disjunction (OR)

Rule bodies can express alternatives with `OR`. The parser expands each
alternative into its own Horn clause at load time — the solver only ever
sees pure Horn clauses:

```
# A user can deploy when they are an admin, OR a dev on an approved env
can_deploy($u, $env) IF
    is_admin($u) OR
    (has_role($u, dev) AND env_approved($u, $env))
```

`AND` binds tighter than `OR`; parenthesized groups expand distributively.
`NOT` applies to single goals only. A `# RULE: <id>` is carried by every
expanded branch, so proofs stay auditable against the source rule.

## Why External Inference?

The external inference gives several advantages:
- deterministic
- explainable
- verifiable
- inexpensive
- replaceable backend

In the current implementation Euclid-MCP uses Prolog.  
Prolog is a 50-year-old battle-tested logic engine. Using it as a "deduction coprocessor" lets small LLMs perform complex multi-step reasoning without needing larger, more expensive models. The intermediate language strips away Prolog's syntax quirks while keeping its logical core.

A specific [benchmark](benchmarks/docs/02-rbac-at-scale.md) demonstrate the difference: with 1 000+ facts, LLMs alone score 2/5 while Euclid-MCP scores 5/5 — and runs 7× faster while outputting 14× fewer tokens.


## Tools

Euclid-MCP exposes **8 tools**, each with a specific purpose:

| Tool | Purpose |
|------|---------|
| `reason` | Main deduction — get solutions + proof trees |
| `explain` | Readable, natural-language reasoning steps |
| `diagnose` | Understand why a query succeeds or fails |
| `what_if` | Test modifications before applying them |
| `check_kb` | Validate KB consistency before reasoning |
| `register_kb` | Register a named KB under a `kb_id` |
| `unregister_kb` | Remove a named KB from the registry |
| `list_kbs` | List registered named KBs (metadata) |

### `reason`

Main tool for verifiable deterministic reasoning.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `knowledge` | `string?` | — | Facts & rules in text or YAML format |
| `kb_id` | `string?` | — | Reference a KB registered via `register_kb` |
| `delta_knowledge` | `string?` | — | Session-specific facts appended to the `kb_id` base |
| `query` | `string?` | — | Override query (optional) |
| `max_solutions` | `int` | `5` | Max solutions to return |
| `max_depth` | `int` | `30` | Max proof tree depth |

**Returns** `ReasonResult` with `solutions[]` — each containing variable bindings and a proof tree.

### `explain`

Deterministic proof-tree → natural-language reasoning steps. No LLM involved: it
walks the proof tree of each solution and renders every step in plain language,
citing the rule ID (`# RULE: <id>`) when a rule has one. Use it to turn a proof
into an auditable, human-readable explanation.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `knowledge` | `string?` | — | Facts & rules in text or YAML format |
| `kb_id` | `string?` | — | Reference a KB registered via `register_kb` |
| `delta_knowledge` | `string?` | — | Session-specific facts appended to the `kb_id` base |
| `query` | `string?` | — | Override query (optional) |
| `max_solutions` | `int` | `5` | Max solutions to return |
| `max_depth` | `int` | `30` | Max proof tree depth |

**Returns** `ExplanationResult` with `explanations[]` — each containing variable
bindings, an ordered list of natural-language `steps`, and language-independent
`structured_steps` (typed `kind`/`goal`/`rule_id`/`body`, ready for localized
rendering in a UI).

### `diagnose`

Query analysis — understand why a query succeeds or fails.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `knowledge` | `string?` | — | Facts & rules in text or YAML format |
| `kb_id` | `string?` | — | Reference a KB registered via `register_kb` |
| `delta_knowledge` | `string?` | — | Session-specific facts appended to the `kb_id` base |
| `query` | `string` | — | Query to diagnose |
| `mode` | `string` | `why` | One of: `why`, `why_not`, `what_needs` |
| `max_solutions` | `int` | `5` | Max solutions to return |
| `max_depth` | `int` | `30` | Max proof tree depth |

**Modes:**
- `why` — explain why a query holds (or that it doesn't)
- `why_not` — explain why a query fails (missing facts/rules)
- `what_needs` — suggest what would make a false query true

**Returns** `DiagnosisResult` with `holds`, `findings[]`, `conclusion`, and optionally `proof`.

### `what_if`

Scenario analysis — apply modifications to a knowledge base and compare results.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_knowledge` | `string?` | — | Base facts & rules |
| `kb_id` | `string?` | — | Reference a KB registered via `register_kb` |
| `delta_knowledge` | `string?` | — | Session-specific facts appended to the `kb_id` base |
| `modifications` | `string` | — | `+ fact(...)` to add, `- fact(...)` to remove |
| `query` | `string` | — | Query to evaluate |
| `max_solutions` | `int` | `5` | Max solutions to return |
| `max_depth` | `int` | `30` | Max proof tree depth |

**Returns** `WhatIfResult` with `before_count`, `after_count`, `delta`, `solutions_before`, `solutions_after`, `conclusion`.

### `check_kb`

Knowledge base validator — check for consistency before running deduction.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `knowledge` | `string?` | — | Facts & rules in text or YAML format |
| `kb_id` | `string?` | — | Reference a KB registered via `register_kb` |
| `delta_knowledge` | `string?` | — | Session-specific facts appended to the `kb_id` base |

**Returns** `KBCheckResult` with `valid`, `errors[]`, `warnings[]`, `facts_count`, `rules_count`, `predicates_count`, and `predicates[]` — the predicate inventory (name → arities, facts, rules counts) that doubles as the contract for LLM extraction.

#### KB identity in results

Every tool result — `ReasonResult`, `ExplanationResult`, `DiagnosisResult`,
`WhatIfResult`, and `KBCheckResult` — carries two identity fields:

| Field | Value |
|-------|-------|
| `content_hash` | sha256 of the **KB text payload** (the exact source that was reasoned over) |
| `version` | the `@version` directive of the KB, or `null` when absent |

The fields are present on **every** return path, including error branches, so a
result can always be pinned to the exact KB it was computed from: anyone with
the `.euclid` text and Euclid-MCP can recompute the hash and verify it. This is
the foundation for KB versioning, signatures, and audit trails built on top of
the engine.

```json
{
  "query": "mortal($who)",
  "solutions": [...],
  "elapsed_ms": 12.4,
  "content_hash": "a3f9c1e4b82d55f0…",
  "version": "1.0"
}
```


#### KB Preload

A knowledge base can be loaded **once at server startup** and reused across
calls, so agents only pass the session-specific facts for the current query.

Preload a KB by file path, via the `EUCLID_KB_PATH` environment variable or a
`--kb-path` CLI flag:

```bash
# Environment variable
EUCLID_KB_PATH=/path/to/policies.euclid python3 -m euclid_mcp

# CLI flag (MCP stdio, console script, and HTTP API)
python3 -m euclid_mcp --kb-path /path/to/policies.euclid
python3 integrations/euclid_api.py --kb-path /path/to/policies.euclid --port 8080
```

Behavior:

- The file is **validated with `check_kb` at startup** and the server fails fast
  with a clear message if the file is missing, unreadable, oversized, or invalid.
- `knowledge`/`base_knowledge` on `reason`, `explain`, `diagnose`, `what_if`, and
  `check_kb` become **optional**: an explicit value always wins, an empty value
  falls back to the preloaded KB. With neither, tools return a clear
  "No knowledge provided" error.
- A **markdown digest** of the preloaded KB (fact/rule/predicate counts, predicate
  inventory, rules with their IDs) is appended to the server instructions, so
  agents can see what the KB covers without extra tool calls.

Backward compatible: passing `knowledge` explicitly behaves exactly as before.


#### Named KBs (`kb_id` + `delta_knowledge`)

A KB can also be **registered once under a `kb_id`** and then referenced on
every call without resending the text — the in-memory registry is per
server instance, so replicas re-register their KBs on startup (matching the
scale-out model of the HTTP API). Up to 32 KBs per instance; `register_kb`
overwrites an existing `kb_id` (update semantics for idempotency).

```python
# Register once — validated with check_kb first
register_kb(kb_id="rbac-policy", knowledge="has_role(alice, admin) ...\n? $role ...")

# Reference it on every call
result = reason(kb_id="rbac-policy", query="can_deploy($user, prod)")

# Session-specific facts on top of the registered base (no re-registration):
result = reason(
    kb_id="rbac-policy",
    delta_knowledge="has_role(alice, dev)\nhas_env(dev, staging)",
    query="can_deploy($user, staging)",
)
```

- `register_kb(kb_id, knowledge)` — validates the `kb_id` (allowlist
  `[a-z0-9_-]{1,64}`) and the KB (`check_kb`), then stores it. Returns the
  record: `registered`, `kb_id`, `content_hash`, `version`, `facts`, `rules`,
  `predicates`. Unknown ids are rejected; a full registry returns an error.
- `unregister_kb(kb_id)` — removes the KB; returns `removed: true/false`.
- `list_kbs()` — lists registered KBs (metadata only, no source text).

**Resolution precedence** on `reason`, `explain`, `diagnose`, `what_if`,
`check_kb`: explicit `knowledge`/`base_knowledge` wins → else `kb_id`
(unknown id → `Unknown kb_id: <id>`; `delta_knowledge` is concatenated to the
registered source) → else the `EUCLID_KB_PATH` preload → else a clear
"No knowledge provided" error. `delta_knowledge` without a `kb_id` is an
error. `content_hash`/`version` on a `kb_id` result are computed from the
effective source (base + delta), so a result can always be pinned to the
exact text reasoned over.

The HTTP API exposes the same flow as `POST /register-kb`,
`POST /unregister-kb`, and `POST /list-kbs`.


## Installation

### pip

```bash
# Prerequisite: Python ≥ 3.10

# SWI-Prolog (for better performances)
brew install swi-prolog

# Install
pip install euclid-mcp
```

### From source

```bash
git clone https://github.com/Euclid-BG/Euclid-MCP
cd Euclid-MCP
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

### Docker

No local SWI-Prolog installation needed — the image bundles everything.

```bash
# Build
docker build -t euclid-mcp .

# MCP stdio mode (for local MCP clients)
docker compose run --rm euclid-mcp

# HTTP API mode (for n8n, Zapier, remote access)
docker compose up euclid-api
# API available at http://localhost:8080
```

See [Docker in Integrations](#docker) for full details.

## Usage

### Via MCP (OpenCode, Claude, etc.)

```json
{
  "mcpServers": {
    "euclid-mcp": {
      "command": "python3",
      "args": ["-m", "euclid_mcp"],
      "cwd": "/path/to/euclid-mcp"
    }
  }
}
```

### Via Python

```python
from euclid_mcp.server import reason, explain, diagnose, what_if, check_kb

# Reasoning
result = reason(knowledge="""
    human(socrates)
    mortal($x) IF human($x)
    ? mortal($who)
""")
for sol in result.solutions:
    print(sol.substitutions, sol.proof.type)

# Explanation — readable reasoning steps (cites rule IDs when present)
expl = explain(
    knowledge="human(socrates)\nmortal($x) IF human($x)  # RULE: BIO-001",
    query="mortal($who)"
)
for e in expl.explanations:
    print(e.substitutions, e.steps)
    print(e.structured_steps)  # typed, language-independent steps

# Diagnosis — why does a query fail?
diag = diagnose(
    knowledge="human(socrates)\nmortal($x) IF human($x)",
    query="mortal(plato)",
    mode="why_not"
)
print(diag.conclusion)

# What-if — how does adding a fact change results?
scenario = what_if(
    base_knowledge="human(socrates)\nmortal($x) IF human($x)",
    modifications="+ human(plato)",
    query="mortal($who)"
)
print(f"Before: {scenario.before_count}, After: {scenario.after_count}")

# KB validation
check = check_kb(knowledge="human(socrates)\nmortal($x) IF human($x)")
print(f"Valid: {check.valid}, Errors: {check.errors}")
```

### Via CLI

The `euclid-cli` command wraps the five reasoning tools (`reason`, `explain`,
`diagnose`, `what_if`, `check_kb`) for the terminal. It reads
the KB from a `.euclid` file (`-f`), inline (`--knowledge`), or falls back to
`EUCLID_KB_PATH`/preload, and selects the backend with `--backend`
(`auto` | `prolog` | `native`). Queries come from `--query` or from the `?`
lines inside the KB file.

Run with **no subcommand** to open an interactive **Euclid-IR REPL** — type
facts, rules and `? query` lines directly, like you would in `swipl` or
`psql`. The session knowledge base accumulates across queries.

```bash
$ euclid-cli
Euclid-MCP REPL — type facts and rules in Euclid-IR, then `? query`.
Commands: :help  :check  :kb  :load  :explain  :diagnose  :what-if  :reset  :quit

euclid > human(socrates)
euclid > mortal($x) IF human($x)
euclid > ? mortal($who)
Query: mortal($who)
Solution 1:
  who: socrates
mortal(socrates)  [rule]
  human(socrates)  [fact]

euclid > :what-if + human(plato)
Solutions: 1 -> 2 (delta: more)
euclid > :quit
```

REPL meta-commands: `:check`, `:kb`, `:load <file>`, `:explain [query]`,
`:diagnose <query> [why|why_not|what_needs]`, `:what-if <mods>`, `:reset`,
`:quit`. Multi-line rules continue after `IF`/`AND` (prompt becomes `... >`).
Piped input runs the same loop as a batch script without prompts:

```bash
printf 'human(socrates)\nmortal($x) IF human($x)\n? mortal($who)\n' | euclid-cli
```

```bash
# Validate a knowledge base
euclid-cli check -f policies.euclid

# Run a deduction (query taken from the ? line in the file)
euclid-cli reason -f policies.euclid

# Explicit query + limits
euclid-cli reason -f policies.euclid --query "can_deploy($user, prod)" \
    --max-solutions 10 --max-depth 40

# Inline KB (no file)
euclid-cli reason --knowledge "human(socrates)
mortal(\$x) IF human(\$x)
? mortal(\$who)"

# Readable reasoning steps
euclid-cli explain -f policies.euclid

# Why does a query fail?
euclid-cli diagnose -f policies.euclid --query "can_deploy(bob, prod)" \
    --mode why_not

# What-if: how does adding a fact change the answer?
euclid-cli what-if -f policies.euclid \
    --modifications "+ has_role(bob, deployer)" --query "can_deploy(bob, prod)"

# Force the pure-Python native engine (no SWI-Prolog)
euclid-cli --backend native reason -f policies.euclid

# Machine-readable output
euclid-cli reason -f policies.euclid --json
```

Exit codes: `0` on success, `1` when the tool reports an error (including an
invalid KB from `check`), `2` on usage errors.

Full CLI reference (all flags, backends, JSON output): [`docs/CLI.md`](docs/CLI.md)

### Example output

```json
{
  "query": "ancestor(tom, $who)",
  "solutions": [
    {
      "substitutions": {"who": "bob"},
      "proof": {
        "type": "rule",
        "goal": "ancestor(tom, bob)",
        "body": "parent(tom, bob)",
        "rule_id": "GEN-1",
        "subproof": {"type": "fact", "goal": "parent(tom, bob)"}
      }
    },
    {
      "substitutions": {"who": "ann"},
      "proof": {
        "type": "rule",
        "goal": "ancestor(tom, ann)",
        "body": "parent(tom, bob), ancestor(bob, ann)",
        "rule_id": "GEN-2",
        "subproof": {
          "type": "and",
          "left": {"type": "fact", "goal": "parent(tom, bob)"},
          "right": {
            "type": "rule",
            "goal": "ancestor(bob, ann)",
            "body": "parent(bob, ann)",
            "rule_id": "GEN-1",
            "subproof": {"type": "fact", "goal": "parent(bob, ann)"}
          }
        }
      }
    }
  ]
}
```

Rules can carry an audit-trail ID via a trailing `# RULE: <id>` comment; the ID
is surfaced as `rule_id` on the `rule` nodes of the proof tree, so a decision
can be cited ("this derives from rule GEN-2").

#### Diagnose output

```json
{
  "query": "mortal(plato)",
  "mode": "why_not",
  "holds": false,
  "findings": [
    {
      "type": "satisfied",
      "predicate": "human",
      "detail": "Facts exist for 'human' (1 facts)"
    }
  ],
  "conclusion": "The query fails. Check rule conditions."
}
```

#### What-if output

```json
{
  "query": "mortal($who)",
  "modifications": "+ human(plato)",
  "before_count": 1,
  "after_count": 2,
  "delta": "more",
  "solutions_before": [{"substitutions": {"who": "socrates"}}],
  "solutions_after": [
    {"substitutions": {"who": "plato"}},
    {"substitutions": {"who": "socrates"}}
  ],
  "conclusion": "Solutions increased: 1 -> 2."
}
```

#### Explain output

```json
{
  "query": "mortal($who)",
  "explanations": [
    {
      "substitutions": {"who": "socrates"},
      "steps": [
        "mortal(socrates) is derived by rule BIO-001 from: human(socrates).",
        "human(socrates) is asserted as a fact in the knowledge base."
      ]
    }
  ]
}
```


## Use cases

- **Small LLM reasoning**: Offload deduction from LLMs (3-8B) to a deterministic engine
- **Explainable decisions**: Every answer comes with a proof tree which allows explanation, reasoning trace, and justification
- **Business rules**: Validate logic chains (permissions, workflows, compliance)
- **Dependency analysis**: Circular dependency detection, topological ordering
- **Education**: Interactive logic tutoring with visible proof chains (see [`docs/DIDACTIC.md`](docs/DIDACTIC.md), a step-by-step teaching guide built around the `euclid-cli` REPL)
- **Knowledge preload**: Complex business rules can be loaded in Euclid instead of using a vector database
- **Query diagnosis**: Understand why queries fail and what facts/rules are missing
- **Scenario analysis**: Test "what-if" modifications before applying them to production
- **KB validation**: Check knowledge bases for consistency before reasoning


### Real-world examples

There are several examples provided as samples: Genealogy, RBAC, Classification, Loan Eligibility,
Cluedo Detective, IT Security & Compliance, LLM vs Euclid-MCP, ...
Most interesting ones are the **IT Security & Compliance** (with
CIS, AWS, IAM Standards enforcement, Company Policies implementation, hundreds of Data Facts)
and side-by-side **LLM vs Euclid-MCP**.

Examples full description: [`docs/EXAMPLES.md`](docs/EXAMPLES.md)


## Integrations

### OpenCode

Euclid-MCP includes a pre-configured agent in `.opencode.json`:

```json
{
  "mcpServers": {
    "euclid-mcp": {
      "command": "python3",
      "args": ["-m", "euclid_mcp"],
      "cwd": "."
    }
  },
  "agents": {
    "reasoning-engine": {
      "description": "Deterministic logic engine",
      "instructions": "Write facts in Euclid IR, use the reason tool...",
      "mcpServers": ["euclid-mcp"]
    }
  }
}
```

### n8n / Zapier / Make

Run the HTTP API:

```bash
python3 integrations/euclid_api.py --port 8080
```

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/reason` | POST | Deduction with proof trees |
| `/explain` | POST | Natural-language reasoning steps |
| `/diagnose` | POST | Query failure analysis |
| `/what-if` | POST | Scenario testing |
| `/check-kb` | POST | KB validation |
| `/register-kb` | POST | Register a named KB (`kb_id`) |
| `/unregister-kb` | POST | Remove a named KB |
| `/list-kbs` | POST | List registered named KBs |
| `/health` | GET | Health check (deep: pings the engine; 503 only when wedged) |
| `/metrics` | GET | Prometheus metrics (open, read-only, never KB content) |

```bash
# Reasoning
curl -X POST http://localhost:8080/reason \
  -H "Content-Type: application/json" \
  -d '{"knowledge": "human(socrates)\nmortal($x) IF human($x)\n? mortal($who)"}'

# Explanation
curl -X POST http://localhost:8080/explain \
  -H "Content-Type: application/json" \
  -d '{"knowledge": "human(socrates)\nmortal($x) IF human($x)\n? mortal($who)"}'

# Diagnosis
curl -X POST http://localhost:8080/diagnose \
  -H "Content-Type: application/json" \
  -d '{"knowledge": "human(socrates)\nmortal($x) IF human($x)", "query": "mortal(plato)", "mode": "why_not"}'

# What-if
curl -X POST http://localhost:8080/what-if \
  -H "Content-Type: application/json" \
  -d '{"base_knowledge": "human(socrates)\nmortal($x) IF human($x)", "modifications": "+ human(plato)", "query": "mortal($who)"}'

# KB validation
curl -X POST http://localhost:8080/check-kb \
  -H "Content-Type: application/json" \
  -d '{"knowledge": "human(socrates)\nmortal($x) IF human($x)"}'

# Register a named KB once, then reference it by kb_id
curl -X POST http://localhost:8080/register-kb \
  -H "Content-Type: application/json" \
  -d '{"kb_id": "rbac", "knowledge": "human(socrates)\nmortal($x) IF human($x)"}'

curl -X POST http://localhost:8080/reason \
  -H "Content-Type: application/json" \
  -d '{"kb_id": "rbac", "delta_knowledge": "human(plato)", "query": "mortal($who)"}'

curl -X POST http://localhost:8080/list-kbs \
  -H "Content-Type: application/json" \
  -d '{}'

curl -X POST http://localhost:8080/unregister-kb \
  -H "Content-Type: application/json" \
  -d '{"kb_id": "rbac"}'
```

### Docker

The Docker image bundles SWI-Prolog + Python, so no local prerequisites are needed.
Base image: [`swipl:stable`](https://hub.docker.com/_/swipl) (Debian Bookworm).

**Two modes via docker-compose:**

```bash
# MCP stdio — pipe to a local MCP client
docker compose run --rm euclid-mcp

# HTTP API — expose REST endpoints on port 8080
docker compose up euclid-api
```

**Standalone usage:**

```bash
# Build
docker build -t euclid-mcp .

# Run HTTP API
docker run --rm -p 8080:8080 euclid-mcp \
  python3 integrations/euclid_api.py --port 8080

# Run MCP stdio (interactive)
docker run --rm -i euclid-mcp

# Quick test — reason directly from CLI
docker run --rm euclid-mcp python3 -c "
from euclid_mcp.server import reason
r = reason(knowledge='human(socrates)\nmortal(\$x) IF human(\$x)\n? mortal(\$who)')
print(r.solutions[0].substitutions)
"
```

**Docker image size:** ~370 MB (SWI-Prolog + Python 3.11 + dependencies).

**Native-only (slim):** a smaller image with the pure-Python Euclid-IR engine
and no SWI-Prolog (`EUCLID_BACKEND=native`). Best for containers with limited
space or as the default for small knowledge bases.

```bash
# Build
docker build -f Dockerfile.native -t euclid-mcp-native .

# Run MCP stdio (interactive)
docker compose run --rm euclid-mcp-native

# Run HTTP API
docker run --rm -p 8080:8080 euclid-mcp-native \
  python3 integrations/euclid_api.py --port 8080

# Quick test — reason directly from CLI
docker run --rm euclid-mcp-native python3 -c "
from euclid_mcp.server import reason
r = reason(knowledge='human(socrates)\nmortal(\$x) IF human(\$x)\n? mortal(\$who)')
print(r.solutions[0].substitutions)
"
```

Base image: [`python:3.12-slim`](https://hub.docker.com/_/python).

### CLI pipeline

```bash
echo '{"knowledge": "red(apple)\\n? red($x)"}' | python3 integrations/euclid_cli.py
```

See `integrations/README.md` for full details.


## Scalability

Euclid-MCP engine is **persistent**: a single long-lived SWI-Prolog
process per server instance, reloaded per request over a JSON-lines pipe
instead of booting Prolog for every call. 
A single instance handles one request at a time.
Requests stay **stateless**: 
each one brings its own knowledge base (or uses the preloaded one), 
so instances share nothing.

This makes Euclid-MCP horizontally scalable:

- **HTTP API** — run any number of instances behind a load balancer (nginx, a
  Kubernetes Service, …). No session affinity needed: any instance can serve any
  request.
- **MCP stdio** — each MCP client spawns its own instance by design, giving
  natural isolation and parallelism across clients.
- **Resource footprint** — one `swipl` process per instance (~tens of MB)
  instead of one short-lived process per request, so a single instance serves
  many requests cheaply.

Reference production architecture — load balancing, resource limits, security
hardening, and monitoring for a replica battery behind HAProxy:
[`docs/PRODUCTION.md`](docs/PRODUCTION.md).


## Development

Requirements: Python ≥ 3.10, SWI-Prolog.

```bash
# Install in editable mode with dev dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Lint
ruff check .

# Type check
mypy euclid_mcp integrations

# Tests with coverage
pytest --cov=euclid_mcp --cov=integrations
```

The CI workflow ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs these
same checks on push and pull request, across Python 3.10–3.14.

### Logging & tracing

Every tool call is logged with its name, elapsed time, and outcome. Enable
structured logs by setting `EUCLID_LOG_LEVEL` (one of `DEBUG`, `INFO`,
`WARNING`, `ERROR`, `CRITICAL`) — e.g. `EUCLID_LOG_LEVEL=INFO`. Without the
variable, only warnings and errors are emitted.

The HTTP API also supports request tracing: send an `X-Request-Id` header and
it is echoed back on the response and included in the access logs.

### Monitoring & metrics

The HTTP API exposes Prometheus metrics on `GET /metrics` (open, read-only,
never carries KB content): per-tool call/error counters and latency
histograms, engine requests/restarts/timeouts, HTTP traffic, solutions
returned, auth failures and process uptime — always on, zero dependencies
(`euclid_mcp/metrics.py`). `GET /health` is a deep check that pings the
engine and reports its workspace stats (503 only when a wedged engine exists).

```bash
curl -s localhost:8080/metrics
```

For a full stack (Prometheus + Grafana + cAdvisor, dashboard and alert rules
included): `monitoring/README.md`.


## What is Prolog?

[**Prolog**](https://en.wikipedia.org/wiki/Prolog) (from *PROgrammation en
LOGique*) is a declarative logic programming
language: instead of telling the machine *how* to compute an answer, you state
**facts** and **rules** and let it find *what* follows from them, using
unification and backtracking. Born in the early 1970s, it remains one of the
most battle-tested tools for symbolic reasoning.

![SWI-Prolog](docs/swipl.png)

Euclid-MCP uses **[SWI-Prolog](https://www.swi-prolog.org/)** as its inference
engine. SWI-Prolog is a mature
**open-source** implementation — continuously developed and freely available
since 1987 — widely used in industry, academia, and research. You write
your rules in Euclid-IR; the translator compiles them to Prolog, and SWI-Prolog
performs the deduction and produces the proof trees that make every Euclid-MCP
answer verifiable.


## How is Euclid?

**Euclid** was an ancient Greek mathematician. Living and teaching in Alexandria, he built the foundations of geometry and number theory using rigorous logical proofs.

**Euclid-MCP** is not:
- an LLM
- a knowledge base
- a vector database
- an agent framework
- a planner

**Euclid-MCP** is a deterministic inference engine that can be used by any of them.  
Euclid-MCP allows deterministic and explainable replies from small LLMs on Edge hardware too.


## License

Apache 2.0

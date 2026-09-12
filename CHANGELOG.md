# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.5.0] — 2026-09-12

### Added
- **Disjunction (OR) in rule bodies** —
  `can($u) IF is_admin($u) OR has_role($u, auditor)` is expanded into one
  pure Horn clause per alternative at parse time, so both backends keep
  reasoning over Horn clauses only. `AND` binds tighter than `OR`;
  parenthesized groups `(a OR b) AND c` expand distributively; `NOT (group)`
  is rejected with a clear parse error. A `# RULE: <id>` is carried by every
  expanded branch (auditable proofs), `rules_count` counts the expanded
  clauses while `content_hash` stays tied to the source text, multi-line
  `OR` bodies are supported, and the LSP parser tracks them.
- **Project landing page** — `website/index.html`, deployed to GitHub Pages
  via `.github/workflows/pages.yml`: a single-page site covering the why,
  the architecture, an Euclid-IR tour, the eight tools, the KB lifecycle,
  live demo GIFs, benchmarks and quickstart.
- **Demo GIFs** — three recorded `euclid-cli` sessions embedded in the
  landing page's Demo section (`website/assets/demo/`): multi-hop RBAC with
  proof tree, diagnose + what-if on a denied deploy, and negation as failure
  citing rule SEC-042. `diagnose.gif` is showcased on the landing page; the
  README embed of it was removed.

### Changed
- **Landing-page flow** — nav and sections reordered to follow the visitor
  funnel: Why → Quickstart → How it works → Euclid-IR → Tools → Demo →
  Benchmarks (KB lifecycle stays tool-adjacent; use cases close the page).
- **docs/DIDACTIC.md** — meta-interpreter comments realigned with the code;
  historical note on the syllogism added.
- **docs/CLI.md** — CLI and REPL acronyms spelled out at first use.
- **Zenodo metadata** — creator recorded with the full author name.

## [0.4.6] — 2026-08-23

### Fixed
- **Backend divergence on `true`/`false` body literals** — `pred($x) IF false`
  crashed the SWI-Prolog backend with an opaque `engine_error`: the
  meta-interpreter had no branch for the literal, so it reached `clause/2`,
  and SWI-Prolog 10 raises `permission_error(access, private_procedure,
  fail/0)` over the built-in `false`/`fail`; the engine loop's catch-all
  discarded the message. The native engine failed cleanly, so the same KB
  behaved differently per backend — and `IF true` was divergent in the other
  direction (succeeded on Prolog, failed natively). Both engines now give the
  literals explicit, identical semantics: `IF false` never proves, `IF true`
  proves like a fact (proof node `fact`, or `rule` when the rule carries an
  ID). This makes `IF false` the legitimate spelling for vocabulary
  declarations in rules-only KBs.
- **Backend divergence on unbound query variables** — solutions from
  non-range-restricted rules (a head variable absent from the body, e.g.
  `report($user) IF system_compromised`, or negation over an empty declared
  predicate with a variable goal) were dropped by the native engine and
  stringified as SWI fresh tokens (`_28498`) — or lost entirely — by
  SWI-Prolog. Both engines now keep the solution and surface unbound query
  variables as explicit `null` bindings (`{"any": null}`). Proof trees are
  also aligned: SWI's nondeterministic fresh-variable names are normalized
  to the Euclid-IR wildcard `_` (quoted literals masked, so user data is
  never rewritten), making proof trees byte-identical across backends and
  across runs.
- **Built-in body goals raised instead of failing** — a rule body naming any
  SWI-Prolog built-in (e.g. `atom_length`) hit `clause/2` and surfaced as an
  opaque `engine_error`. Both meta-interpreter branches now carry a
  `\+ predicate_property(Goal, built_in)` guard: since user clauses can never
  exist for a built-in, the goal fails cleanly — matching the native engine,
  where unknown predicates simply fail.
- **Zero-arity predicates leaked across engine loads** — `_extract_pred_sig`
  required parentheses, so bare statements (`rainy`, or a `t IF true` head)
  were never declared dynamic nor registered in the persistent engine's
  workspace; their clauses survived `clear_workspace` and duplicated on every
  subsequent load, silently multiplying solutions. Bare atoms now produce a
  `/0` signature. Parity tests pin single-solution behavior across reloads.
- **Backend divergence on non-ASCII variables** — `$città`, `$кто` and any
  other Unicode variable now behave identically on both backends. The
  variable-name pattern (`language.VAR_NAME_RE`, single source of truth for
  the native parser, the Prolog translator and the linter) accepts Unicode
  letters, and the translator masks variables (`__VAR_name__`) during
  atom-quoting so they can never be wrapped into quoted atoms. Previously
  the native engine raised a parse error while SWI-Prolog silently
  truncated the name (or quoted it into an atom that unified with nothing).
- **NFC normalization at every entry point** — `parse()` normalizes KB text
  and `strip_query_prefix()` normalizes explicit queries to NFC, so
  decomposed (NFD) spellings unify symmetrically on both backends instead
  of failing on the native engine and matching only byte-identical forms
  on SWI-Prolog.
- **`--backend` flag silently discarded an exported `EUCLID_BACKEND`** — the
  CLI wrote the flag's default (`auto`) into the environment on every run,
  so `EUCLID_BACKEND=native euclid-cli` still launched SWI-Prolog. The flag
  is now applied only when explicitly passed: an exported value is honored,
  and an explicit `--backend` wins over it.
- **Multi-line rules with leading `AND` split into garbage statements** — a
  rule continued with the conjunction at the START of each line (the common
  Prolog habit) was cut at its first complete body goal, while the leftover
  `AND ...` lines were accepted as facts by the lenient language parser and
  then rejected at runtime by both engines. The parser now absorbs
  AND-leading continuation lines (and rejects orphan ones with a clear
  message), and the interactive REPL holds a completed rule until the next
  input settles whether a continuation follows. Continuation detection is
  buffer-aware: a line trails the open statement when the buffered text ends
  with `IF`/`AND` or the line itself opens with `AND`, so trailing-style and
  leading-style multi-line rules both work in files, seeded KBs and live
  sessions (previously a continuation line without an inner `IF`, e.g.
  `$y is $x - 1 AND`, was flushed as its own statement).
- **`:check` could stay green on statements the engines refuse** —
  validation relied only on the lenient parser while both backends re-parse
  every statement with the strict term parser. `run_check_kb` now runs each
  fact, rule and the query through that same parser, so a green check
  guarantees the KB loads and queries on either backend.
- **REPL errors vanished into stderr** — engine and parse errors printed
  only a terse message to stderr, easy to lose next to the tool-call log
  lines (and invisible in piped sessions). They now print to stdout.
- **String literals bind bare values on both backends** — IR quoted values
  are translated to single-quoted Prolog *atoms* instead of SWI string
  terms; bindings are now identical to the native engine's bare content
  (e.g. `müller`, not `"müller"`). Operators inside literals were already
  inert data and remain so.

### Changed
- **REPL banner renamed** — `Euclid-MCP REPL …` → `Euclid-IR REPL vX.Y.Z —
  type facts and rules, then `? query`.`. The REPL calls the tool functions
  in-process; no MCP server or protocol is involved, so the banner now names
  the language. The version comes from the in-tree package constant (with a
  new drift test against `pyproject.toml`), not from possibly stale install
  metadata.

### Added
- **Reserved boolean keywords** — `true` / `false` join `if`, `and`, `not`,
  `is` as reserved words: rejected as predicate names, bare facts and rule
  heads with a clear message (previously such KBs broke the Prolog load with
  the same opaque error). As *arguments* they remain plain atom data.
- **Vocabulary-declaration idiom documented** — `docs/EUCLID_IR.md` documents
  the `true`/`false` literals and the load-once/query-many pattern where a
  rules-only stable layer declares its input vocabulary with `IF false`
  bodies (validated green by `check_kb`, zero inference impact); the PCI-DSS
  sample was migrated from the `IF 1 > 2` workaround.
- `prova_unicode.py` / `divergenze.py` — Unicode conformance suite and
  backend-divergence isolator used to pin the fixes above.
- `tests/test_true_false_literals.py` — backend-parity suite for the boolean
  literals, negation over declared predicates, clean built-in failure, the
  zero-arity reload regression, and the end-to-end vocabulary +
  `delta_knowledge` flow.
- `tests/test_unbound_variables.py` — backend-parity suite for unbound query
  variables: explicit `null` bindings, cross-backend proof-tree identity,
  run-to-run determinism, and quoted-data safety of the wildcard
  normalization.
- `tests/test_multiline_continuations.py` — AND-leading rule continuations
  in parser and REPL, plus stdout visibility of engine errors.
- `tests/test_check_kb_engine_alignment.py` — statements the engines reject
  are flagged at check time; unicode/quoted KBs stay green.
- `tests/test_backend_precedence.py` — `EUCLID_BACKEND` survives a run
  without `--backend`; an explicit flag overrides it.
- `tests/test_version.py` — package version matches `pyproject.toml`.
- REPL: `:kb` listing gained a paste-safe counts header (`# session KB: N
  facts, M rules`) and the help documents the hidden `:list` alias.

## [0.4.5] — 2026-08-22

### Added
- **Unicode atoms in the native engine** — the pure-Python lexer
  (`euclid_mcp/ir_parser.py`) now accepts Unicode predicate/atom names
  (`父(张三)`, `смертный($x)`, `Бог(Иван)`), closing the last documented gap
  with SWI-Prolog (see `docs/NATIVE_ENGINE.md`). Numbers stay ASCII (`0-9`),
  so Unicode digits are read as name characters, and variables remain ASCII
  (`$name`) per the Euclid-IR spec — identical on both backends.
- **Added examples 09 and 11** - a **Turing machine** in pure Euclid-IR
  demonstrating Turing-completeness of the language and
  a **Certainty factors implementation** with MYCIN-style scoring and exact dyadic
  arithmetic.

### Changed
- **Unicode parity tests** — `test_reason_tool_unicode` and
  `test_what_if_unicode` in `tests/test_unicode_atoms.py` lost their
  `prolog_only` marker and now run on both backends; the two
  `native_only` rejection tests were removed together with the limitation.
  New native-engine-level Unicode tests live in `tests/test_native_engine.py`
  (predicates, args, rules with rule IDs, negation, case sensitivity).

### Fixed
- **Native engine crashed on division by zero** — `$x is 1 / 0` raised an
  uncaught `ZeroDivisionError` that escaped the tool layer (which only
  catches `RuntimeError`), crashing the `reason` call instead of returning
  an error result. The native evaluator now raises a clean
  "Arithmetic error: division by zero", matching the Prolog backend's
  `engine_error`. A deep proof that exhausts the Python stack is likewise
  converted into a clear error asking to lower `max_depth`.
- **Native parser silently split malformed numeric literals** — the lexer
  read only the leading decimal part of unsupported literal forms
  (`1e3`, `0x10`, `1_000`, `12abc`) and the argument parser tolerated
  missing commas, so e.g. `n(1e3)` silently became the arity-2 term
  `n(1, e3)` and queries failed with zero solutions and no error. Both are
  now explicit parse errors; `p(1-2)` is rejected too instead of parsing as
  `p(1, -2)` (see `docs/NATIVE_ENGINE.md`). Regression tests in
  `tests/test_native_engine.py`.
- **Preloaded-KB digest dropped Unicode predicates** — the predicate regex in
  `euclid_mcp/kb_summary.py` was ASCII-lowercase-only, so a preloaded KB with
  e.g. `Бог(Иван)` omitted that predicate from the server-instructions digest.
- **Prolog engine crashed on compound-term bindings** — a query variable bound
  to a nested compound term (e.g. a structured state) made `json_write/3`
  raise `type_error(json_term, ...)`, surfaced only as an opaque
  `engine_error`. Both snippet generators now route every binding through a
  new `euclid_json_value/2` engine helper: atoms become strings, numbers pass
  through, other terms are rendered via `term_string/2` — matching how the
  native engine already renders compound bindings. Regression test in
  `tests/test_prolog_bridge.py`.
- **Spurious arity warnings/circular-rule errors on nested-compound KBs** —
  `check_kb` counted *all* commas in a predicate's argument list, so nested
  compounds (`cfg(run, tape(cell(1, blank)))`) reported inflated arities and
  triggered false `inconsistent_arity` warnings. Arity counting is now
  depth- and quote-aware (shared `_arity` helper in `euclid_mcp/validation.py`,
  also used by the preloaded-KB digest). Additionally, the circular-rule check
  now accepts a variable-bearing **fact** as a legitimate base case for a
  recursive rule (e.g. `final(cfg(done, $t), cfg(done, $t))`).

## [0.4.4] — 2026-08-18

### Added
- **LSP server for Euclid-IR** — `euclid-lsp/`: a full Language Server Protocol
  implementation using pygls v2. Features: real-time diagnostics (parse errors,
  undefined predicates, circular rules), autocomplete (predicates, keywords,
  operators, snippets), and hover (predicate info with fact/rule counts).
  Includes a positioned parser that tracks line/column for every fact, rule, and
  query.
- **VS Code extension** — `euclid-lsp/vscode/`: syntax highlighting via
  TextMate grammar, language configuration (comments, brackets, folding), and
  LSP client integration. Install with `code --install-extension`.
- **Sublime Text plugin** — `euclid-lsp/sublime-text/`: Euclid-IR syntax
  support for Sublime Text.
- **LSP documentation** — `docs/LSP.md`: full LSP server documentation,
  OpenCode configuration, and editor setup guides.
- **Didactic cut-operator section** — `docs/DIDACTIC.md` gained a "Pro Tip"
  section explaining Prolog's cut operator (`!`), why Euclid-IR omits it,
  and a commented pseudo-implementation for reference.
- **Improved example coverage** — `examples/00_basics/hello.euclid` and
  `examples/04a_simple_policy/simple_access.euclid` added; IT Security
  Compliance example 07 gained `--mode explain` with rule ID citations.

### Fixed
- **prolog_engine.pl included in wheel** — `package-data` in `pyproject.toml`
  now includes `*.pl`, so the Prolog engine file is bundled in the wheel and
  installed correctly via `pip install euclid-mcp`.
- **server.json indentation** — corrected inconsistent indentation in the
  package version field.
- **uv.lock updated for euclid-lsp** — lockfile now includes the euclid-lsp
  workspace member and its dependencies.
- **Sublime Text excluded from ruff** — `euclid-lsp/sublime-text` added to
  ruff's `exclude` list to avoid linting non-Python plugin files.
- **CI installs workspace packages** — `uv sync` now uses `--all-packages` to
  install all workspace members (euclid-lsp) in CI, resolving missing test
  dependencies.

### Changed
- **CI actions upgraded** — `actions/checkout` v5→v7, `actions/setup-python`
  v6→v7, `codecov/codecov-action` v6→v7, `astral-sh/setup-uv` pinned to
  v10.0.1 (replacing v6 to resolve Node.js 20 deprecation warnings).

## [0.4.3] — 2026-08-16

### Added
- **Native-only Docker image** — `Dockerfile.native`: a slim image on
  `python:3.12-slim` (no SWI-Prolog installed) that runs the pure-Python
  Euclid-IR engine (`EUCLID_BACKEND=native`) for MCP stdio, HTTP API and CLI
  use. Compose service `euclid-mcp-native`. Docs: README "Docker".
- **Didactic guide** — `docs/DIDACTIC.md` (12 chapters): a tutorial-style walk
  from Euclid-IR facts and rules to proof trees and the `euclid-cli` REPL,
  closing with the chapter "Beyond the 1:1 mapping: the audit layer" on the
  elements that go beyond a plain Prolog subset (rule IDs, `content_hash`/
  `version`, `structured_steps`, backend dispatch). Reference links to the
  SWI-Prolog documentation at first mention.
- **LSP server** — `euclid-lsp/`: a full Language Server Protocol
  implementation for Euclid-IR using pygls v2. Features: real-time
  diagnostics (parse errors, undefined predicates, circular rules),
  autocomplete (predicates, keywords, operators, snippets), and hover
  (predicate info with fact/rule counts). Includes a positioned parser that
  tracks line/column for every fact, rule, and query.
- **VS Code extension** — `euclid-lsp/vscode/`: syntax highlighting via
  TextMate grammar, language configuration (comments, brackets, folding),
  and LSP client integration. Install with `code --install-extension`.
- **Shared validation module** — `euclid_mcp/validation.py`: KB validation
  logic extracted from `server.py` and shared by both the MCP server and the
  LSP server. Public API: `run_check_kb()`.
- **New examples** — `examples/00_basics/hello.euclid` (hello world) and
  `examples/04a_simple_policy/simple_access.euclid` (intermediate example
  covering all Euclid-IR features: `@version`, `//`, strings, `NOT`,
  arithmetic, wildcards, rule IDs, conjunction queries).

### Fixed
- **CI never ran the native backend** — the matrix installed `swi-prolog` but
  never set `EUCLID_BACKEND`, so `auto` always picked Prolog and native-only
  tests were silently skipped. The matrix now includes an explicit
  `EUCLID_BACKEND=native` leg on every push/PR.
- **Mislabeled Unicode test markers** — `test_reason_tool_unicode` and
  `test_what_if_unicode` were marked `@native_only` while asserting SWI-Prolog
  Unicode behaviour that the native engine deliberately rejects (ASCII-only
  lexer). They are now `@prolog_only`, and two new `@native_only` tests assert
  the clear rejection error (`Query parsing error: Unexpected character …`),
  so the limitation is documented instead of silently skipped.
- **Backend-aware tests** — the API deep-health backend assertion and the
  engine-metrics test now follow the *resolved* backend (`resolve_backend()`)
  instead of the presence of `swipl` on `PATH`; in-process CLI tests isolate
  `EUCLID_BACKEND`, which `cli.main()` writes to the process env and used to
  leak across tests in the same run.
- **Example consistency** — normalized comment style (`%` → `#`), translated
  Italian comments to English, and fixed `=` → `is` for arithmetic assignment
  in policy compiler examples. Added query lines to `cluedo_rules.euclid` and
  `role_hierarchy.euclid`.

## [0.4.2] — 2026-08-16

### Added
- **Interactive Euclid-IR REPL** — `euclid-cli` with no subcommand opens a
  `swipl`/`psql`-style shell: facts and rules accumulate in a session
  knowledge base across `? query` lines, multi-line rules continue after
  `IF`/`AND` (continuation prompt `... > `), and `:` meta-commands cover the
  remaining tools (`:check`, `:kb`, `:load <file>`, `:explain [query]`,
  `:diagnose <query> [why|why_not|what_needs]`, `:what-if <mods>`, `:reset`,
  `:quit`). Piped input runs the same loop as a batch script without prompts;
  `-f`/`--knowledge` seed the session (preload fallback when empty). Docs:
  README "Via CLI" and `docs/CLI.md`.

## [0.4.1] — 2026-08-16

### Added
- **Prometheus metrics (observability, Mode C)** — `euclid_mcp/metrics.py`:
  a zero-dependency (stdlib-only) module implementing `Counter`, `Gauge` and
  `Histogram` (fixed buckets) and rendering them in the Prometheus text
  exposition format. Always on, no dependencies added.
- **Instrumentation** across all three layers, feeding the same registry:
  - Engine lifecycle (`prolog_server.py`): `euclid_engine_requests_total`
    (by `command`), `euclid_engine_restarts_total` (by `reason` —
    `periodic`/`timeout`/`broken_pipe`), `euclid_engine_timeouts_total`,
    `euclid_kb_skipped_loads_total`, and the `euclid_kb_size` gauge
    (facts/rules in the workspace).
  - Tool layer (`server.py`, `_log_call`): `euclid_tool_calls_total`,
    `euclid_tool_errors_total` and `euclid_tool_call_duration_seconds` per
    tool — this covers MCP stdio mode and every in-process consumer too.
  - HTTP API (`integrations/euclid_api.py`): `euclid_http_requests_total`
    (method/path/status), `euclid_http_request_duration_seconds` per path,
    `euclid_solutions_total` per path, `euclid_auth_failures_total`, and the
    `euclid_process_uptime_seconds` gauge. Exposed on the open, read-only
    `GET /metrics` endpoint (never carries KB content).
- **Deep `GET /health`** — now pings the engine and reports its workspace
  stats (`facts`, `rules`, `requests_since_restart`); returns 503 only when
  an engine process exists but does not answer (wedged). A cold process with
  no engine yet is healthy (the engine starts lazily). The native backend is
  healthy by default.
- **Graceful shutdown** — the HTTP API now handles SIGTERM/SIGINT: it stops
  accepting requests, finishes the in-flight one, closes the socket and the
  engine (`prolog_bridge.close()`), so no `swipl` process is orphaned when a
  container stops.
- **Monitoring stack** (`monitoring/`): `docker-compose.monitoring.yml`
  (Prometheus + Grafana + cAdvisor, attached to the shared `euclid-app`
  network so every scaled replica is scraped), Prometheus config with alert
  rules (`EuclidDown`, error rate, p99 latency, engine restart storm, memory
  pressure), Grafana datasource + a prebuilt `Euclid-MCP` dashboard, and a
  README. `docker-compose.yml` gained the named `euclid-app` network.
- **Remote benchmark mode** — `benchmarks/euclid_bench.py --api-url URL`
  stresses an already-running API (no local `swipl` required) and reads
  engine restarts + process uptime from the API's `GET /metrics`.
- **Docs** — `docs/MONITORING.md` gained Mode C (metric reference, scrape
  and query examples), `docs/PRODUCTION.md` gained a metrics section and the
  deep-health check notes, and `benchmarks/docs/08-monitoring.md` documents
  the new benchmark mode (PASS, 5 394 iterations, 658.7 req/s, 0 failures).

### Changed
- `euclid_http_requests_total` and per-path latency histograms record the
  `GET /metrics` scrape itself (its `path` is `/metrics`).

## [0.4.0] — 2026-08-14

### Added
- **Predicate inventory** — `check_kb` now returns `predicates`:
  `PredicateInfo(name, arities, facts, rules)` for every predicate in the KB
  (derived from facts and rule heads, no Euclid-IR syntax added), giving LLM
  extraction a derived contract without extending the language. A new
  `inconsistent_arity` warning flags the same predicate used with multiple
  arities (e.g. `can_access(a)` + `can_access(a, b)`); it is a warning,
  consistent with `duplicate_fact`/`duplicate_rule_id`. Exposed on the MCP
  tool, `POST /check-kb`, and `euclid-cli check` (text + `--json`).
  `predicates_count` is unchanged for backward compatibility.
- **Structured explain** — each `Explanation` now also carries
  `structured_steps`: typed, language-independent reasoning steps (`kind`
  `fact`/`rule`/`neg`/`true`/`unknown`, plus `goal`, `rule_id`, and `body`
  conjuncts). The English `steps: list[str]` remain unchanged and are now
  derived from the same typed steps, so existing consumers are fully backward
  compatible while a UI (e.g. a frontend) can render localized explanations
  without re-walking the proof tree. Exposed on the MCP tool and `POST /explain`.
- **Exposed KB identity** — every tool result (`ReasonResult`,
  `ExplanationResult`, `DiagnosisResult`, `WhatIfResult`, `KBCheckResult`) now
  carries `content_hash` (sha256 of the KB text payload) and `version` (from the
  `@version` directive, when present), on **every** return path including error
  branches. `kb_fingerprint` (`euclid_mcp/engine.py`) is now public. The HTTP
  API exposes both fields on `/reason`, `/explain`, `/diagnose`, `/what-if`,
  and `/check-kb`. Anyone with the `.euclid` text can recompute the hash and
  verify which exact KB a result was computed from — the foundation for KB
  versioning, signatures, and audit trails.
- **Named knowledge bases** — new tools `register_kb`, `unregister_kb`,
  and `list_kbs` manage an in-memory, per-instance registry (max 32 KBs,
  overwrite allowed for idempotent updates). A KB registered once under a
  `kb_id` can then be referenced on `reason`, `explain`, `diagnose`, `what_if`,
  and `check_kb` instead of resending the text, with an optional
  `delta_knowledge` overlay for session-specific facts (requires a `kb_id`).
  Registration validates the `kb_id` (allowlist `[a-z0-9_-]{1,64}`) and the KB
  with `check_kb`. Resolution precedence everywhere: explicit
  `knowledge`/`base_knowledge` → `kb_id` (`Unknown kb_id` error when absent) →
  preloaded KB → "No knowledge provided". With `kb_id` + `delta_knowledge`,
  `content_hash`/`version` are computed from the merged source. The HTTP API
  exposes the same flow as `POST /register-kb`, `POST /unregister-kb`, and
  `POST /list-kbs`, and forwards `kb_id`/`delta_knowledge` on the five
  reasoning endpoints.
- **Native Euclid-IR engine** (`euclid_mcp/ir_parser.py`, `euclid_mcp/ir_engine.py`):
  a pure-Python engine that interprets Euclid-IR directly — facts, rules,
  recursive rules, conjunctions, negation as failure (`NOT`), arithmetic
  (`> >= < <= == != is =` with `+ - * /`), rule ids, string literals and
  wildcards — and produces the same proof trees as the Prolog backend.
  Designed for small knowledge bases where SWI-Prolog cannot be installed
  (e.g. minimal containers); full semantics, limitations and the supported
  test matrix are documented in `docs/NATIVE_ENGINE.md`.
- **Inference-backend dispatcher** (`euclid_mcp/engine.py`): a single `execute`
  dispatch point selects the backend via `EUCLID_BACKEND` (`auto` | `prolog` |
  `native`, default `auto` → SWI-Prolog when on `PATH`, otherwise native) or
  the new `--backend` CLI flag. All tools (`reason`, `explain`, `diagnose`,
  `what_if`, `check_kb`) route through it, so swapping the engine never
  touches the tool layer.
- **Native engine tests** (`tests/test_native_engine.py`): 23 tests covering
  deduction, recursion, negation, arithmetic, strings, wildcards, limits
  (`max_solutions`, depth, timeout) and the dispatcher — run in every CI matrix
  even without SWI-Prolog.
- **Native-vs-Prolog benchmark** (`benchmarks/native_vs_prolog_benchmark.py`
  + `benchmarks/docs/07-native-vs-prolog.md`): head-to-head on example 07 with
  result parity (all solution counts match); native ~7× slower aggregate but
  only ~1.3–2.5× on typical queries, blowing up (17–32×) on high-solution
  wildcard joins and exhaustive-failure `NOT` queries.
- **`euclid-cli` command-line interface** (`euclid_mcp/cli.py`, console script
  `euclid-cli`): a thin, human-friendly wrapper around the five reasoning
  tools. Subcommands `check`, `reason`, `explain`, `diagnose`, and `what-if`
  mirror the MCP tools; the KB comes from a `.euclid` file (`-f`), inline
  (`--knowledge`), or `EUCLID_KB_PATH`/preload, and the query from `--query`
  or the `?` lines in the KB. Backend selection via `--backend`
  (`auto` | `prolog` | `native`), human-readable output by default with a
  `--json` flag for scripting, and exit codes `0`/`1`/`2` for
  success/tool-error/usage-error.

### Changed
- **Example 08 (Cluedo) rewritten to be readable**: the output no longer dumps
  20 raw suspect/weapon/room triples (which were just *remaining candidates*,
  not the answer) with a misleading "CASE RESOLVED". It now narrates the
  deduction: per-category "still possible" vs "eliminated (with reason)",
  real combination counts (e.g. `2 × 2 × 6 = 24`), an honest "not resolved"
  message, and a new **Resolved Game** scenario that genuinely pins down the
  envelope and prints the `explain` proof trace. Engine tool-call logs are
  silenced and the what-if scenario that was a no-op was fixed.

### Fixed
- Example 08 (Cluedo) game-state KB rewritten from Prolog-style
  `.`-terminated facts (one per line) to idiomatic Euclid-IR, so it also runs
  on the native engine.
- **Flaky HTTP API auth tests** (`tests/test_api.py::TestApiAuth` intermittent
  `ConnectionResetError`): the API now sends explicit `Content-Length` +
  `Connection: close` on every response so clients frame the body without an
  EOF/EOF-vs-RST race, and treats a client disconnecting mid-response as normal
  (logged at debug). The test harness shuts the server down and joins the
  serve thread before closing the listening socket, and the test client retries
  once on `ConnectionResetError`/`RemoteDisconnected` — correct consumer
  behavior for real TCP that does not mask a persistently broken server. The
  auth class now passes reliably (previously failing ~5/8 runs).

## [0.3.1] — 2026-08-13

### Added
- **HTTP API authentication & TLS** (`integrations/euclid_api.py`): opt-in
  `EUCLID_API_KEY` (or `--api-key`) requires `Authorization: Bearer <key>` on
  every POST (constant-time check, `401` otherwise, `/health` stays open for
  load balancers), and `EUCLID_TLS_CERT` / `EUCLID_TLS_KEY` (or
  `--certfile` / `--keyfile`) serve HTTPS directly. Setup and posture
  documented in `docs/PRODUCTION.md` → "Authentication & TLS".
- **Python 3.13 and 3.14 support**: verified end-to-end (lint, mypy, and the
  full test suite) on CPython 3.13 and 3.14. New PyPI classifiers advertise
  both, and the CI matrix now runs on Python 3.10–3.14.
- **Stress & soak benchmark** (`benchmarks/euclid_bench.py`): detects response
  mixing, KB pollution, and engine errors across periodic restarts; it is the
  regression detector for the load+query atomicity and the periodic-restart
  policy (must stay PASS at `--workers 4`).
- **Benchmark documentation**: one detail page per benchmark
  (`benchmarks/docs/`) plus a catalog of results and consequent
  implementation choices (`benchmarks/BENCHMARKS.md`).
- **SWI-Prolog compatibility matrix** (`benchmarks/docs/06-swi-prolog-versions.md`):
  the full suite passes on SWI-Prolog 8.4.2, 9.0.4, 9.2.9, and 10.0.2 —
  verified after the 9.x autoloader bug below was fixed.

### Performance
- **KB preload optimization**: repeated loads of the same knowledge base now
  skip re-parsing and re-asserting. Python-side parse+translate results are
  cached per KB source (`_translate_cached`), and the engine skips the
  workspace rebuild when the `load` carries the same `kb_hash` (reply
  `skipped:true` with the stored stats). A repeated identical KB at 20 000
  facts drops from ~196 ms to ~18 ms per load (and the query still runs);
  `explain`, `diagnose`, and `what_if` inherit the win through `reason`, and
  the HTTP API benefits as well. `assert`/`retract` invalidate the
  fingerprint so the next load rebuilds the workspace.

### Fixed
- **Engine workspace sweep is SWI-Prolog 9.x-safe**: `clear_workspace/0`
  retracted every dynamic predicate, including SWI-Prolog's own dynamic
  bookkeeping (e.g. `$search_path_file_cache/3`, `prolog_file_type/2`,
  `$autoload_nesting/1`). On SWI-Prolog 9.x those are dynamic too, so the
  sweep corrupted the autoloader and the next library autoload (e.g.
  `maplist/2`) died with `domain_error(file_type, prolog)` — every tool call
  failed with "Euclid engine error". The engine now tracks the loaded
  workspace in an explicit predicate registry (`workspace_predicate/1`) and
  clears only that; `stats` counts only the registered user predicates. The
  engine is now portable across SWI-Prolog 9.x (CI/Ubuntu) and 10.x.
- **Periodic engine restart**: the restart fired at the end of the request
  that crossed the threshold, stranding the paired query on a bare engine
  (`existence_error` on the per-load `prove/3` → `engine_error`). It now
  fires before the next `load`, so a relaunched engine always receives its
  workspace first. Regression coverage in `tests/test_prolog_server.py`.
- **Load+query atomicity gap**: `prolog_bridge.execute` ran `load` and `query`
  as two separately-locked pipe exchanges, so concurrent workers could
  interleave one request's workspace into another's query (~50% response
  mixing at `--workers 4` in `euclid_bench.py`). `PrologServer.load_and_query`
  now holds the server lock across both steps — a single atomic exchange.
  Regression coverage in `tests/test_prolog_server.py` and the benchmark
  flips from FAIL to PASS at `--workers 4`.

## [0.3.0] — 2026-08-12

### Added
- **Unicode atoms** (`\p{L}`): predicate names, arguments, and rule IDs can now
  be any Unicode letter (CJK, Cyrillic, Greek, …), e.g. `父(张三)` or
  `Бог(Иван)`. Case folding is ASCII-only — `Parent(TOM)` still normalizes to
  `parent(tom)`, while `БОГ(иван)` and `бог(иван)` stay distinct predicates.
  Non-ASCII and uppercase-initial atoms are single-quoted on the Prolog side so
  the engine can never misread them as variables. Covered end-to-end in
  `tests/test_unicode_atoms.py`.

### Changed
- **Persistent SWI-Prolog engine**: replaces the per-call subprocess model. A
  single long-lived `swipl` process is started once and kept alive, connected
  to the server by a JSON-lines pipe (`euclid_mcp/prolog_server.py`,
  `euclid_mcp/prolog_engine.pl`). Each request reloads only the workspace
  (dynamic predicates are cleared and re-asserted over the pipe) instead of
  booting Prolog and consulting a temp file, and the meta-interpreter and
  proof serializer stay resident. Same external API and identical solution
  ordering — pure performance work.
- **Streaming query results**: the generated query snippet writes the JSON
  array of solutions directly to the engine's output via `forall/2` +
  `json_write/3` instead of collecting them in a `findall/3` term, and the
  engine returns the array as a string that the client decodes. No
  double-serialization, low memory on large result sets.
- **Benchmark**: `benchmarks/persistent_engine_benchmark.py` compares the
  stateless (pre-0.3.0) path against the persistent engine across KB sizes
  (100/1k/10k facts) and query shapes (ground / full scan). Measured on the
  reference machine: ~3×–42× steady-state speedup, mean ~14× across cases;
  the persistent path is faster in every measured configuration.
- **Canonical rule-ID marker is now `# RULE:`** (uppercase). The parser remains
  case-insensitive (`# rule:`, `# Rule:` all work), but documentation and
  examples now use `# RULE: <id>` to match the Euclid-IR keyword convention.
  Tests keep exercising the lowercase forms to pin case-insensitivity.
- **README**: new "Scalability" section — persistent engine, stateless
  requests, horizontal scale-out behind a load balancer.

## [0.2.0] — 2026-08-10

### Added
- **`explain` tool**: deterministic proof-tree → natural-language reasoning
  steps (`euclid_mcp/explain.py`). Walks each solution's proof tree and renders
  readable steps in plain language, citing the rule ID when a rule has one —
  no LLM involved, so explanations stay auditable. Exposed over MCP
  (`euclid-mcp_explain`) and HTTP (`POST /explain`).
- **Knowledge Base preload**: a KB can be loaded once at server startup via the
  `EUCLID_KB_PATH` env var or a `--kb-path` CLI flag (`python -m euclid_mcp`,
  console script, and `integrations/euclid_api.py`). The file is validated with
  `check_kb` at import time and fails fast with a clear message on a missing,
  unreadable, oversized, or invalid file. A generic markdown digest of the
  preloaded KB (new `euclid_mcp/kb_summary.py`: fact/rule/predicate counts,
  predicate inventory with arities, rules with their IDs) is appended to the
  server `instructions`, so agents see what the preloaded KB covers without
  extra tool calls. The HTTP API accepts requests without a `knowledge` field
  when a KB is preloaded.
- **Rule IDs**: rules can carry an audit-trail ID via a trailing `# rule: <id>`
  comment (case-preserving, also on the last body line of multi-line rules).
  The ID is surfaced as `rule_id` on `rule` nodes of proof trees, so a decision
  can be cited ("this derives from rule RBAC-0043"). Backward compatible: rules
  without an ID behave exactly as before and their proofs omit the field.
  `check_kb` warns on duplicate rule IDs; `# rule:` on a fact/query is a parse
  error; the reserved internal marker `euclid_rule_id/1` is rejected by the
  sanitizer. Rule bodies in proof output no longer leak the internal marker.
- Dependabot (`.github/dependabot.yml`): weekly update PRs for pip and GitHub Actions
- Reproducible CI install: `uv sync --frozen --extra dev` from `uv.lock` instead of
  floating `pip install` (prevents unpinned upgrades like `mcp` 1.x → 2.x breaking CI)
- Test coverage for HTTP API (`tests/test_api.py`) and CLI (`tests/test_cli.py`)
- `per-file-ignores` in ruff config for demo scripts (`examples/`, `benchmarks/`)
- `mypy` coverage extended to `integrations/`
- CI workflow on push/PR: Python 3.10-3.12 matrix, ruff, mypy, pytest with coverage,
  Codecov upload (`.github/workflows/ci.yml`)
- Structured logging: every tool call logs name, elapsed time, and outcome;
  controllable via the `EUCLID_LOG_LEVEL` env var
- Request tracing in the HTTP API: `X-Request-Id` header is echoed on the response
  and included in access logs
- Pre-commit hooks (`.pre-commit-config.yaml`): ruff, mypy, pytest
- Coverage gate: `fail_under = 80` enforced by pytest-cov
- `pre-commit` added to dev dependencies
- `is` is now validated as a reserved keyword and rejected as a predicate name

### Changed
- **Optional knowledge**: `knowledge`/`base_knowledge` on `reason`, `explain`,
  `diagnose`, `what_if`, and `check_kb` are now optional
  (`str | None = None`). An explicit value always wins; an empty value falls back
  to the KB preloaded from `EUCLID_KB_PATH` (or a `--kb-path` flag). With neither
  provided, tools return a clear "No knowledge provided" error. Backward
  compatible: passing `knowledge` explicitly behaves exactly as before.
- Migrated to **MCP Python SDK v2** (`mcp>=2.0`): `FastMCP` → `MCPServer`
  (`mcp.server.mcpserver`), explicit server name preserved (`Euclid-MCP`).
  Unlocks in-memory testing via `Client(mcp)` (no stdio/ports), hardened stdio,
  stricter protocol validation, and structured `output_schema` on all tools.
  The previous `mcp>=1.27,<2` pin (which blocked SDK 2.0 after it removed
  `mcp.server.fastmcp`) is lifted.
- **Examples**: example 07 (`it_security_compliance`) gained an `--mode explain`
  demonstrating readable reasoning steps with rule ID citations; its policy and
  standard rules carry `# rule:` IDs.
- **Docs**: README, `docs/EUCLID_IR.md`, `AGENTS.md`, and
  `integrations/README.md` now document the `explain` tool, KB preload
  (`EUCLID_KB_PATH` / `--kb-path`), and the `# rule:` syntax with `rule_id` in
  proof output. `.opencode.json`'s `reasoning-engine` agent covers all 5 tools.
- README: shields.io badges (PyPI, Python versions, license, CI, coverage) and
  a Development section with the standard check commands
- `==` replaces `=:=` as the documented arithmetic-equality operator (`=:=` is
  still accepted for backward compatibility); `==` now also works in queries,
  and `==`/`!=`/`<=` inside quoted strings are no longer rewritten
- Keywords (`IF`/`AND`/`NOT`) and the `@version` directive are now
  case-insensitive (`if`/`and`/`not` and `@VERSION` are accepted)
- `what_if` modifications now split on `AND`/`and` case-insensitively

### Fixed
- License detection: replaced the short header-only `LICENSE` with the full
  Apache-2.0 text so GitHub resolves the license (badge + repo metadata)
- CI: bump `actions/checkout@v4`→`v5`, `actions/setup-python@v5`→`v6`,
  `codecov/codecov-action@v5`→`v6` (Node 20 runtime is deprecated on runners)
- Fixed lint issues across examples, benchmarks, and integrations (ruff clean)
- Fixed `mypy` type errors in HTTP API and CLI wrappers

## [0.1.5] — 2026-08-07

### Fixed
- `check_kb` reported spurious "recursive rule without base case" errors when a
  rule body referenced a predicate whose name contains another predicate as a
  substring (e.g. `role_level(...) IF deploy_role_level(...)`). Recursive-rule
  detection now matches exact predicate names.
- Example 07 KB: removed six rules in `aws_iam_patterns.euclid` that referenced
  undefined predicates (`last_used_days/2`, `cross_account_role/1`, `iam_user/1`,
  `rotate_keys_90d/1`, `has_wildcard_permission/2`), keeping the KB `check_kb`
  clean (`valid: True`, no errors or warnings).
- Example 07 generated data: duplicate `has_role/2` facts removed
  (`dat_0003`, `sre_0067`, `plf_0142`); `generate_rbac_data.py` now guards
  `secondary_role != primary_role`.
- Example 10 demo readability: darker cyan/gray colors for light terminals,
  "Tools called:" in magenta, aligned banner, scripted mode asks for Enter
  before questions 2..n instead of after the first.

### Added
- `examples/10_llm_vs_euclid/generate_kb_markdown.py` + committed
  `kb_markdown.md`: the condensed markdown digest of the IT Security KB used by
  Bot A in example 10 is now persisted for review instead of being built only
  in memory at startup.

## [0.1.4] — 2026-08-06

### Fixed
- Arithmetic comparisons (`>`, `>=`, `<`, `<=`, `=:=`, `=\=`) silently returned 0
  solutions because the generated Prolog used `member/2` in the meta-interpreter's
  `is_arith_goal/1` without importing `library(lists)`. Thanks to @eddyscanlan for
  the report with root-cause analysis and fix suggestion.

## [0.1.3] — 2026-07-13

### Added
- `diagnose` tool: query analysis with `why`, `why_not`, `what_needs` modes
- `what_if` tool: scenario analysis with fact additions/removals
- `check_kb` tool: knowledge base validator (syntax, undefined predicates, circular rules, duplicates)
- `max_solutions` parameter exposed in MCP tool (passed to translator)
- Input sanitizer: rejects dangerous Prolog directives (`shell()`, `halt()`, `:-` injection)
- Hard limits: max 500 KB input, max 500 depth, max 1000 solutions, 30 s timeout
- Error message sanitization (strips internal file paths from Prolog errors)
- Glama registry metadata (`glama.json`)
- EUCLID_IR.md language reference document

### Changed
- Security hardening across the full pipeline (sanitize → parse → translate → execute)

## [0.1.2] — 2026-07-13

### Added
- `max_solutions` parameter to translator and server
- Security hardening: input sanitization, hard limits, error sanitization
- EUCLID_IR.md language reference

### Fixed
- Translator passes `max_solutions` through to Prolog query limits

## [0.1.1] — 2026-07-12

### Added
- Arithmetic comparisons in rules (`>`, `>=`, `<`, `<=`, `=:=`, `=\=`)
- Negation operator (`NOT` → Prolog `\+`)
- Multi-line rule parsing (body on next lines)
- Conjunction queries with variable deduplication
- IT Security & Compliance demo (3,872 facts, 10 questions)
- Unit tests for new features (25 total, all passing)
- MCP Registry metadata (`server.json`)
- GitHub Actions workflow for PyPI publishing

### Changed
- Updated MCP server `instructions` with new capabilities
- Translated `pyproject.toml` description to English

### Fixed
- Meta-interpreter now handles built-in arithmetic operators
- Query conjunctions correctly wrapped in Prolog parentheses
- NOT operator converted to Prolog negation (`\+`)
- Multi-line rules no longer split into separate statements

## [0.1.0] — 2026-07-01

### Added
- Initial release
- Euclid IR parser (text + YAML formats)
- Prolog translator with meta-interpreter for proof trees
- MCP server with `reason` tool
- Examples: genealogy, RBAC, classification, loan eligibility, compliance auditor

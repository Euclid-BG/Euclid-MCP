# Native Engine

Euclid-MCP's primary inference engine is **SWI-Prolog**. A pure-Python
**native engine** interprets **Euclid-IR** directly as a fallback for small
knowledge bases where SWI-Prolog cannot be installed.

It is **not** a full replacement for SWI-Prolog: it targets small, well-formed
knowledge bases and deliberately implements a subset of the semantics (Horn
clauses, negation as failure, arithmetic). The full test suite always runs
against the Prolog backend; the native engine adds its own test suite and a
compatibility matrix (see below).

## Activation

The backend is selected by the `EUCLID_BACKEND` environment variable or the
`--backend` CLI flag:

| Value    | Behavior                                                       |
|----------|----------------------------------------------------------------|
| `auto`   | SWI-Prolog if `swipl` is on `PATH`, otherwise the native engine (default) |
| `prolog` | Always the persistent SWI-Prolog engine                        |
| `native` | Always the native engine                                       |

All tools (`reason`, `explain`, `diagnose`, `what_if`, `check_kb`) route
through a single dispatch point (`euclid_mcp/engine.py:execute`), so no tool
changes are needed to swap the backend.

```bash
EUCLID_BACKEND=native euclid-mcp
# or, per invocation:
EUCLID_BACKEND=native python examples/04_loan_eligibility.py
```

## Architecture

```
server.py ──► engine.py (dispatcher) ──► prolog_bridge.py ──► SWI-Prolog
                                     └─► ir_engine.py ──► ir_parser.py (native)
```

* `euclid_mcp/ir_parser.py` — lexer + recursive-descent parser producing a small
  term tree (`Var` / `Atom` / `Number` / `Compound`).
* `euclid_mcp/ir_engine.py` — unification (with occurs check), a depth-limited
  SLD-style solver, negation as failure, arithmetic evaluation, and proof-tree
  construction. `rule_id` markers and string literals are preserved.
* Both backends emit the **same `ProofNode` structure**, so `explain`,
  `diagnose` and `what_if` work unchanged on native proofs.

## Supported

* Facts and rules (Horn clauses), including recursive rules
* Conjunctions (`AND`), multi-line rule bodies
* Negation as failure (`NOT`), same depth limit as the Prolog meta-interpreter
* **Boolean body literals** (`true` / `false`): `p IF false` never proves,
  `p IF true` proves like a fact (proof node `fact`, or `rule` when the rule
  carries an ID) — identical to the Prolog meta-interpreter, which has
  dedicated branches for both literals and a built-in guard so no built-in
  body goal can raise inside `clause/2`
* Arithmetic: `> >= < <= == != is =` with `+ - * /` expressions
  (`$level >= $min_level + 1` works; expressions are evaluated recursively)
* `=` is **unification**, not arithmetic (matches Prolog: `$x = $y + 1`
  binds `$x` to the *term* `y+1`)
* `==` / `!=`: numeric when both sides are numeric, otherwise syntactic
  equality of ground terms (a native extension — Prolog's `=:=` errors there)
* Rule ids (`# RULE: <id>`) surfaced as `rule_id` in proofs and cited by
  `explain`
* String literals (`"..."`, `'...'`) preserved as UTF-8
* **Unicode predicate/atom names** (`父(张三)`, `смертный($x)`, `Бог(Иван)`),
  matching SWI-Prolog; case folding stays ASCII-only, so non-ASCII names are
  case-sensitive (`БОГ` and `бог` are distinct predicates). Variables remain
  ASCII (`$name`), as in Euclid-IR itself.
* Wildcards (`_`), negative numbers (`-90`), hyphenated atoms (`security-ops`)
* Clause ordering matches the Prolog backend (sort by predicate name, then
  statement text), so solution order is identical for typical KBs

## Semantics parity

For the examples in this repo the native engine produces **identical results**
to the Prolog backend — verified per-question on example 07
(`it_security_compliance`, ~577 facts with arithmetic) and examples
01, 02, 04, 08 and 13.

## Limitations (by design)

* **No cut** (`!`), lists, `findall`/`bagof`, dynamic `assert`/`retract`,
  or modules — and no disjunction either: `OR` in Euclid-IR rules is
  desugared into pure Horn clauses at parse time, before the engine sees it.
* **Depth-limited recursion** (`max_depth`, default 30) and a wall-clock
  timeout; performance is tuned for small KBs (a few hundred facts), not large
  datasets.
* **One statement per line**: multiple `.`-terminated Prolog-style facts on a
  single line are not supported natively (the Cluedo example was converted to
  idiomatic Euclid-IR for this reason).
* **Decimal numbers only**: integers and floats (`42`, `-7`, `3.14`). Other
  literal forms accepted by SWI-Prolog are rejected with a parse error instead
  of being misread: scientific notation (`1e3`), hex/binary/octal (`0x10`),
  digit separators (`1_000`), trailing garbage (`12abc`). Write big magnitudes
  with explicit arithmetic (`1000000`, `$n * 1000`).
* A `-` immediately after a number is read as a negative number, not
  subtraction, so both `p(1-2)` and `$x > 90-1` are parse errors — arguments
  must be comma-separated and arithmetic needs spaces (`$a - $b`, `90 - 1`;
  `$a-$b` is rejected too).
* **Division by zero** raises a clean arithmetic error (the tool layer returns
  it as an error result, matching the Prolog backend's `engine_error`), not a
  Python crash.
* Unbound variables in comparisons/`is` raise an arithmetic error (as Prolog's
  `=:=`/`is` do on uninstantiated operands).
* Solutions with unbound query variables are kept: unbound variables surface
  as explicit `null` bindings (`{"who": null}`) and render as the wildcard
  `_` in proof-tree goals — identical to the Prolog backend, including SWI's
  fresh-variable normalization (see `docs/EUCLID_IR.md`, "Unbound query
  variables").
* Native Engine is slower than SWI-Prolog
  (see [`07-native-vs-prolog.md`](../benchmarks/docs/07-native-vs-prolog.md)).
  Of course it is not *slower by design* but making it faster is not in our roadmap.

## Resource ceilings vs SWI-Prolog

SWI-Prolog documents its own limits
([representation limits](https://www.swi-prolog.org/pldoc/man?section=limits));
the native engine's practical ceilings come from the Python interpreter it
runs on. Measured on CPython 3.12 with the default recursion limit (1000) —
expect the same *order of magnitude*, not exact values, on other versions:

| Resource | Native ceiling (measured) | Notes |
|----------|---------------------------|-------|
| Proof depth (linear chain) | ~320 levels | The API accepts `max_depth` up to 500, but deep proofs hit the Python stack first; exceeding it returns a clear error asking to lower `max_depth`. SWI-Prolog handles chains of 400+ natively. |
| Conjunction width | ~950 goals `AND`-ed in one query/rule body | Beyond that the solver exhausts the Python stack. |
| Nested term depth | ~250 | Parser, unifier and renderer all recurse per nesting level. |
| Timeout coverage | solving only (default 30s) | KB parsing is bounded by the shared 500 KB knowledge-size cap instead. |

Depth *semantics* are identical on both backends: a chain of N rule steps
needs exactly `max_depth = N` on each — verified empirically (no off-by-one).

Where the native engine differs from SWI-Prolog's documented limits:

| Aspect | Native engine | SWI-Prolog |
|--------|---------------|------------|
| Compound arity | no limit (verified at 1500 args) | max arity 1024 |
| Integers | arbitrary precision (Python `int`) | arbitrary precision (GMP) — parity |
| Occurs check | always on (`$x = $x + 1` fails cleanly) | off by default (`X = X + 1` builds a cyclic term) |
| Float literals like `.5` | parsed as an **atom**, not a number | number (`0.5`) — write `0.5` explicitly |
| `==` / `!=` on non-numeric terms | syntactic equality (native extension) | `=:=` raises a type error |


## Test matrix

Run the full suite against the Prolog backend (default), then against the
native engine:

```bash
pytest                          # Prolog backend — full suite (all tests)
EUCLID_BACKEND=native pytest    # native engine
```

Native matrix (this release):

| Result | Tests |
|--------|-------|
| pass   | `tests/test_native_engine.py` (34) + the whole main suite |
| pass   | the Unicode atom tests in `tests/test_unicode_atoms.py`, unmarked — they run on both backends and assert parity (`test_reason_tool_unicode`, `test_what_if_unicode`) |

The CI matrix runs both backends explicitly: the Prolog legs on every supported
Python, plus a `EUCLID_BACKEND=native` leg, so native-specific behaviour is
always exercised on every push/PR.

New tool-level behaviour must keep the Prolog suite green; native-specific
behaviour belongs in `tests/test_native_engine.py`.

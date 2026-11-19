# Benchmark 6 — SWI-Prolog version compatibility

- **Run date:** 2026-08-13; re-verified on 11.0.0 on 2026-11-19
- **What it measures:** the engine stays correct across recent SWI-Prolog
  releases — 8.4.2, 9.0.4, 9.2.9, 10.0.2, and 11.0.0.

## Why this matters

The persistent engine (`euclid_mcp/prolog_engine.pl`) runs on whatever SWI-Prolog
the deployment provides: the CI runner (`apt` `swi-prolog` on Ubuntu) and
end-user machines span the 8.x–11.x line. A version-specific regression in the
engine must be caught before release, not in production.

## Method

The full test suite (630 tests) is run on the target SWI-Prolog; the
engine-dependent suites (`test_prolog_server.py`, `test_prolog_bridge.py`,
`test_tools.py`, `test_unicode_atoms.py`, `test_security.py`, …) exercise load,
query, proof trees, `assert`/`retract`, the `kb_hash` skip path, and the
concurrency regression tests. CI runs the same suite on the GitHub runner
(5 Python versions) against the distro `swi-prolog`.

| SWI-Prolog | Environment | Result |
|------------|-------------|--------|
| 8.4.2 | Ubuntu 22.04 (container) | **256/256 PASS** |
| 9.0.4 | Ubuntu 24.04 (CI, `apt swi-prolog`) | **PASS** (Python 3.10–3.14) |
| 9.2.9 | Debian bookworm (container) | **256/256 PASS**, coverage 83.8% |
| 10.0.2 | macOS (local) | **256/256 PASS** |
| 11.0.0 | macOS (Homebrew), `swipl:11.0.0` image and CI container | **630/630 PASS** (`EUCLID_BACKEND=prolog`, Python 3.12.11 and 3.13.5) |

## Verification on 11.0.0 (2026-11-19)

SWI-Prolog 11.0.0 was verified after a Homebrew upgrade, with the backend
forced to `prolog` so the suite cannot silently fall back to the native engine:

| Check | Result |
|-------|--------|
| `ruff check .` / `mypy euclid_mcp integrations` | PASS |
| Full suite, `EUCLID_BACKEND=prolog` | **630 passed**, coverage 88.81% |
| Same suite in the `swipl:11.0.0` CI container | **630 passed**, Python 3.13.5 |
| Full suite, `EUCLID_BACKEND=native` | 629 passed, 1 skipped |
| MCP tools (`reason`, `explain`, `diagnose`, `what_if`, `check_kb`) | PASS |
| `divergenze.py` (both backends) / `prova_unicode.py` | PASS, backend outputs congruent |
| `docker build` of both images + in-container reasoning | PASS; Prolog image uses `/usr/bin/swipl`, native image has none |

No engine change was needed: the meta-interpreter's built-in guard and the
registry-scoped workspace clearing are version-agnostic. The Docker image is
now pinned to `swipl:11.0.0` and CI adds a dedicated 11.0.0 container job.

## Bug found and fixed (v0.3.1, 2026-08-13)

**Symptom.** On SWI-Prolog 9.x every tool call failed with `Euclid engine error`
(after the PR pushed the persistent-engine commits to CI for the first time).

**Root cause.** `clear_workspace/0` swept **every dynamic predicate** in the
process. On SWI-Prolog 9.x the runtime's own bookkeeping
(`$search_path_file_cache/3`, `prolog_file_type/2`, `$autoload_nesting/1`, …)
is dynamic, so the sweep retracted those clauses and **corrupted the
autoloader**: the next library autoload (e.g. `maplist/2`) died with
`domain_error(file_type, prolog)`. On SWI-Prolog 10.x those internals are no
longer dynamic, which is why the engine passed locally and only failed on the
distro SWI.

**Fix.** `euclid_mcp/prolog_engine.pl` now tracks the loaded workspace in an
explicit predicate registry (`workspace_predicate/1`):
- `declare_dynamic/1` and `assert_clause/1` register the predicate;
- `clear_workspace/0` retracts only the registered predicates (plus the
  engine-internal array flag `euclid_array_first/0`);
- `stats/2` counts only the registered user predicates (meta-interpreter
  excluded), never a broad dynamic sweep.

Result: the engine uses only core Prolog (retract/assertz/recursion) available
in every supported release. `user_predicate/1` still excludes the
meta-interpreter and the fingerprint/streaming bookkeeping from the stats.

## Performance impact of the fix

`euclid_bench.py` (`direct workers=4`, 30 s) on the same machine, two runs
each, before and after the fix:

| | pre-fix | post-fix |
|---|--------:|---------:|
| throughput | 440.0 / 418.6 req/s | **513.2 / 511.8 req/s** |
| mean latency | 9.0 / 9.5 ms | **7.8 / 7.8 ms** |

The fix is **faster**, not slower: the registry sweep touches only the
workspace predicates instead of enumerating every dynamic predicate in the
process, and the `kb_hash` skip path never runs `clear_workspace` at all.

## Consequent implementation choices

1. **Registry-based workspace clearing** — the `workspace_predicate/1`
   approach is kept: it is correct on all SWI-Prolog 8.x–11.x and faster than
   the broad dynamic sweep it replaces.
2. **CI keeps distro `swi-prolog`** (`apt`), which on `ubuntu-latest` means
   SWI-Prolog 9.x — exactly the version class that caught this bug; the engine
   must stay green there. A second job runs the suite in `swipl:11.0.0`, since
   the distro package does not provide 11.x yet.
3. **Stats semantics tightened**: `stats` now counts only the loaded user
   workspace (documented contract), so the numbers are identical across SWI
   versions instead of drifting with the runtime's dynamic bookkeeping.

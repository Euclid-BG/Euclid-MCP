# Benchmarks — Euclid-MCP

Catalog of the benchmark suite: what each script measures, the results, and
the implementation choices that followed. One detail page per benchmark lives
in [`docs/`](docs/).

**Environment (2026-08-12/08-14 runs):** SWI-Prolog 10.0.2 (arm64-darwin), Python
3.12.11, `.venv`. The SWI-Prolog compatibility matrix (benchmark 6) spans
8.4.2/9.0.4/9.2.9/10.0.2 and was re-verified on 11.0.0 on 2026-11-19.

## Index

| # | Script | Measures | Result | Detail |
|---|--------|----------|--------|--------|
| 1 | `reasoning_benchmark.py` | Small LLM vs cloud LLM vs LLM + Euclid-MCP, 5 small reasoning tasks | All equal (5/5) at small scale; Euclid adds input tokens | [01](docs/01-reasoning-vs-llm.md) |
| 2 | `rbac_1000.py` | Same comparison at scale (1 000 users, 1 053 facts) | LLMs 2/5, Euclid 5/5, faster (963 ms) and fewer output tokens | [02](docs/02-rbac-at-scale.md) |
| 3 | `persistent_engine_benchmark.py` | Stateless subprocess vs persistent engine | **12.1×** mean steady-state speedup | [03](docs/03-persistent-engine.md) |
| 4 | `solution_cap_benchmark.py` | Engine-side `max_solutions` cap stops work early | Capped time flat (0.6→23 ms); ratio vs uncapped grows 19×→54× | [04](docs/04-solution-cap.md) |
| 5 | `euclid_bench.py` | Stress & soak: mixing, pollution, restart, API under load | workers=1, workers=4 & API **PASS** | [05](docs/05-stress-soak.md) |
| 6 | — (full suite + CI) | Engine correctness across SWI-Prolog 8.4.2/9.0.4/9.2.9/10.0.2/11.0.0 | **PASS** on all versions (630/630 on 11.0.0) | [06](docs/06-swi-prolog-versions.md) |
| 7 | `native_vs_prolog_benchmark.py` | Native Euclid-IR engine vs SWI-Prolog on example 07 (10 queries, 2 KB sizes) | **Parity** (all solution counts match); native ~7× slower aggregate, ~1.3–2.5× on typical queries, up to 17–32× on high-solution joins & exhaustive-failure `NOT` queries | [07](docs/07-native-vs-prolog.md) |
| 8 | `euclid_bench.py --api-url` | Remote (containerized) HTTP API under load; report reads restarts/uptime from `GET /metrics` | **PASS** (v0.4.1, local API) | [08](docs/08-monitoring.md) |

## Summary of results

1. **Reasoning at small scale (July 2026).** With 5–15 facts, LLM alone is
   sufficient: all three conditions scored 5/5. Euclid-MCP matches accuracy at
   slightly higher input tokens. **→** Use the engine only when facts outgrow
   reliable LLM context.

2. **RBAC at scale (July 2026).** At 1 053 facts both LLMs hallucinate
   systematically (2/5); Euclid-MCP is exact (5/5), faster (963 ms vs
   6 966 ms) and token-cheaper (12 vs 165 output tokens). **→** The engine's
   value proposition, referenced from the README.

3. **Persistent engine vs stateless (2026-08-12).** Reusing one long-lived
   `swipl` process instead of spawning one per call is **12.1×** faster in
   steady state. The gap narrows at large KBs because the per-call workspace
   reload dominates. **→** Persistent engine is the default path; the reload
   cost motivated the v0.3.1 KB memoization (see "KB reload cost").

4. **Solution cap (2026-08-12).** The Prolog-side cap keeps a capped query at
   ~flat cost (0.6 → 23.4 ms) while the uncapped cost scales with solutions
   (12 → 1 254 ms). **→** Cap enforced engine-side (`count_limit/2`), so
   dense queries cannot degenerate into full scans.

5. **Stress & soak (2026-08-12 → v0.3.1).**
   - `direct workers=1`, 1 200 it., restart_every=1000: **PASS**, 280 req/s,
     mean 3.4 ms, 2 restarts, 0 failures.
   - `direct workers=4`: **FAIL** on 2026-08-12 (1 464/2 925 mismatches, ~50%)
     — the load+query atomicity gap, **fixed in v0.3.1**; the same run is now
     **PASS** (5 324 it., 442.9 req/s, 0 failures).
   - `api workers=4`, 10 s: **PASS**, 194 req/s, 0 failures.
    **→** Found and fixed a real restart bug (see below) and the load+query
    atomicity gap; `euclid_bench.py` stays as the regression detector for both.

6. **SWI-Prolog version compatibility (2026-08-13, v0.3.1; 11.0.0 re-check
   2026-11-19).** The full suite passes on SWI-Prolog 8.4.2 (Ubuntu 22.04),
   9.0.4 (CI), 9.2.9 (Debian), 10.0.2 (macOS) and 11.0.0 (Homebrew, Docker
   image and CI container). The first CI run on the 9.x line exposed a real
   engine bug: `clear_workspace` retracted SWI-Prolog's own dynamic bookkeeping
   and corrupted the autoloader (`domain_error(file_type, prolog)`). The
   registry fix is ~19% faster (513 vs 429 req/s), not slower. **→** The engine
   is portable across the supported SWI-Prolog releases; the 9.x CI matrix and
   the new 11.0.0 container job keep guarding it.

7. **Native engine vs SWI-Prolog (2026-08-14, v0.4.0).** The first head-to-head
   between the pure-Python native engine and SWI-Prolog on example 07 (10
   queries, small + full KB). **Result parity**: every solution count matches.
   Native is ~7× slower aggregate (53 → 390 ms small, 564 → 3 777 ms full), but
   only ~1.3–2.5× on typical queries; it blows up (17–32×) precisely on
    high-solution wildcard joins and exhaustive-failure `NOT` queries — the
    compliance-audit workloads of example 07. **→** Confirms native is for small
    interactive KBs; heavy audits stay on SWI-Prolog; a native Program cache
    (mirroring `_translate_cached`) is the next optimization.

8. **Remote API mode (2026-08-16, v0.4.1).** `euclid_bench.py --api-url URL`
    hammers an already-running API (the containerized one from
    `docker-compose.yml`, or any deployed instance) instead of spawning the
    server in-process. The final report reads engine restarts and process
    uptime from the API's `GET /metrics` endpoint — the same data the
    Prometheus stack scrapes. **→** The benchmark now covers the real
    deployment shape, including a containerized `swipl` inside the API image.

## Consequent implementation choices

- **Persistent engine architecture** (`PrologServer` + JSON-lines pipe)
  validated by Benchmark 3; it replaced the per-call `swipl` subprocess.
- **Engine-side solution cap** (`count_limit/2`, `MAX_SOLUTIONS_LIMIT`)
  introduced by Benchmark 4 under the security-hardening work
  (commit `6b0295ba`).
- **Periodic-restart bug fixed** (Benchmark 5): the restart fired at the end
  of a crossing request and stranded the next query on a bare engine
  (`existence_error` on the per-load `prove/3`). It now fires at the start of
  the next `load` (`euclid_mcp/prolog_server.py`), with regression tests in
  `tests/test_prolog_server.py`.
- **Load+query atomicity gap fixed** (Benchmark 5, v0.3.1): `load` and `query`
  were two separately-locked pipe exchanges, so concurrent workers mixed
  workspaces (~50% response mixing at `--workers 4`). `load_and_query` now
  holds the lock across both — a single atomic exchange — and the direct
  workers=4 run flips to PASS (regression test
  `test_load_and_query_is_atomic_under_concurrency`).
- **KB memoization** (v0.3.1): repeated loads of the same KB skip re-parsing,
  re-translation, and the engine workspace rebuild — see "KB reload cost"
  below.
- **SWI-Prolog 9.x safety** (v0.3.1, Benchmark 6): `clear_workspace` now
  retracts only the registered workspace predicates (`workspace_predicate/1`)
  instead of every dynamic predicate, keeping the engine correct on
  SWI-Prolog 8.x–11.x (see `benchmarks/docs/06-swi-prolog-versions.md`).
- **Remote API benchmark mode** (v0.4.1, Benchmark 8): `--api-url` stresses a
  real deployment (containerized API + its own `swipl`), and the report reads
  restarts/uptime from `GET /metrics` — the same observability surface the
  monitoring stack uses (see `benchmarks/docs/08-monitoring.md`).

## Exploratory measurement — KB reload cost (2026-08-12)

Ad-hoc profiling of a single engine call (parse → translate → load → query) on
a hot engine, to decide whether persisting the KB is worthwhile:

| KB | parse | translate | load (assert) | query |
|----|------:|----------:|--------------:|------:|
| 500 | 4.6 ms | 2.3 ms | 3.7 ms | 0.4 ms |
| 5 000 | 36 ms | 18 ms | 14 ms | 2.7 ms |
| 20 000 | 143 ms | 73 ms | 44 ms | 4.7 ms |

The engine reload is only ~17–25% of the cost; **Python-side parse dominates**
(~55%). Every tool call reloads the whole KB, and `what_if` does it twice.

**Decision (A+B) — implemented in v0.3.1.** Cache parse+translate in Python
keyed by KB fingerprint (`euclid_mcp/server.py` `_translate_cached`), and
skip the engine reload when the fingerprint is unchanged (the `load` carries
the `kb_hash`; the engine replies `skipped:true` with the stored stats).
Measured on a repeated identical 20 000-fact KB: **~196 ms → ~18 ms per load**
(the rebuild is also skipped, not just the Python side; the query still
runs). The delta-based approach (keep base resident, apply/remove only session
facts) stays deferred, as does the two-phase conditional load that would drop
the unchanged-KB cost to ~1 ms by not shipping the clauses over the pipe.

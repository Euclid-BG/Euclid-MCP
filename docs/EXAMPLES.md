# Euclid-MCP Examples

Euclid-MCP is a hybrid cognitive architecture: a lightweight LLM describes the world in facts, and a deterministic engine performs the actual deduction. The LLM never needs to reason — it only needs to describe.


## Real-world examples

After installing Euclid-MCP (via pip or from source with an active virtualenv):

```bash
# Hello World — simplest Euclid-IR example (10 lines)
# Load into the REPL or run via check_kb
euclid-cli check -f examples/00_basics/hello.euclid
euclid-cli reason -f examples/00_basics/hello.euclid

# Genealogy — recursive family tree reasoning
python examples/01_genealogy.py

# RBAC — Role-Based Access Control
python examples/02_rbac.py

# Classification — biological taxonomy
python examples/03_classification.py

# Business rules — loan eligibility
python examples/04_loan_eligibility.py

# Simple access policy — intermediate example (NOT, arithmetic, wildcards, rule IDs, @version)
euclid-cli check -f examples/04a_simple_policy/simple_access.euclid
euclid-cli reason -f examples/04a_simple_policy/simple_access.euclid

# Compliance auditor — cloud resource policy enforcement
python examples/05_compliance_auditor/auditor.py

# Loan officer — CSV-driven eligibility with detailed breakdown
python examples/06_loan_eligibility/loan_officer.py

# IT Security & Compliance — multi-layer policy reasoning (rule IDs + explanations)
python examples/07_it_security_compliance/demo.py --small

# Cluedo Detective — solve Cluedo mysteries with deductive elimination
python examples/08_cluedo/cluedo.py

# Turing Machine — demonstrating Turing-completeness of the language
python examples/09_turing_machine/tm_machine.py

# LLM vs Euclid-MCP — interactive side-by-side comparison
python examples/10_llm_vs_euclid/demo.py

# Certainty Factors (mini-MYCIN) — Using both logic and uncertainty
python examples/11_certainty_factors/certainty_factors.py

# KB validation — check_kb on valid and broken knowledge bases
python examples/12_kb_check/demo.py

# Policy Compiler — document → Euclid-IR KB → reasoning (policy + EU AI Act art. 6(3))
python examples/13_policy_compiler/demo.py
```

Each example runs a complete reasoning session and prints solutions with proof trees — no LLM required.  
Use them as templates for integrating Euclid-MCP into your own agents.

First easy examples show the reasoning capability of Euclid-MCP.

Examples 05 and 06 demonstrate a **data-driven agent workflow**:
- Read external data (JSON, CSV) that simulates API/CRM exports
- Convert structured data to Euclid facts in Python
- Load policy rules from `.euclid` files (separated from data)
- Call `reason()` for deduction
- Format results into human-readable reports with proof chains

This mirrors how a real agent would work: collect data, describe it as facts, let Euclid reason, and present the results.

### Example 04a: Simple Access Policy

Intermediate example demonstrating all core Euclid-IR features in a single
readable file: `@version` directive, `//` comments, string literals, zero-arity
facts, multi-line rules with `# RULE:` IDs, `NOT` (negation), arithmetic
comparisons (`>=`, `<=`, `==`, `!=`), wildcards (`_`), conjunction queries,
and `OR` (disjunction) with parenthesized groups and `AND > OR` precedence —
rule `POL-05` lets support or contractor roles access internal resources.

```bash
# Validate
euclid-cli check -f examples/04a_simple_policy/simple_access.euclid

# Reason
euclid-cli reason -f examples/04a_simple_policy/simple_access.euclid

# Explain with rule ID citations
euclid-cli explain -f examples/04a_simple_policy/simple_access.euclid
```

### Example 07: IT Security & Compliance

The most advanced example demonstrating:
- **3-layer architecture**: Standards (CIS, AWS IAM) → Company Policies → Data Facts
- **Arithmetic comparisons**: `$days > 90` for stale access detection
- **Multi-line rules**: Complex policies split across lines
- **Conjunction queries**: Combining multiple predicates
- **Negative tests**: Verifying empty results for invalid access patterns
- **Rule IDs**: policy rules tagged with `# RULE: <id>` and cited in proofs
- **Explanations**: `--mode explain` renders readable reasoning steps with
  rule ID citations for a full audit trail

```bash
# Quick test (30 users, 50 resources, ~577 facts)
python3 examples/07_it_security_compliance/demo.py --small

# Full dataset (200 users, 300 resources, ~3,869 facts)
python3 examples/07_it_security_compliance/demo.py

# Natural-language explanations with rule ID citations
python3 examples/07_it_security_compliance/demo.py --small --mode explain
```

### Example 08: Cluedo Detective

A detective agent that solves Cluedo mysteries by deductive elimination: given
a game state (cards in hands, cards shown during suggestions) the engine
determines who, with what weapon, and in which room is in the envelope —
guaranteed to be consistent with every clue. Features `what-if` scenarios to
test the effect of learning a new clue.

![Euclid-Owl — the detective mascot of example 08](../examples/08_cluedo/euclid_owl.png)

```bash
# Run both scenarios (early + late game)
python3 examples/08_cluedo/cluedo.py

# Single scenario, or what-if analysis
python3 examples/08_cluedo/cluedo.py --scenario early
python3 examples/08_cluedo/cluedo.py --scenario late
python3 examples/08_cluedo/cluedo.py --scenario what-if

# Custom game state file
python3 examples/08_cluedo/cluedo.py --custom my_game.txt

# Native Euclid Engine
EUCLID_BACKEND=native python3 examples/08_cluedo/cluedo.py --scenario late
```


### Example 09: Turing Machine in Pure Euclid-IR

Proof that Euclid-IR is Turing-complete **without** cut, lists, or
assert/retract: a binary-increment Turing machine where the tape is two
stacks of nested compound terms (`cell(H, Rest)`) and execution is pure
deduction — `final/2` reachability over `step/2` transitions. The runner
feeds initial tapes, the engine halts with the incremented tape, and the
result is checked against Python's arithmetic.

```bash
# Run all demo inputs (1011→1100, 111→1000, 100→101, 0→1)
python3 examples/09_turing_machine/tm_machine.py

# A single input
python3 examples/09_turing_machine/tm_machine.py --bits 1011

# Native Euclid Engine
EUCLID_BACKEND=native python3 examples/09_turing_machine/tm_machine.py
```

### Example 10: LLM vs Euclid-MCP

Interactive side-by-side comparison: a plain LLM vs the same LLM augmented with Euclid-MCP's reasoning engine. Same model, same knowledge base, dramatically different results.

```bash
# Requires: Ollama running with llama3.1:8b pulled
ollama pull llama3.1:8b

# Run the interactive demo
python3 examples/10_llm_vs_euclid/demo.py

# Options
python3 examples/10_llm_vs_euclid/demo.py --model llama3.1:8b   # Explicit model
python3 examples/10_llm_vs_euclid/demo.py --bot-a-only           # Plain LLM only
python3 examples/10_llm_vs_euclid/demo.py --bot-b-only           # Euclid bot only
python3 examples/10_llm_vs_euclid/demo.py --verbose              # Show proof chains

# Scripted mode — run preset questions in sequence, then exit (ideal for demos)
python3 examples/10_llm_vs_euclid/demo.py --scripted
python3 examples/10_llm_vs_euclid/demo.py --scripted --pause     # Enter between questions
python3 examples/10_llm_vs_euclid/demo.py --scripted --delay 2   # 2s pause between questions

# Regenerate the condensed markdown digest of the KB (Bot A's context), persisted
# in kb_markdown.md so the same digest can be reviewed/versioned
python3 examples/10_llm_vs_euclid/generate_kb_markdown.py
```

- **Bot A** (plain): entire KB injected as markdown context — like RAG, grows with history
- **Bot B** (Euclid): short system prompt + tool calling via `reason`, `diagnose`, `what_if`, `check_kb`
- Language-agnostic: speak in any language, the engine translates to Euclid-IR automatically
- Demonstrates proof trees, deterministic answers, and query diagnosis vs LLM hallucination

### Example 11: Certainty Factors (mini-MYCIN)

A miniature MYCIN-style diagnostic engine: findings carry certainty
factors, diseases are scored as `rule_CF x min(findings)` via `min_of/3`
and exact arithmetic (`is`). Includes transitive closure over a canonical
symptom order, pattern-shape gates so each disease scores through exactly
one rule, and a dyadic-exact expected ranking: flu 0.25 > covid 0.0625 >
cold 0.03125. Uncertainty lives in the data; the derivation stays
deterministic and auditable.

```bash
# Full ranking with expected-value checks
python3 examples/11_certainty_factors/certainty_factors.py

# Native Euclid Engine
EUCLID_BACKEND=native python3 examples/11_certainty_factors/certainty_factors.py
```

### Example 13: Policy Compiler — document → Euclid-IR KB → reasoning

The first example that starts from a **source document in natural language**
and derives a Euclid-IR knowledge base from it, then loads and uses that KB
with Euclid-MCP. Two committed KBs are provided:

- `kb/access_control_policy.euclid` — fictional access-control policy
  (environments, role levels, deployment rights, data classification,
  emergency access, derogations)
- `kb/ai_act_art6_3.euclid` — official extract of the EU AI Act
  (Reg. (UE) 2024/1689) art. 6(3): high-risk derogation, conditions a–d, and
  the profiling counter-exception

The extraction pipeline (`extract/`) has three stages: deterministic document
parsing (stage 1), optional LLM formalization via Ollama (stage 2), and KB
assembly + `check_kb` validation (stage 3), followed by human curation
(stage 4). Every rule carries `# RULE: <id>` and a `# src: <section>` anchor.

```bash
# Validate the committed KBs, then reason over them
python3 examples/13_policy_compiler/extract/extract.py check --kb examples/13_policy_compiler/kb/access_control_policy.euclid
python3 examples/13_policy_compiler/demo.py
python3 examples/13_policy_compiler/demo.py --kb ai_act
python3 examples/13_policy_compiler/demo.py --preload --query P2

# Regenerate a KB from its source (Ollama optional; default model llama3.1:8b)
python3 examples/13_policy_compiler/extract/extract.py compile \
  --source examples/13_policy_compiler/source/access_control_policy.md \
  --out examples/13_policy_compiler/kb/access_control_policy.euclid
```

Engine constraints surfaced and encoded in the example: `==` is arithmetic
only (atom equality crashes the engine, so self-approval is a denormalized
flag), rule ids must be trailing comments, and every body predicate must be
defined or `check_kb` rejects the KB.


from typing import Any, Optional

from pydantic import BaseModel, Field


class ProofNode(BaseModel):
    type: str
    goal: Optional[str] = None
    body: Optional[str] = None
    subproof: Optional["ProofNode"] = None
    left: Optional["ProofNode"] = None
    right: Optional["ProofNode"] = None
    rule_id: Optional[str] = None


class Solution(BaseModel):
    substitutions: dict[str, Any] = Field(default_factory=dict)
    proof: ProofNode


class ReasonResult(BaseModel):
    solutions: list[Solution] = Field(default_factory=list)
    query: str = ""
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    content_hash: Optional[str] = None
    version: Optional[str] = None


class KB(BaseModel):
    facts: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    query: Optional[str] = None
    version: Optional[str] = None
    rule_ids: dict[int, str] = Field(default_factory=dict)
    rule_sources: dict[int, int] = Field(default_factory=dict)


# ── Explanation models ──


class ExplainStep(BaseModel):
    """A single typed reasoning step, independent of any natural language.

    ``kind`` is one of ``fact``, ``rule``, ``neg``, ``true``, ``unknown``.
    ``body`` holds the rule-body conjuncts already split (the ``euclid_rule_id``
    marker stripped, ``\\+`` rendered as ``NOT``). A frontend renders these with
    its own localized templates; the English ``steps`` strings are derived from
    the same steps.
    """
    kind: str
    goal: Optional[str] = None
    rule_id: Optional[str] = None
    body: list[str] = Field(default_factory=list)


class Explanation(BaseModel):
    """Natural-language explanation of a single solution's proof."""
    substitutions: dict[str, Any] = Field(default_factory=dict)
    steps: list[str] = Field(default_factory=list)
    structured_steps: list[ExplainStep] = Field(default_factory=list)


class ExplanationResult(BaseModel):
    """Result from explain(): deterministic proof-tree to natural language."""
    query: str = ""
    explanations: list[Explanation] = Field(default_factory=list)
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    content_hash: Optional[str] = None
    version: Optional[str] = None


# ── Diagnosis models ──


class DiagnosisFinding(BaseModel):
    """A single finding from diagnosis: a missing fact, a blocking rule, etc."""
    type: str  # "missing_fact", "missing_rule", "blocking_condition", "satisfied"
    predicate: str
    detail: str = ""


class DiagnosisResult(BaseModel):
    """Result from diagnose(): explains why a query succeeds or fails."""
    query: str = ""
    mode: str = ""  # "why", "why_not", "what_needs"
    holds: bool = False  # whether the query is true or false
    findings: list[DiagnosisFinding] = Field(default_factory=list)
    proof: Optional[ProofNode] = None
    solutions: list[Solution] = Field(default_factory=list)
    conclusion: str = ""
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    content_hash: Optional[str] = None
    version: Optional[str] = None


# ── What-if models ──


class WhatIfResult(BaseModel):
    """Result from what_if(): shows impact of knowledge modifications."""
    query: str = ""
    modifications: str = ""
    before_count: int = 0  # solutions before modification
    after_count: int = 0  # solutions after modification
    delta: str = ""  # "more", "less", "same", "new", "lost"
    solutions_before: list[Solution] = Field(default_factory=list)
    solutions_after: list[Solution] = Field(default_factory=list)
    conclusion: str = ""
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    content_hash: Optional[str] = None
    version: Optional[str] = None


# ── KB check models ──


class KBError(BaseModel):
    """A single issue found in the knowledge base."""
    type: str  # "syntax_error", "undefined_predicate", "circular_rule", etc.
    message: str
    predicate: Optional[str] = None
    line: Optional[int] = None


class PredicateInfo(BaseModel):
    """Predicate inventory entry: name → arities with fact/rule counts.

    Derived from the KB itself (facts and rule heads), so it doubles as the
    contract for LLM extraction without adding any Euclid-IR syntax.
    """
    name: str
    arities: list[int] = Field(default_factory=list)
    facts: int = 0
    rules: int = 0


class KBCheckResult(BaseModel):
    """Result from check_kb(): KB consistency and health report."""
    valid: bool = True
    errors: list[KBError] = Field(default_factory=list)
    warnings: list[KBError] = Field(default_factory=list)
    facts_count: int = 0
    rules_count: int = 0
    predicates_count: int = 0
    predicates: list[PredicateInfo] = Field(default_factory=list)
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    content_hash: Optional[str] = None
    version: Optional[str] = None

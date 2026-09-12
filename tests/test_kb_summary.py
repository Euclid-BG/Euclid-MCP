"""Unit tests for euclid_mcp.kb_summary (generic preloaded-KB digest)."""

from euclid_mcp.kb_summary import build_kb_summary


class TestBuildKbSummary:
    def test_counts_and_inventory(self):
        digest = build_kb_summary(
            "human(socrates)\nhuman(plato)\n"
            "mortal($x) IF human($x)\n"
            "? mortal($who)"
        )
        assert "Statistics: 2 facts, 1 rule, 2 predicates." in digest
        assert "- human/1: 2 facts, 0 rules" in digest
        assert "- mortal/1: 0 facts, 1 rule" in digest

    def test_rules_with_ids(self):
        digest = build_kb_summary(
            "human(socrates)\n"
            "mortal($x) IF human($x)  # rule: MORTAL-1\n"
            "? mortal($who)"
        )
        assert "- mortal($x) IF human($x)  # rule: MORTAL-1" in digest

    def test_rule_display_conjuncts(self):
        digest = build_kb_summary(
            "parent(tom, bob)\nparent(bob, ann)\n"
            "ancestor($x, $y) IF parent($x, $y)\n"
            "ancestor($x, $y) IF parent($x, $z) AND ancestor($z, $y)\n"
            "? ancestor(tom, $who)"
        )
        assert (
            "- ancestor($x, $y) IF parent($x, $z) AND ancestor($z, $y)"
            in digest
        )

    def test_zero_arity_predicates(self):
        digest = build_kb_summary("rainy\nsunny\n? rainy")
        assert "Statistics: 2 facts, 0 rules, 2 predicates." in digest
        assert "- rainy/0: 1 facts, 0 rules" in digest

    def test_query_line(self):
        digest = build_kb_summary("p(a)\n? p($who)")
        assert "Query: p($who)" in digest

    def test_empty_kb(self):
        digest = build_kb_summary("")
        assert "Statistics: 0 facts, 0 rules, 0 predicates." in digest
        assert "Predicates (name/arity: facts, rules):" in digest

    def test_yaml_kb(self):
        kb = """
facts:
  - parent(tom, bob)
rules:
  - ancestor($x, $y) IF parent($x, $y)
query: ancestor(tom, $who)
"""
        digest = build_kb_summary(kb)
        assert "Statistics: 1 fact, 1 rule, 2 predicates." in digest
        assert "- ancestor/2: 0 facts, 1 rule" in digest
        assert "- ancestor($x, $y) IF parent($x, $y)" in digest
        assert "Query: ancestor(tom, $who)" in digest

    def test_invalid_kb_raises(self):
        import pytest
        with pytest.raises(ValueError):
            build_kb_summary("p(a)  # rule: NOT-ALLOWED-ON-FACT")

    def test_or_rule_expanded_with_single_rule_id(self):
        digest = build_kb_summary(
            "human(socrates)\nhero(achilles)\n"
            "mortal($x) IF human($x) OR hero($x)  # rule: M-1\n"
            "? mortal($who)"
        )
        # the two Horn branches each list, and the rule id is shown once
        assert "- mortal($x) IF human($x)  # rule: M-1" in digest
        assert "- mortal($x) IF hero($x)" in digest

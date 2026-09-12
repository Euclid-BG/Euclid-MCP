"""Tests for the positioned parser."""

from euclid_lsp.positioned_parser import parse_positioned


class TestPositionedParser:
    def test_empty(self):
        pkb = parse_positioned("")
        assert pkb.items == []
        assert pkb.facts == []
        assert pkb.rules == []

    def test_single_fact(self):
        pkb = parse_positioned("parent(tom, bob)")
        assert len(pkb.items) == 1
        item = pkb.items[0]
        assert item.kind == "fact"
        assert item.text == "parent(tom, bob)"
        assert item.start_line == 0
        assert item.end_line == 0

    def test_multiple_facts(self):
        text = "parent(tom, bob)\nparent(bob, ann)"
        pkb = parse_positioned(text)
        assert len(pkb.items) == 2
        assert pkb.items[0].start_line == 0
        assert pkb.items[1].start_line == 1

    def test_rule(self):
        text = "ancestor($x, $y) IF\n    parent($x, $y) AND\n    ancestor($y, $z)"
        pkb = parse_positioned(text)
        assert len(pkb.items) == 1
        item = pkb.items[0]
        assert item.kind == "rule"
        assert item.start_line == 0
        assert item.end_line == 2
        assert len(pkb.rules) == 1

    def test_query(self):
        pkb = parse_positioned("? mortal($who)")
        assert len(pkb.items) == 1
        assert pkb.items[0].kind == "query"
        assert pkb.query == "mortal($who)"

    def test_version_directive(self):
        pkb = parse_positioned("@version 1.0\nparent(tom, bob)")
        assert len(pkb.items) == 2
        assert pkb.items[0].kind == "version"
        assert pkb.version == "1.0"
        assert pkb.items[1].kind == "fact"

    def test_comments_skipped(self):
        text = "# This is a comment\nparent(tom, bob)\n// Another comment"
        pkb = parse_positioned(text)
        assert len(pkb.items) == 1
        assert pkb.items[0].kind == "fact"

    def test_rule_with_id(self):
        text = "mortal($x) IF human($x) # RULE: BIO-001"
        pkb = parse_positioned(text)
        assert len(pkb.items) == 1
        assert pkb.items[0].rule_id == "BIO-001"
        assert pkb.rule_ids[0] == "BIO-001"

    def test_zero_arity_fact(self):
        pkb = parse_positioned("system_online")
        assert len(pkb.items) == 1
        assert pkb.items[0].kind == "fact"
        assert pkb.facts == ["system_online"]

    def test_located_item_fields(self):
        text = "parent(tom, bob)"
        pkb = parse_positioned(text)
        item = pkb.items[0]
        assert item.start_col == 0
        assert item.end_col > 0
        assert item.head is None  # fact, not rule
        assert item.body_goals == []

    def test_multiline_rule_tracking(self):
        text = "can_access($u, $r) IF\n    user($u) AND\n    has_role($u, $role)"
        pkb = parse_positioned(text)
        assert len(pkb.items) == 1
        item = pkb.items[0]
        assert item.start_line == 0
        assert item.end_line == 2
        assert len(item.body_goals) >= 2

    def test_multiline_or_continuation(self):
        text = "can_access($u, $r) IF\n    admin($u) OR\n    role($u, dev)"
        pkb = parse_positioned(text)
        assert len(pkb.items) == 1
        item = pkb.items[0]
        assert item.start_line == 0
        assert item.end_line == 2
        assert item.body_goals == ["admin($u)", "role($u, dev)"]

    def test_or_rule_body_goals_split_on_or(self):
        text = "can($u) IF admin($u) OR dev($u)"
        pkb = parse_positioned(text)
        item = pkb.items[0]
        assert item.body_goals == ["admin($u)", "dev($u)"]

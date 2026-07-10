"""Tests for the skills/ playbook loader."""
from app.skill_loader import load_skill, load_skill_tree


def test_load_skill_reads_a_pattern_file():
    content = load_skill("sql-patterns/SKILL.md")
    assert "SQL" in content


def test_load_skill_missing_file_returns_empty_string():
    assert load_skill("does-not-exist/nope.md") == ""


def test_skill_tree_includes_master_playbook_and_references():
    tree = load_skill_tree()
    assert "MASTER PLAYBOOK" in tree
    assert "REFERENCES" in tree
    # reference files are listed but not inlined
    assert "references/data-model.md" in tree

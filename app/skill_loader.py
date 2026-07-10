"""
Skill Loader — reads the skills/ folder structure and assembles context for the LLM.
"""
import os
import streamlit as st

# Resolve the skills directory relative to the project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(_PROJECT_ROOT, "skills")


def _read_file(path: str) -> str:
    """Read a file and return its content, or empty string if missing."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


@st.cache_data(ttl=3600, show_spinner=False)
def load_skill(skill_path: str) -> str:
    """Load a single skill file by path relative to skills/ root.

    Example: load_skill("sql-patterns/SKILL.md")
    """
    full_path = os.path.join(SKILLS_DIR, skill_path)
    return _read_file(full_path)


@st.cache_data(ttl=3600, show_spinner=False)
def load_skill_tree() -> str:
    """Walk the skills/ directory and assemble the full playbook context.

    Returns a single string with all SKILL.md files and their content,
    organized by folder. Reference files are listed but not loaded
    (they're loaded on demand during follow-up questions).
    """
    sections = []

    # Master SKILL.md
    master = _read_file(os.path.join(SKILLS_DIR, "SKILL.md"))
    if master:
        sections.append(f"# MASTER PLAYBOOK\n\n{master}")

    # Walk sub-skill folders
    for entry in sorted(os.listdir(SKILLS_DIR)):
        entry_path = os.path.join(SKILLS_DIR, entry)
        if not os.path.isdir(entry_path):
            continue
        if entry == "references":
            # List reference files but don't auto-load them
            refs = [f for f in os.listdir(entry_path) if f.endswith(".md")]
            if refs:
                ref_list = "\n".join(f"- references/{r}" for r in sorted(refs))
                sections.append(
                    f"# REFERENCES (available on demand)\n\n{ref_list}"
                )
            continue

        # Load sub-skill SKILL.md
        sub_skill = _read_file(os.path.join(entry_path, "SKILL.md"))
        if sub_skill:
            sections.append(f"# SUB-SKILL: {entry}\n\n{sub_skill}")

        # Load all other .md files in the sub-skill folder
        for md_file in sorted(os.listdir(entry_path)):
            if md_file == "SKILL.md" or not md_file.endswith(".md"):
                continue
            content = _read_file(os.path.join(entry_path, md_file))
            if content:
                sections.append(
                    f"## {entry}/{md_file}\n\n{content}"
                )

    return "\n\n---\n\n".join(sections)


def load_reference(ref_name: str) -> str:
    """Load a specific reference file from skills/references/.

    Example: load_reference("data-model.md")
    """
    return _read_file(os.path.join(SKILLS_DIR, "references", ref_name))

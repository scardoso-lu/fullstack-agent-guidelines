import re
from pathlib import Path

SKILL_MD = Path(__file__).parents[3] / "SKILL.md"
DESCRIPTION_CHAR_LIMIT = 1536


def _extract_description(text: str) -> str:
    """Return the value of the YAML frontmatter `description` block, stripped of indentation."""
    m = re.search(r"^description: \|\n((?:  .*\n|\n)*)", text, re.MULTILINE)
    if not m:
        return ""
    lines = [line[2:] if line.startswith("  ") else line for line in m.group(1).splitlines()]
    return "\n".join(lines).strip()


def test_skill_md_description_within_claude_ui_limit():
    text = SKILL_MD.read_text()
    description = _extract_description(text)
    assert description, "SKILL.md is missing a `description` frontmatter block"
    length = len(description)
    assert length <= DESCRIPTION_CHAR_LIMIT, (
        f"SKILL.md description is {length} chars, exceeding the {DESCRIPTION_CHAR_LIMIT}-char "
        f"Claude UI import limit by {length - DESCRIPTION_CHAR_LIMIT} chars. "
        "Trim the `description` field in the YAML frontmatter."
    )

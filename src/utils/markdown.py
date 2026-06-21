import re

_SUMMARY_MAX = 220
_MD_INLINE = re.compile(r"(\*\*|__|\*|_|`)")
_FRONTMATTER = re.compile(r"^---\n.*?\n---\n", re.DOTALL)


def extract_summary(content: str) -> str:
    """Return the first prose paragraph after the H1 title, stripped of inline markdown."""
    content = _FRONTMATTER.sub("", content, count=1).lstrip()
    without_title = re.sub(r"^#[^#][^\n]*\n", "", content, count=1).lstrip()
    for para in without_title.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        non_empty = [ln for ln in para.splitlines() if ln.strip()]
        if all(ln.lstrip().startswith(">") or ln.lstrip().startswith("---") for ln in non_empty):
            continue
        flat = re.sub(r"\s+", " ", para)
        return _MD_INLINE.sub("", flat)[:_SUMMARY_MAX]
    return ""

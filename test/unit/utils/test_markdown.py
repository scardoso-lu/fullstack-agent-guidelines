import pytest

from src.utils.markdown import extract_summary

_PROSE = "Use when you need a summary paragraph."


def test_no_frontmatter_returns_first_prose():
    content = f"# My Title\n\n{_PROSE}\n\n## Section\n\nMore text."
    assert extract_summary(content) == _PROSE


def test_frontmatter_is_skipped():
    content = f"---\nmodel: sonnet\neffort: extract\n---\n\n# My Title\n\n{_PROSE}"
    assert extract_summary(content) == _PROSE


def test_frontmatter_fields_absent_from_summary():
    content = f"---\nmodel: opus\neffort: high\n---\n\n# Title\n\n{_PROSE}"
    result = extract_summary(content)
    assert "model" not in result
    assert "opus" not in result
    assert "effort" not in result


def test_frontmatter_with_all_real_values():
    for model in ("sonnet", "opus"):
        for effort in ("high", "extract"):
            content = f"---\nmodel: {model}\neffort: {effort}\n---\n\n# Title\n\n{_PROSE}"
            assert extract_summary(content) == _PROSE


def test_no_frontmatter_no_title_returns_empty():
    assert extract_summary("") == ""


def test_only_title_returns_empty():
    assert extract_summary("# Just a Title\n") == ""


def test_summary_truncated_to_220_chars():
    long = "word " * 60
    content = f"# T\n\n{long}"
    result = extract_summary(content)
    assert len(result) <= 220

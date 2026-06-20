from __future__ import annotations

import re
from collections import defaultdict

from src.application.dto.metadata_dto import ExampleMetaDto, GuidelineMetaDto, MetadataDto
from src.infrastructure.repositories.contract import (
    ExampleRepositoryInterface,
    GuidelineRepositoryInterface,
)

# Characters to include in the summary — enough for an agent to understand the topic
_SUMMARY_MAX = 220
# Inline markdown markers to strip before returning the summary
_MD_INLINE = re.compile(r"(\*\*|__|\*|_|`)")


def _extract_summary(content: str) -> str:
    """Return the first prose paragraph after the H1 title, stripped of markdown."""
    without_title = re.sub(r"^#[^#][^\n]*\n", "", content, count=1).lstrip()
    # Walk paragraphs until we find one that is actual prose (not a blockquote / HR)
    for para in without_title.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        non_empty = [ln for ln in para.splitlines() if ln.strip()]
        # Skip paragraphs where every line is a blockquote (>) or a horizontal rule (---)
        if all(ln.lstrip().startswith(">") or ln.lstrip().startswith("---") for ln in non_empty):
            continue
        flat = re.sub(r"\s+", " ", para)
        return _MD_INLINE.sub("", flat)[:_SUMMARY_MAX]
    return ""


class GetMetadataUseCase:
    def __init__(
        self,
        guideline_repo: GuidelineRepositoryInterface,
        example_repo: ExampleRepositoryInterface,
    ) -> None:
        self._guidelines = guideline_repo
        self._examples = example_repo

    async def execute(self) -> MetadataDto:
        guidelines = await self._guidelines.get_all()
        examples = await self._examples.get_all()

        # Group guidelines by stack, sorted by slug within each group
        g_by_stack: dict[str, list[GuidelineMetaDto]] = defaultdict(list)
        for g in sorted(guidelines, key=lambda x: x.slug):
            g_by_stack[g.stack].append(
                GuidelineMetaDto(
                    slug=g.slug,
                    stack=g.stack,
                    title=g.title,
                    summary=_extract_summary(g.content),
                )
            )

        # Group examples by stack, sorted by name within each group
        e_by_stack: dict[str, list[ExampleMetaDto]] = defaultdict(list)
        for e in sorted(examples, key=lambda x: x.name):
            e_by_stack[e.stack].append(
                ExampleMetaDto(
                    name=e.name,
                    stack=e.stack,
                    layer=e.layer,
                    filename=e.filename,
                    description=e.description,
                )
            )

        return MetadataDto(
            guidelines=dict(g_by_stack),
            examples=dict(e_by_stack),
            total_guidelines=len(guidelines),
            total_examples=len(examples),
        )

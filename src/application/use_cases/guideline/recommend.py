import re

from src.application.dto.guideline_dto import GuidelineSummaryDto, RecommendationResultDto
from src.domain.entities.guideline import Guideline
from src.infrastructure.repositories.contract import GuidelineRepositoryInterface

_STOPWORDS = frozenset({
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "is", "are", "am",
    "be", "as", "by", "i", "my", "me", "we", "our", "it", "its", "this", "that",
    "with", "from", "into", "and", "or", "not", "no", "do", "did", "does",
    "have", "has", "had", "will", "can", "could", "should", "would", "may",
    "might", "must", "need", "want", "about", "how", "when", "what",
    "which", "who", "where", "why", "just", "more", "up", "use", "using",
    "used", "add", "new", "some", "any", "all", "but", "get", "set",
    "also", "very", "such",
})

_VALID_STACKS = frozenset({"backend", "frontend"})
_TOP_N = 5


def _keywords(text: str) -> set[str]:
    return {
        w for w in re.findall(r"[a-z]+", text.lower())
        if len(w) > 2 and w not in _STOPWORDS
    }


def _score(g: Guideline, keywords: set[str]) -> int:
    title = g.title.lower()
    content = g.content.lower()
    score = 0
    for kw in keywords:
        if kw in title:
            score += 3
        if any(kw in tag for tag in g.tags):
            score += 2
        elif kw in content:
            score += 1
    return score


class RecommendGuidelinesUseCase:
    def __init__(self, repo: GuidelineRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self, task: str, stack: str | None = None) -> RecommendationResultDto:
        if not task or not task.strip():
            raise ValueError("Task description cannot be empty")

        task = task.strip()

        if stack is not None:
            stack = stack.strip().lower()
            if stack not in _VALID_STACKS:
                raise ValueError(
                    f"Unknown stack '{stack}'. Valid values: {sorted(_VALID_STACKS)}"
                )

        guidelines = await self.repo.get_all()

        if stack is not None:
            guidelines = [g for g in guidelines if g.stack == stack]

        keywords = _keywords(task)
        if not keywords:
            return RecommendationResultDto(items=[], task=task, total=0)

        scored = sorted(
            ((g, _score(g, keywords)) for g in guidelines),
            key=lambda x: x[1],
            reverse=True,
        )

        top = [g for g, score in scored[:_TOP_N] if score > 0]

        items = [
            GuidelineSummaryDto(
                slug=g.slug, stack=g.stack, title=g.title, tags=g.tags, summary=g.summary
            )
            for g in top
        ]
        return RecommendationResultDto(items=items, task=task, total=len(items))

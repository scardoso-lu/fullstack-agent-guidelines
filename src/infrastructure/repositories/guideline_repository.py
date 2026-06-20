import re
from functools import lru_cache
from pathlib import Path

import aiofiles

from src.domain.entities.guideline import VALID_STACKS, Guideline
from src.infrastructure.repositories.contract import GuidelineRepositoryInterface
from src.utils.markdown import extract_summary


class GuidelineRepository(GuidelineRepositoryInterface):
    def __init__(self, guidelines_dir: Path) -> None:
        self._dir = guidelines_dir
        self._cache: dict[str, Guideline] | None = None

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_title(content: str) -> str:
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _tags_from_slug(slug: str) -> list[str]:
        # slug = "backend/01-project-structure" → tags from the filename part
        filename = slug.split("/")[-1]
        parts = filename.split("-")
        return [p for p in parts[1:] if p]

    async def _read_file(self, path: Path, stack: str) -> Guideline:
        async with aiofiles.open(path, encoding="utf-8") as f:
            content = await f.read()
        slug = f"{stack}/{path.stem}"
        title = self._parse_title(content) or path.stem
        tags = self._tags_from_slug(slug)
        summary = extract_summary(content)
        return Guideline(slug=slug, stack=stack, title=title, content=content, tags=tags, summary=summary)

    async def _load_all(self) -> dict[str, Guideline]:
        if self._cache is not None:
            return self._cache

        cache: dict[str, Guideline] = {}
        base = Path(self._dir)

        for stack in VALID_STACKS:
            stack_dir = base / stack
            if not stack_dir.is_dir():
                continue
            for path in sorted(stack_dir.glob("*.md")):
                g = await self._read_file(path, stack)
                cache[g.slug] = g

        self._cache = cache
        return self._cache

    # ------------------------------------------------------------------ #
    # Interface implementation
    # ------------------------------------------------------------------ #

    async def get_all(self) -> list[Guideline]:
        cache = await self._load_all()
        return list(cache.values())

    async def get_by_slug(self, slug: str) -> Guideline | None:
        cache = await self._load_all()
        return cache.get(slug)

    async def search(self, query: str) -> list[Guideline]:
        cache = await self._load_all()
        q = query.lower()
        return [
            g
            for g in cache.values()
            if q in g.title.lower()
            or q in g.content.lower()
            or any(q in t for t in g.tags)
        ]


@lru_cache(maxsize=1)
def get_guideline_repository() -> GuidelineRepository:
    from src.config.settings import get_config

    return GuidelineRepository(Path(get_config().GUIDELINES_DIR))

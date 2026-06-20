# Description: Repository implementation — concrete filesystem storage behind the interface
# Layer: infrastructure
#
# Key rules:
#   - Inherits from the interface — type system enforces the contract
#   - lru_cache(maxsize=1) on the factory makes it a singleton (one instance per process)
#   - In-memory cache (_cache) avoids redundant I/O on repeated calls
#   - aiofiles for non-blocking file reads — never use open() in an async function
#   - Subdirectory layout: guidelines/{backend,frontend}/*.md → slug = "backend/01-..."
#   - No business logic here — just fetch, parse, cache, return

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import aiofiles

from src.domain.entities.guideline import Guideline
from src.infrastructure.repositories.contract import GuidelineRepositoryInterface

_VALID_STACKS = ("backend", "frontend")


class GuidelineRepository(GuidelineRepositoryInterface):

    def __init__(self, guidelines_dir: Path) -> None:
        self._dir = guidelines_dir
        self._cache: dict[str, Guideline] | None = None   # None = not loaded yet

    # --- private helpers --------------------------------------------------

    @staticmethod
    def _parse_title(content: str) -> str:
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _tags_from_stem(stem: str) -> list[str]:
        # "01-project-structure" → ["project", "structure"]
        return [p for p in stem.split("-")[1:] if p]

    async def _load_all(self) -> dict[str, Guideline]:
        if self._cache is not None:          # warm cache — skip disk I/O
            return self._cache
        cache: dict[str, Guideline] = {}
        base = Path(self._dir)
        for stack in _VALID_STACKS:
            stack_dir = base / stack
            if not stack_dir.is_dir():
                continue
            for path in sorted(stack_dir.glob("*.md")):
                slug = f"{stack}/{path.stem}"   # "backend/01-project-structure"
                async with aiofiles.open(path, encoding="utf-8") as f:
                    content = await f.read()
                cache[slug] = Guideline(
                    slug=slug,
                    stack=stack,
                    title=self._parse_title(content) or path.stem,
                    content=content,
                    tags=self._tags_from_stem(path.stem),
                )
        self._cache = cache
        return self._cache

    # --- interface implementation -----------------------------------------

    async def get_all(self) -> list[Guideline]:
        return list((await self._load_all()).values())

    async def get_by_slug(self, slug: str) -> Guideline | None:
        return (await self._load_all()).get(slug)

    async def search(self, query: str) -> list[Guideline]:
        q = query.lower()
        return [
            g for g in (await self._load_all()).values()
            if q in g.title.lower() or q in g.content.lower()
        ]


# --- singleton factory --------------------------------------------------------

@lru_cache(maxsize=1)
def get_guideline_repository() -> GuidelineRepository:
    # Import deferred to avoid circular imports at module load time
    from src.config.settings import get_config
    return GuidelineRepository(Path(get_config().GUIDELINES_DIR))


# =============================================================================
# ANTI-PATTERN — do NOT do this
# =============================================================================

# 1. Flat glob — misses the backend/frontend subdirectory layout:
#
# async def _load_all(self):
#     for path in Path(self._dir).glob("*.md"):   ← finds nothing; files are in subfolders
#         ...

# 2. Synchronous file read inside an async function — blocks the event loop:
#
# async def _load_all(self):
#     for path in Path(self._dir).glob("*.md"):
#         content = open(path).read()     ← blocks all other coroutines while reading

# 3. No cache — re-reads every .md file on every request:
#
# async def get_all(self):
#     result = []
#     for path in Path(self._dir).glob("*.md"):  ← disk I/O on every call
#         ...
#     return result

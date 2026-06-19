from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import aiofiles

from src.domain.entities.example import Example
from src.infrastructure.repositories.contract import ExampleRepositoryInterface

_LAYERS = ("domain", "application", "infrastructure", "presentation")


class ExampleRepository(ExampleRepositoryInterface):

    def __init__(self, examples_dir: Path) -> None:
        self._dir = examples_dir
        self._cache: list[Example] | None = None

    @staticmethod
    def _parse_description(content: str) -> str:
        match = re.search(r"^#\s*Description:\s*(.+)$", content, re.MULTILINE)
        return match.group(1).strip() if match else ""

    async def _load_all(self) -> list[Example]:
        if self._cache is not None:
            return self._cache
        examples: list[Example] = []
        for layer in _LAYERS:
            layer_dir = Path(self._dir) / layer
            if not layer_dir.is_dir():
                continue
            for path in sorted(layer_dir.glob("*.py")):
                async with aiofiles.open(path, encoding="utf-8") as f:
                    content = await f.read()
                examples.append(
                    Example(
                        name=f"{layer}/{path.stem}",
                        layer=layer,
                        filename=path.name,
                        description=self._parse_description(content),
                        content=content,
                    )
                )
        self._cache = examples
        return self._cache

    async def get_all(self) -> list[Example]:
        return await self._load_all()

    async def get_by_name(self, name: str) -> Example | None:
        return next((e for e in await self._load_all() if e.name == name), None)

    async def get_by_layer(self, layer: str) -> list[Example]:
        return [e for e in await self._load_all() if e.layer == layer]


@lru_cache(maxsize=1)
def get_example_repository() -> ExampleRepository:
    from src.config.settings import get_config

    return ExampleRepository(Path(get_config().EXAMPLES_DIR))

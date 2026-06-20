from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import aiofiles

from src.domain.entities.example import Example
from src.infrastructure.repositories.contract import ExampleRepositoryInterface
from src.utils.logger import get_logger

_logger = get_logger("repo.example")

_BACKEND_LAYERS = ("domain", "application", "infrastructure", "presentation")
_FRONTEND_GLOBS = ("*.ts", "*.tsx")


class ExampleRepository(ExampleRepositoryInterface):

    def __init__(self, examples_dir: Path) -> None:
        self._dir = examples_dir
        self._cache: list[Example] | None = None
        _logger.info("ExampleRepository init dir=%s", examples_dir)

    @staticmethod
    def _parse_description(content: str) -> str:
        match = re.search(r"^#\s*Description:\s*(.+)$", content, re.MULTILINE)
        return match.group(1).strip() if match else ""

    async def _load_all(self) -> list[Example]:
        if self._cache is not None:
            _logger.debug("cache hit — returning %d examples", len(self._cache))
            return self._cache

        _logger.info("cache miss — loading examples from %s", self._dir)
        examples: list[Example] = []
        base = Path(self._dir)

        # Backend: examples/backend/{layer}/*.py
        backend_dir = base / "backend"
        if backend_dir.is_dir():
            for layer in _BACKEND_LAYERS:
                layer_dir = backend_dir / layer
                if not layer_dir.is_dir():
                    _logger.debug("layer dir not found layer=%s path=%s", layer, layer_dir)
                    continue
                for path in sorted(layer_dir.glob("*.py")):
                    _logger.debug("loading example path=%s", path)
                    async with aiofiles.open(path, encoding="utf-8") as f:
                        content = await f.read()
                    examples.append(
                        Example(
                            name=f"backend/{layer}/{path.stem}",
                            stack="backend",
                            layer=layer,
                            filename=path.name,
                            description=self._parse_description(content),
                            content=content,
                        )
                    )

        # Frontend: examples/frontend/*.ts | *.tsx
        frontend_dir = base / "frontend"
        if frontend_dir.is_dir():
            paths = sorted(
                p for glob in _FRONTEND_GLOBS for p in frontend_dir.glob(glob)
            )
            for path in paths:
                _logger.debug("loading example path=%s", path)
                async with aiofiles.open(path, encoding="utf-8") as f:
                    content = await f.read()
                examples.append(
                    Example(
                        name=f"frontend/{path.stem}",
                        stack="frontend",
                        layer="frontend",
                        filename=path.name,
                        description=self._parse_description(content),
                        content=content,
                    )
                )

        self._cache = examples
        _logger.info("examples loaded total=%d", len(self._cache))
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

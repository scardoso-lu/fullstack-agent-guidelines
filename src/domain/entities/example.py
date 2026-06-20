from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Example:
    name: str         # "backend/domain/01_entity" | "frontend/01_api_service"
    stack: str        # "backend" | "frontend"
    layer: str        # "domain" | "application" | ... | "frontend"
    filename: str     # "01_entity.py" | "01_api_service.ts"
    description: str  # parsed from first "# Description: ..." comment line
    content: str      # full file content

    @staticmethod
    def _mock(
        name: str = "backend/domain/01_entity",
        stack: str = "backend",
        layer: str = "domain",
        description: str = "Mock example",
    ) -> "Example":
        return Example(
            name=name,
            stack=stack,
            layer=layer,
            filename="01_entity.py",
            description=description,
            content="# Mock content\n",
        )

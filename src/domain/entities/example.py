from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Example:
    name: str           # "domain/01_entity"  (layer/filename_stem)
    layer: str          # "domain" | "application" | "infrastructure" | "presentation"
    filename: str       # "01_entity.py"
    description: str    # parsed from first "# Description: ..." comment line
    content: str        # full file content

    @staticmethod
    def _mock(
        name: str = "domain/01_entity",
        layer: str = "domain",
        description: str = "Mock example",
    ) -> "Example":
        return Example(
            name=name,
            layer=layer,
            filename="01_entity.py",
            description=description,
            content="# Mock content\n",
        )

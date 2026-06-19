from __future__ import annotations

from src.application.dto import BaseSchema


class GuidelineMetaDto(BaseSchema):
    slug: str    # "backend/01-project-structure"
    stack: str   # "backend" | "frontend"
    title: str
    summary: str  # first paragraph of content — enough to decide whether to read it


class ExampleMetaDto(BaseSchema):
    name: str        # "backend/domain/01_entity" | "frontend/01_api_service"
    stack: str       # "backend" | "frontend"
    layer: str       # "domain" | "application" | ... | "frontend"
    filename: str    # "01_entity.py" | "01_api_service.ts"
    description: str # parsed from "# Description:" comment


class MetadataDto(BaseSchema):
    guidelines: dict[str, list[GuidelineMetaDto]]  # keyed by stack
    examples: dict[str, list[ExampleMetaDto]]       # keyed by stack
    total_guidelines: int
    total_examples: int

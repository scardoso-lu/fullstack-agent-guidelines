from __future__ import annotations

from src.application.dto import BaseSchema


class ExampleSummaryDto(BaseSchema):
    name: str
    stack: str
    layer: str
    filename: str
    description: str


class ExampleDto(ExampleSummaryDto):
    content: str


class ExampleListDto(BaseSchema):
    items: list[ExampleSummaryDto]
    total: int
    stack_filter: str | None = None
    layer_filter: str | None = None

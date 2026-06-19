from src.application.dto import BaseSchema


class GuidelineSummaryDto(BaseSchema):
    """Lightweight representation for listing — omits full content."""

    slug: str
    stack: str
    title: str
    tags: list[str]


class GuidelineDto(GuidelineSummaryDto):
    """Full representation including markdown content."""

    content: str


class GuidelineListDto(BaseSchema):
    items: list[GuidelineSummaryDto]
    total: int
    stack_filter: str | None = None


class SearchResultDto(BaseSchema):
    items: list[GuidelineDto]
    query: str
    total: int

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Guideline:
    slug: str
    title: str
    content: str
    tags: list[str] = field(default_factory=list)

    @staticmethod
    def _mock(slug: str = "01-test", title: str = "Test Guideline") -> "Guideline":
        return Guideline(
            slug=slug,
            title=title,
            content=f"# {title}\n\nMock content for testing.",
            tags=["test"],
        )

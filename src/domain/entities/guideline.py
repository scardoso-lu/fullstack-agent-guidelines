from dataclasses import dataclass, field

VALID_STACKS: frozenset[str] = frozenset(
    {
        "backend",
        "frontend",
        "infra",
        "agile",
        "qa",
        "architecture",
        "security",
        "structure",
    }
)


@dataclass(frozen=True)
class Guideline:
    slug: str    # "backend/01-project-structure" | "frontend/01-project-structure"
    stack: str   # "backend" | "frontend"
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    summary: str = ""

    @staticmethod
    def _mock(
        slug: str = "backend/01-test",
        stack: str = "backend",
        title: str = "Test Guideline",
    ) -> "Guideline":
        return Guideline(
            slug=slug,
            stack=stack,
            title=title,
            content=f"# {title}\n\nMock content for testing.",
            tags=["test"],
            summary="Mock content for testing.",
        )

# Description: Value object — frozen dataclass for immutable domain concepts
# Layer: domain
#
# Key rules:
#   - frozen=True: equality by value, hashable, cannot be mutated
#   - No ORM mapping — value objects are embedded in entities or used standalone
#   - Validation in __post_init__ — invalid state is impossible to construct
#   - _mock() factory for tests — no pytest fixture file needed

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Email:
    """Wraps a string email so the type system enforces validity at construction."""

    address: str

    def __post_init__(self) -> None:
        if "@" not in self.address or len(self.address) > 254:
            raise ValueError(f"Invalid email address: {self.address!r}")

    @property
    def domain(self) -> str:
        return self.address.split("@", 1)[1]

    @staticmethod
    def _mock(address: str = "user@example.com") -> "Email":
        return Email(address=address)


@dataclass(frozen=True)
class Guideline:
    """Read-only domain object loaded from a markdown file. No DB mapping needed."""

    slug: str       # "backend/01-project-structure" | "frontend/01-project-structure"
    stack: str      # "backend" | "frontend"
    title: str
    content: str
    tags: list[str] = field(default_factory=list)

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
            content=f"# {title}\n\nTest content.",
            tags=["test"],
        )


# =============================================================================
# ANTI-PATTERN — do NOT do this
# =============================================================================

class EmailBad:
    def __init__(self, address):
        self.address = address   # mutable, no validation — anyone can set address = ""

# Passing raw dicts instead of value objects loses type safety:
# create_user({"email": "bad"})  ← what fields? is it validated?

# Mutable guideline — enables accidental mutation of shared domain state:
class GuidelineBad:
    def __init__(self, slug, title, content):
        self.slug = slug
        self.title = title
        self.content = content     # caller can mutate .content at any time

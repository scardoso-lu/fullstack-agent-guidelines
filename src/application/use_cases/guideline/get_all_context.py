from src.infrastructure.repositories.contract import GuidelineRepositoryInterface


class GetAllContextUseCase:
    def __init__(self, repo: GuidelineRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self, stack: str | None = None) -> str:
        guidelines = await self.repo.get_all()

        if stack is not None:
            guidelines = [g for g in guidelines if g.stack == stack.strip().lower()]

        separator = "\n\n---\n\n"
        return separator.join(
            f"<!-- Guideline: {g.slug} -->\n{g.content}"
            for g in sorted(guidelines, key=lambda g: g.slug)
        )

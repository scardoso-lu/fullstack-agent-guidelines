from src.infrastructure.repositories.contract import GuidelineRepositoryInterface


class GetAllContextUseCase:
    def __init__(self, repo: GuidelineRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self) -> str:
        guidelines = await self.repo.get_all()
        separator = "\n\n---\n\n"
        return separator.join(
            f"<!-- Guideline: {g.slug} -->\n{g.content}"
            for g in sorted(guidelines, key=lambda g: g.slug)
        )

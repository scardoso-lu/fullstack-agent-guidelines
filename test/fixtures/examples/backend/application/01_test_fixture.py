# Description: Fixture DTO for testing — Pydantic model example
# Layer: application

from pydantic import BaseModel


class FixtureDto(BaseModel):
    id: int
    name: str

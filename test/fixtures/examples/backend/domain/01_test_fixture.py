# Description: Fixture entity for testing — frozen dataclass example
# Layer: domain

from dataclasses import dataclass


@dataclass(frozen=True)
class FixtureEntity:
    id: int
    name: str

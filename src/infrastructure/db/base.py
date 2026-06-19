from typing import Any
from functools import lru_cache

import sqlalchemy as sq
from pydantic_core import core_schema
from snowflake import SnowflakeGenerator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def _get_snowflake_generator(instance: int = 1) -> SnowflakeGenerator:
    return SnowflakeGenerator(instance)


def generate_snowflake_id() -> int:
    return next(_get_snowflake_generator())


class IdMixin:
    _id: Mapped[int] = mapped_column(
        "id",
        sq.BigInteger,
        primary_key=True,
        nullable=False,
        default=generate_snowflake_id,
    )

    @property
    def id(self) -> str:
        return str(self._id)


class IdInt(str):
    @classmethod
    def validate(cls, value: Any) -> int:
        def is_64bits(num: int) -> bool:
            return -(2**63) <= num < 2**63

        if not (isinstance(value, str) and value.isdigit()):
            raise ValueError("Value must be a string representing an integer")
        int_value = int(value)
        if not is_64bits(int_value):
            raise ValueError("Value must be a 64-bit integer")
        return int_value

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any):
        return core_schema.no_info_after_validator_function(
            cls.validate, core_schema.str_schema()
        )

# Description: DTOs — Pydantic models that cross layer boundaries safely
# Layer: application
#
# Key rules:
#   - DTOs are the ONLY thing that crosses from application → presentation
#   - Never expose ORM entities (User, Note) to routes or MCP tools
#   - BaseSchema sets shared Pydantic config once; all DTOs inherit it
#   - from_attributes=True lets Pydantic read SQLAlchemy model fields directly
#   - Separate "summary" (list) vs "detail" (full) DTOs to avoid over-fetching

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Shared config for all DTOs. Define once, inherit everywhere."""

    model_config = ConfigDict(
        use_enum_values=True,       # serialize enums as their value, not name
        from_attributes=True,       # allow model_validate(orm_object)
        arbitrary_types_allowed=True,
    )


# --- output DTOs (what the use case returns) ----------------------------------

class UserSummaryDto(BaseSchema):
    """Used in list endpoints — minimal fields to avoid N+1 over-fetching."""
    id: int
    email: str


class UserDto(UserSummaryDto):
    """Used in detail endpoints — inherits summary fields, adds extras."""
    is_active: bool


class UserListDto(BaseSchema):
    items: list[UserSummaryDto]
    total: int


# --- input DTOs (what the use case receives from presentation) ----------------

class CreateUserDto(BaseSchema):
    email: str
    password: str   # plain text — use case will hash via entity.password setter


# --- usage in a use case ------------------------------------------------------

# result: UserDto = UserDto.model_validate(user_orm_object)
# result: UserDto = UserDto(id=1, email="a@b.com", is_active=True)


# =============================================================================
# ANTI-PATTERN — do NOT do this
# =============================================================================

# Returning the ORM object directly from a use case:
# async def execute(self) -> User:          ← leaks DB column names to routes
#     return await self.repo.get_by_id(1)

# Using plain dicts:
# return {"id": 1, "email": "a@b.com"}     ← no type-checking, no docs, breaks silently

# Description: Write use case — create operation with input validation, entity construction, DTO return
# Layer: application
#
# Key rules:
#   - One use case = one operation (SRP) — don't combine create + update in one class
#   - Validate ALL input before any I/O — fail fast with a clear error
#   - Entity owns construction logic (ID generation, password hashing, invariants)
#   - Use case never touches HTTP, DB sessions, or config — only the interface
#   - Return a DTO; callers never see the domain entity

from __future__ import annotations

from src.application.dto.user_dto import UserDto
from src.infrastructure.repositories.contract import UserRepositoryInterface
from src.domain.entities.user import User


class CreateUserUseCase:
    """
    Register a new user account.

    Raises:
        ValueError: if email or password are blank / too short
        ConflictError: if a user with this email already exists
    """

    def __init__(self, repo: UserRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self, email: str, password: str) -> UserDto:
        # 1. Validate input — before any I/O, raise with a meaningful message
        if not email or "@" not in email:
            raise ValueError("A valid email address is required")
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters")

        # 2. Guard against duplicates — read before write
        existing = await self.repo.get_by_email(email.lower())
        if existing is not None:
            from src.utils.exc import ConflictError
            raise ConflictError(f"Email '{email}' is already registered")

        # 3. Construct entity — ID generation and hashing live in the entity, not here
        user = User(email=email.lower())
        user.password = password    # setter hashes with bcrypt; plain text never stored

        # 4. Persist
        saved = await self.repo.save(user)

        # 5. Return DTO — never return the ORM entity to the presentation layer
        return UserDto.model_validate(saved)


# =============================================================================
# ANTI-PATTERN — do NOT do this
# =============================================================================

# 1. Hashing inside the use case — business logic that belongs to the entity:
#
# import bcrypt
#
# class CreateUserUseCaseBad:
#     async def execute(self, email: str, password: str):
#         hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
#         user = User(email=email, password_hash=hashed)   # ← duplicates entity invariant
#         ...

# 2. Returning the ORM entity directly:
#
# async def execute(self, email: str, password: str) -> User:   # ← leaks ORM to caller
#     ...
#     return await self.repo.save(user)

# 3. Skipping input validation:
#
# async def execute(self, email: str, password: str):
#     user = User(email=email)
#     user.password = password        # no check — empty string gets hashed and stored
#     return await self.repo.save(user)

# 4. Combining create + update in one use case:
#
# class UpsertUserUseCase:           # two operations, two responsibilities
#     async def execute(self, id: int | None, ...):
#         if id:
#             return await self._update(id, ...)
#         return await self._create(...)

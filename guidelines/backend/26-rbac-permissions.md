---
model: opus
effort: high
---

# RBAC Permissions — Roles in DB, Permission Constants, Use-Case Enforcement

Use when implementing any access control — admin-only features, role-based visibility, or per-resource permissions. Defines the correct RBAC pattern for this stack: roles stored in the database (not env vars, not code), permission strings as typed constants, checks enforced in use cases, and frontend guards for UI only. AI agents and vibecoding tools almost always get this wrong — the most common mistake is reading allowed groups or roles from environment variables.

## The Anti-Patterns (What AI Always Generates)

These are the patterns to recognise and refuse:

```python
# ❌ WRONG — permissions read from env var
ALLOWED_GROUPS = os.environ.get("ALLOWED_GROUPS", "admin,superuser").split(",")

@router.get("/admin/data")
def get_data(user: User = Depends(get_current_user)):
    if user.role not in ALLOWED_GROUPS:
        raise HTTPException(403)
```

Adding a new role now requires a code change and a redeploy. It is not manageable, not auditable, and not testable without setting env vars.

```python
# ❌ WRONG — magic role strings hardcoded in route handlers
@router.delete("/articles/{id}")
def delete_article(user: User = Depends(get_current_user)):
    if user.role != "admin":          # magic string; scattered across 30 routes
        raise HTTPException(403)
```

```python
# ❌ WRONG — single boolean flag that doesn't scale
class User(Base, IdMixin):
    is_admin: Mapped[bool] = mapped_column(default=False)
    # What happens when you need "editor", "moderator", "billing_admin"?
```

```python
# ❌ WRONG — permission check only in the frontend
// React component
if (user.role === "admin") {
  return <DeleteButton />;
}
// The API endpoint has no server-side check — anyone with a REST client bypasses this
```

## The Correct Pattern

### 1 — Roles Are a Reference-Data Table

Roles follow the lookup-table pattern from `backend/25-reference-data`. Each role carries a `permissions` JSON array — the set of capability strings that role grants.

**`src/domain/entities/role.py`**
```python
import sqlalchemy as sq
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from src.infrastructure.db.base import Base, IdMixin

class Role(Base, IdMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(sq.String(255), nullable=False)
    slug: Mapped[str] = mapped_column(sq.String(255), unique=True, nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(sq.Boolean, default=True, nullable=False)
```

The `User` entity holds a FK to `Role`:

**`src/domain/entities/user.py`**
```python
from sqlalchemy.orm import relationship

class User(Base, IdMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(sq.String(255), unique=True, nullable=False)
    role_id: Mapped[int] = mapped_column(sq.ForeignKey("roles.id"), nullable=False)
    role: Mapped["Role"] = relationship("Role", lazy="joined")
```

### 2 — Permission Strings Are Typed Constants

All permission identifiers live in the constants class. No magic strings anywhere else in the codebase.

**`src/config/constants.py`**
```python
class C:
    # Permission strings — format: "resource:action"
    PERM_ARTICLES_READ   = "articles:read"
    PERM_ARTICLES_WRITE  = "articles:write"
    PERM_ARTICLES_DELETE = "articles:delete"
    PERM_USERS_READ      = "users:read"
    PERM_USERS_MANAGE    = "users:manage"
    PERM_SETTINGS_READ   = "settings:read"
    PERM_SETTINGS_WRITE  = "settings:write"
    PERM_ROLES_MANAGE    = "roles:manage"
```

### 3 — Seed Roles with Initial Permissions

**`alembic/versions/xxxx_seed_roles.py`**
```python
import sqlalchemy as sa
from alembic import op

def upgrade() -> None:
    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("name", sa.String),
            sa.column("slug", sa.String),
            sa.column("permissions", sa.JSON),
            sa.column("is_active", sa.Boolean),
        ),
        [
            {
                "name": "Admin",
                "slug": "admin",
                "permissions": [
                    "articles:read", "articles:write", "articles:delete",
                    "users:read", "users:manage",
                    "settings:read", "settings:write",
                    "roles:manage",
                ],
                "is_active": True,
            },
            {
                "name": "Editor",
                "slug": "editor",
                "permissions": ["articles:read", "articles:write"],
                "is_active": True,
            },
            {
                "name": "Viewer",
                "slug": "viewer",
                "permissions": ["articles:read"],
                "is_active": True,
            },
        ],
    )
```

Admins can add roles and adjust permissions through the admin UI — no code change, no redeploy.

### 4 — JWT Contains Role Slug, Not Permissions

The JWT payload includes only stable identifiers. Permission lists are fetched fresh from the database on every request — so revoking a permission takes effect immediately, not after token expiry.

**`src/infrastructure/services/token_service.py`**
```python
def create_access_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role.slug,   # stable slug, not a permissions list
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, get_config().JWT_SECRET, algorithm="HS256")
```

The `get_current_user` dependency resolves the full user (with role and permissions) from the DB on every authenticated request:

**`src/infrastructure/services/auth_dependency.py`**
```python
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from src.infrastructure.repositories.contract import UserRepositoryInterface
from src.utils.exc import UnauthorizedError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_repo: UserRepositoryInterface = Depends(get_user_repository),
) -> User:
    payload = decode_token(token)           # raises UnauthorizedError if invalid
    user = await user_repo.get_by_id(payload["sub"])
    if user is None or not user.role.is_active:
        raise UnauthorizedError("User or role not found")
    return user                             # user.role.permissions is loaded
```

### 5 — `require_permission` Dependency Enforces Access

Define a reusable dependency factory. Route handlers declare what they need; the dependency enforces it.

**`src/infrastructure/services/auth_dependency.py`**
```python
from src.utils.exc import ForbiddenError

def require_permission(permission: str):
    def _check(current_user: User = Depends(get_current_user)) -> User:
        if permission not in (current_user.role.permissions or []):
            raise ForbiddenError(
                f"Role '{current_user.role.slug}' lacks permission '{permission}'"
            )
        return current_user
    return _check
```

Route handlers are thin — they declare the required permission and pass the user to the use case:

**`src/presentation/routes/article.py`**
```python
from src.config.constants import C

@router.delete("/articles/{article_id}")
async def delete_article(
    article_id: int,
    current_user: User = Depends(require_permission(C.PERM_ARTICLES_DELETE)),
    use_case: DeleteArticleUseCase = Depends(get_delete_article_use_case),
):
    return await use_case.execute(article_id, current_user)
```

### 6 — Use Cases Re-Enforce for Business Logic

The route-level dependency is the first gate. Use cases add a second check when the permission is tied to a business rule (e.g., a user can only delete their own articles unless they have the delete-any permission):

**`src/application/use_cases/article/delete.py`**
```python
from src.config.constants import C
from src.utils.exc import ForbiddenError, NotFoundError

class DeleteArticleUseCase:
    async def execute(self, article_id: int, current_user: User) -> None:
        article = await self._repo.get_by_id(article_id)
        if article is None:
            raise NotFoundError("Article not found")

        owns = article.author_id == current_user.id
        can_delete_any = C.PERM_ARTICLES_DELETE in current_user.role.permissions
        if not owns and not can_delete_any:
            raise ForbiddenError("Cannot delete another user's article")

        await self._repo.delete(article_id)
```

### 7 — Frontend Hides UI; Never Enforces Security

The frontend reads the role slug from the JWT or a `/me` endpoint and uses it to show or hide UI elements. This is for **user experience only** — it is not a security gate.

```tsx
// ✅ correct use — hide the button for non-editors (UX only)
{user.role === "admin" || user.role === "editor" ? (
  <DeleteButton articleId={article.id} />
) : null}

// The API will reject the request if the server-side check fails.
// The frontend check is cosmetic — remove it and security is unchanged.
```

Never make security decisions on the frontend. The server enforces; the frontend reflects.

## Role Management UI

Roles follow the reference-data pattern from `backend/25-reference-data`. The admin UI must allow:

- Creating new roles with a name, slug, and permission selection (multi-select from the `C.PERM_*` list)
- Editing permissions on existing roles (takes effect on next request for all users with that role)
- Archiving roles (`is_active = false`) — cannot be deleted if users hold that role
- Assigning roles to users on the user management page

No permission change ever requires a code edit or a redeploy.

## Decision Guide

| You want to… | Correct approach |
|---|---|
| Restrict a route to one or more roles | `Depends(require_permission(C.PERM_X))` |
| Add a new role | Insert a row via the admin UI — no code change |
| Add a new permission | Add a `C.PERM_*` constant, add it to the relevant seed roles in a migration, expose it in the role-edit UI |
| Check a permission in a use case | `if C.PERM_X not in current_user.role.permissions: raise ForbiddenError(...)` |
| Hide a UI element from non-admins | Read role from JWT/`/me`; hide the element — not a security gate |
| Revoke a permission immediately | Edit the role via admin UI — takes effect on next request |

## Quick Checklist

- [ ] No role or permission string is read from an env var
- [ ] No magic role strings (`"admin"`, `"superuser"`) appear outside `C.PERM_*` constants and seed migrations
- [ ] No `is_admin` boolean on User — roles are a separate FK relationship
- [ ] `Role` is a DB table with `permissions` (JSON array) and `is_active`
- [ ] JWT contains `role` slug only — permissions are fetched from DB on every request
- [ ] Every protected route uses `Depends(require_permission(C.PERM_X))`
- [ ] Use cases re-check permissions when the rule involves ownership or business context
- [ ] Frontend hides elements based on role but makes no security decisions
- [ ] An admin UI exists to create roles, edit permissions, and assign roles to users
- [ ] A seed migration populates at least `admin`, `editor`, and `viewer` roles

---
model: opus
effort: high
---

# RBAC Permissions — Roles, Permissions, and Assignments All in DB

Use when implementing any access control — admin-only features, role-based visibility, or per-resource permissions. Defines the correct RBAC pattern: roles, permissions, and their assignments all live in the database and are manageable at runtime through an admin UI. No permission string, no role definition, and no role-permission assignment ever belongs in source code or env vars. AI agents and vibecoding tools almost always get this wrong.

## The Anti-Patterns (What AI Always Generates)

```python
# ❌ WRONG — permissions read from env var
ALLOWED_GROUPS = os.environ.get("ALLOWED_GROUPS", "admin,superuser").split(",")

@router.get("/admin/data")
def get_data(user: User = Depends(get_current_user)):
    if user.role not in ALLOWED_GROUPS:
        raise HTTPException(403)
```

Adding or renaming a role now requires a code change and a redeploy.

```python
# ❌ WRONG — permission strings as code constants
class C:
    PERM_ARTICLES_READ  = "articles:read"
    PERM_ARTICLES_WRITE = "articles:write"
```

Constants are still hardcoded strings. A new permission requires a code change. Admins cannot define new permissions at runtime.

```python
# ❌ WRONG — magic role strings in route handlers
@router.delete("/articles/{id}")
def delete_article(user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(403)
```

```python
# ❌ WRONG — single boolean that doesn't scale
class User(Base, IdMixin):
    is_admin: Mapped[bool] = mapped_column(default=False)
```

```tsx
// ❌ WRONG — permission check only in the frontend
{user.role === "admin" && <DeleteButton />}
// The API has no server-side check — any REST client bypasses this
```

## The Correct Pattern

### 1 — Three Tables: Permission, Role, and RolePermission

Permissions and roles are both first-class entities. Their relationship is a join table.

**`src/domain/entities/permission.py`**
```python
import sqlalchemy as sq
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.db.base import Base, IdMixin

class Permission(Base, IdMixin):
    __tablename__ = "permissions"

    slug: Mapped[str] = mapped_column(sq.String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(sq.String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(sq.Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(sq.Boolean, default=True, nullable=False)
```

**`src/domain/entities/role.py`**
```python
import sqlalchemy as sq
from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.infrastructure.db.base import Base, IdMixin
from src.domain.entities.permission import Permission

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

class Role(Base, IdMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(sq.String(255), nullable=False)
    slug: Mapped[str] = mapped_column(sq.String(255), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(sq.Boolean, default=True, nullable=False)
    permissions: Mapped[list[Permission]] = relationship(
        Permission, secondary=role_permissions, lazy="joined"
    )
```

**`src/domain/entities/user.py`**
```python
class User(Base, IdMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(sq.String(255), unique=True, nullable=False)
    role_id: Mapped[int] = mapped_column(sq.ForeignKey("roles.id"), nullable=False)
    role: Mapped["Role"] = relationship("Role", lazy="joined")
```

### 2 — Seed Both Permissions and Role Assignments via Migration

Initial permissions and role-permission assignments are seeded data, not constants. Admins extend them at runtime through the UI without any code change.

**`alembic/versions/xxxx_seed_permissions_and_roles.py`**
```python
import sqlalchemy as sa
from alembic import op

def upgrade() -> None:
    # Insert without explicit IDs so the autoincrement sequence stays in sync.
    # role_permissions are wired by slug-based subquery, not hardcoded integers.
    conn = op.get_bind()

    conn.execute(
        sa.text("""
            INSERT INTO permissions (slug, name, description, is_active) VALUES
            ('articles:read',   'Read articles',   NULL, TRUE),
            ('articles:write',  'Write articles',  NULL, TRUE),
            ('articles:delete', 'Delete articles', NULL, TRUE),
            ('users:read',      'Read users',      NULL, TRUE),
            ('users:manage',    'Manage users',    NULL, TRUE),
            ('settings:read',   'Read settings',   NULL, TRUE),
            ('settings:write',  'Write settings',  NULL, TRUE),
            ('roles:manage',    'Manage roles',    NULL, TRUE)
        """)
    )

    conn.execute(
        sa.text("""
            INSERT INTO roles (name, slug, is_active) VALUES
            ('Admin',  'admin',  TRUE),
            ('Editor', 'editor', TRUE),
            ('Viewer', 'viewer', TRUE)
        """)
    )

    # Join by slug so no hardcoded IDs are needed and sequences stay correct.
    conn.execute(
        sa.text("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id FROM roles r, permissions p
            WHERE
                -- admin gets everything
                (r.slug = 'admin')
                OR
                -- editor: read + write articles
                (r.slug = 'editor' AND p.slug IN ('articles:read', 'articles:write'))
                OR
                -- viewer: read articles only
                (r.slug = 'viewer' AND p.slug = 'articles:read')
        """)
    )
```

### 3 — JWT Contains Role Slug Only

The token carries identifiers, not permissions. Permissions are fetched fresh from the database on every request so changes via the admin UI take effect immediately — not after token expiry.

**`src/infrastructure/services/token_service.py`**
```python
def create_access_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role.slug,
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, get_config().JWT_SECRET, algorithm="HS256")
```

The `get_current_user` dependency resolves the full user — with role and its permissions — from the DB on every authenticated request. It follows the same `Annotated[AsyncSession, Depends(get_session)]` pattern used everywhere in the presentation layer (see `backend/05-presentation-layer`):

**`src/infrastructure/services/auth_dependency.py`**
```python
from typing import Annotated
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.db.engine import get_session
from src.infrastructure.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    payload = decode_token(token)
    user = await UserRepository(session).get_by_id(payload["sub"])
    if user is None or not user.role.is_active:
        raise UnauthorizedError("User or role not found")
    return user   # user.role.permissions is loaded via joined relationship
```

### 4 — `require_permission` Checks Against DB-Loaded Slugs

The permission slug used in a route handler is a string that references a record in the `permissions` table — not a local constant. The enforcement reads the live set of permission slugs on the user's role as loaded from the DB.

**`src/infrastructure/services/auth_dependency.py`**
```python
def require_permission(permission_slug: str):
    async def _check(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        has = any(
            p.slug == permission_slug and p.is_active
            for p in current_user.role.permissions
        )
        if not has:
            raise ForbiddenError(
                f"Role '{current_user.role.slug}' lacks permission '{permission_slug}'"
            )
        return current_user
    return _check
```

Route handlers pass the slug string directly. The string must match a `permissions.slug` value in the DB — it is not a constant, it is a reference. The session is injected via `Depends(get_session)` and passed directly to the repository constructor, exactly as shown in `backend/05-presentation-layer`:

**`src/presentation/routes/article.py`**
```python
from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.db.engine import get_session
from src.infrastructure.repositories.article_repository import ArticleRepository

router = APIRouter(prefix="/articles", tags=["Articles"])

@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article(
    article_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_permission("articles:delete"))],
) -> None:
    await DeleteArticleUseCase(ArticleRepository(session)).execute(article_id, current_user)
```

When a new permission is needed for a new endpoint, the workflow is:
1. Insert the new `Permission` row via migration (or admin UI if it is a fully runtime-defined permission)
2. Assign it to the relevant roles via the admin UI
3. Reference its slug in the new route handler's `require_permission()` call

### 5 — Use Cases Re-Enforce for Business Context

The route dependency is the first gate. Use cases add a second check when ownership or business rules are involved:

**`src/application/use_cases/article/delete.py`**
```python
from src.infrastructure.repositories.contract import ArticleRepositoryInterface

class DeleteArticleUseCase:
    def __init__(self, article_repository: ArticleRepositoryInterface) -> None:
        self._repo = article_repository   # constructor injection — depends on interface

    async def execute(self, article_id: int, current_user: User) -> None:
        article = await self._repo.get_by_id(article_id)
        if article is None:
            raise NotFoundError("Article not found")

        owns = article.author_id == current_user.id
        can_delete_any = any(
            p.slug == "articles:delete" and p.is_active
            for p in current_user.role.permissions
        )
        if not owns and not can_delete_any:
            raise ForbiddenError("Cannot delete another user's article")

        await self._repo.delete(article_id)
```

The frontend permission pattern (route guards, permission hooks, UI visibility) is covered in `frontend/19-rbac-permissions`.

### 6 — Admin UI Manages Everything at Runtime

The admin UI must provide full control over the RBAC system without any code changes or redeployments:

- **Permissions page** — list all permissions, add new ones (name + slug + description), archive unused ones
- **Roles page** — list all roles, create new roles, edit role name, assign/remove permissions via multi-select, archive roles
- **Users page** — assign or change a user's role

When an admin adds a new permission and assigns it to a role, all users with that role gain the permission on their next request. No redeploy. No code change.

## What Requires Code vs What Doesn't

| Action | Code change needed? |
|---|---|
| Add a new role | No — admin UI |
| Add a new permission type | No — admin UI (or migration for initial seed) |
| Assign a permission to a role | No — admin UI |
| Revoke a permission from a role | No — admin UI, takes effect immediately |
| Change a user's role | No — admin UI |
| Protect a new API endpoint | Yes — `require_permission("slug")` on the new route handler |

Protecting a new endpoint always requires code because the endpoint itself is code. Everything else is runtime.

## Quick Checklist

- [ ] No role string, permission string, or group list is read from an env var
- [ ] No permission strings are defined as code constants — they are rows in the `permissions` table
- [ ] `Permission` and `Role` are separate DB tables; assignments live in `role_permissions`
- [ ] No `is_admin` boolean on `User` — role is a FK relationship
- [ ] JWT contains `role` slug only — permissions are fetched fresh from DB on every request
- [ ] Every protected route uses `Depends(require_permission("slug"))`
- [ ] Use cases re-check permissions when ownership or business context is involved
- [ ] Admin UI exists to manage permissions, roles, assignments, and user role assignment at runtime
- [ ] A seed migration populates initial permissions and role-permission assignments
- [ ] See `frontend/19-rbac-permissions` for frontend route guards and UI visibility patterns

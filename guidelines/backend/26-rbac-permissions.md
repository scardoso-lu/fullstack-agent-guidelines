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
    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(permissions_table, [
        {"id": 1,  "slug": "articles:read",   "name": "Read articles",    "description": None, "is_active": True},
        {"id": 2,  "slug": "articles:write",  "name": "Write articles",   "description": None, "is_active": True},
        {"id": 3,  "slug": "articles:delete", "name": "Delete articles",  "description": None, "is_active": True},
        {"id": 4,  "slug": "users:read",      "name": "Read users",       "description": None, "is_active": True},
        {"id": 5,  "slug": "users:manage",    "name": "Manage users",     "description": None, "is_active": True},
        {"id": 6,  "slug": "settings:read",   "name": "Read settings",    "description": None, "is_active": True},
        {"id": 7,  "slug": "settings:write",  "name": "Write settings",   "description": None, "is_active": True},
        {"id": 8,  "slug": "roles:manage",    "name": "Manage roles",     "description": None, "is_active": True},
    ])

    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(roles_table, [
        {"id": 1, "name": "Admin",  "slug": "admin",  "is_active": True},
        {"id": 2, "name": "Editor", "slug": "editor", "is_active": True},
        {"id": 3, "name": "Viewer", "slug": "viewer", "is_active": True},
    ])

    rp_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )
    op.bulk_insert(rp_table, [
        # admin gets everything
        {"role_id": 1, "permission_id": 1},
        {"role_id": 1, "permission_id": 2},
        {"role_id": 1, "permission_id": 3},
        {"role_id": 1, "permission_id": 4},
        {"role_id": 1, "permission_id": 5},
        {"role_id": 1, "permission_id": 6},
        {"role_id": 1, "permission_id": 7},
        {"role_id": 1, "permission_id": 8},
        # editor: read + write articles
        {"role_id": 2, "permission_id": 1},
        {"role_id": 2, "permission_id": 2},
        # viewer: read articles only
        {"role_id": 3, "permission_id": 1},
    ])
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

The `get_current_user` dependency resolves the full user — with role and its permissions — from the DB on every authenticated request:

**`src/infrastructure/services/auth_dependency.py`**
```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_repo: UserRepositoryInterface = Depends(get_user_repository),
) -> User:
    payload = decode_token(token)
    user = await user_repo.get_by_id(payload["sub"])
    if user is None or not user.role.is_active:
        raise UnauthorizedError("User or role not found")
    return user   # user.role.permissions is loaded via joined relationship
```

### 4 — `require_permission` Checks Against DB-Loaded Slugs

The permission slug used in a route handler is a string that references a record in the `permissions` table — not a local constant. The enforcement reads the live set of permission slugs on the user's role as loaded from the DB.

**`src/infrastructure/services/auth_dependency.py`**
```python
def require_permission(permission_slug: str):
    def _check(current_user: User = Depends(get_current_user)) -> User:
        has = any(p.slug == permission_slug for p in current_user.role.permissions)
        if not has:
            raise ForbiddenError(
                f"Role '{current_user.role.slug}' lacks permission '{permission_slug}'"
            )
        return current_user
    return _check
```

Route handlers pass the slug string directly. The string must match a `permissions.slug` value in the DB — it is not a constant, it is a reference:

**`src/presentation/routes/article.py`**
```python
@router.delete("/articles/{article_id}")
async def delete_article(
    article_id: int,
    current_user: User = Depends(require_permission("articles:delete")),
    use_case: DeleteArticleUseCase = Depends(get_delete_article_use_case),
):
    return await use_case.execute(article_id, current_user)
```

When a new permission is needed for a new endpoint, the workflow is:
1. Insert the new `Permission` row via migration (or admin UI if it is a fully runtime-defined permission)
2. Assign it to the relevant roles via the admin UI
3. Reference its slug in the new route handler's `require_permission()` call

### 5 — Use Cases Re-Enforce for Business Context

The route dependency is the first gate. Use cases add a second check when ownership or business rules are involved:

**`src/application/use_cases/article/delete.py`**
```python
class DeleteArticleUseCase:
    async def execute(self, article_id: int, current_user: User) -> None:
        article = await self._repo.get_by_id(article_id)
        if article is None:
            raise NotFoundError("Article not found")

        owns = article.author_id == current_user.id
        can_delete_any = any(
            p.slug == "articles:delete" for p in current_user.role.permissions
        )
        if not owns and not can_delete_any:
            raise ForbiddenError("Cannot delete another user's article")

        await self._repo.delete(article_id)
```

### 6 — Frontend Hides UI; Never Enforces Security

The frontend reads the role slug from `/me` and uses it to show or hide UI elements. This is user experience, not access control.

```tsx
// ✅ hide for UX — security is enforced server-side regardless
{user.role === "admin" || user.role === "editor" ? (
  <DeleteButton articleId={article.id} />
) : null}
```

### 7 — Admin UI Manages Everything at Runtime

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
- [ ] Frontend hides elements based on role but makes no security decisions
- [ ] Admin UI exists to manage permissions, roles, assignments, and user role assignment at runtime
- [ ] A seed migration populates initial permissions and role-permission assignments

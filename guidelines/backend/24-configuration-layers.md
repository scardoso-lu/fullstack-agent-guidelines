---
model: opus
effort: high
---

# Configuration Layers — Env, Runtime DB, Settings UI, and Reference Data Tables

Use when deciding where any value in the system lives — secrets, service URLs, user preferences, feature flags, or product lists like categories, statuses, and types. Defines the three-layer rule for config and the reference-data rule for product lists. Hardcoded values anywhere in the codebase are always wrong. AI agents and vibecoding tools miss both rules almost every time.

Every value in the system belongs to exactly one layer. Choosing the wrong layer causes operational pain (a redeploy to rename a category) or security problems (secrets in the DB). The correct default is always the database — never source code.

## The Core Principle

> If a user could ever want to change it, add to it, or rename it — it belongs in the database, not in the code.

This applies to two distinct categories:

1. **Configuration values** — limits, flags, preferences that admins control (max upload size, default language, maintenance mode)
2. **Product reference data** — lookup lists the domain uses (categories, statuses, document types, payment methods, tags)

AI-generated code almost always hardcodes both. The guidelines below establish the correct pattern for each.

## The Three-Layer Rule (Config Values)

```
Layer 1 — Startup (env vars / .env)
  ↳ Set at container launch. Ops controls. Changing requires a redeploy.
  ↳ Examples: DATABASE_URL, JWT_SECRET, SMTP_HOST, EXTERNAL_API_KEY

Layer 2 — Runtime (database table)
  ↳ Changed at runtime without redeploy. Users or admins control via the UI.
  ↳ Examples: max_upload_mb, default_language, support_email, feature flags

Layer 3 — Settings UI (frontend admin panel)
  ↳ The surface through which admins write Layer 2 values.
  ↳ Always required when Layer 2 exists.
```

**The absolute rule:** no value from any layer may be hardcoded in source code.

## Layer 1 — Startup Config

Startup config is read once when the container starts. Use `pydantic-settings` (`BaseSettings`). Every field must have no default — a missing env var should crash loudly at startup, not silently use a fallback that corrupts production.

**`src/config/settings/__init__.py`**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── infrastructure ────────────────────────────────────────────────────
    DATABASE_URL: str           # no default → crash if missing
    JWT_SECRET: str             # no default → crash if missing

    # ── external services ─────────────────────────────────────────────────
    SMTP_HOST: str
    SMTP_PORT: int
    SENDGRID_API_KEY: str

    # ── optional with sane defaults ───────────────────────────────────────
    LOG_LEVEL: str = "INFO"     # safe to default; not a secret
    ENVIRONMENT: str = "development"


_config: Settings | None = None

def get_config() -> Settings:
    global _config
    if _config is None:
        _config = Settings()
    return _config
```

Commit `.env.example` with placeholder values; gitignore `.env`:

**`.env.example`**
```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost/appdb
JWT_SECRET=replace-with-64-char-random-string
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SENDGRID_API_KEY=SG.replace-me
```

**`.env`** — never committed, listed in `.gitignore`.

## Layer 2 — Runtime Config (Database)

Runtime config is everything a user or admin can change without a redeploy. It lives in an `app_config` table as key-value pairs with typed coercion at the use-case boundary.

### Domain Entity

**`src/domain/entities/app_config.py`**
```python
import sqlalchemy as sq
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.db.base import Base

class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(sq.String(255), primary_key=True)
    value: Mapped[str] = mapped_column(sq.Text, nullable=False)
    description: Mapped[str | None] = mapped_column(sq.Text, nullable=True)
    updated_at: Mapped[sq.DateTime] = mapped_column(
        sq.DateTime(timezone=True),
        server_default=sq.func.now(),
        onupdate=sq.func.now(),
    )
```

### Known Keys Constant

Define all valid keys as constants so callers never use magic strings:

**`src/config/constants.py`**
```python
class C:
    # Layer 2 config keys — stored in app_config table
    MAX_UPLOAD_MB: str = "max_upload_mb"
    DEFAULT_LANGUAGE: str = "default_language"
    SUPPORT_EMAIL: str = "support_email"
    MAINTENANCE_MODE: str = "maintenance_mode"
```

### Repository Interface

**`src/infrastructure/repositories/contract.py`** (add to existing file)
```python
from abc import ABC, abstractmethod
from src.domain.entities.app_config import AppConfig

class AppConfigRepositoryInterface(ABC):
    @abstractmethod
    async def get(self, key: str) -> AppConfig | None: ...

    @abstractmethod
    async def get_all(self) -> list[AppConfig]: ...

    @abstractmethod
    async def upsert(self, key: str, value: str) -> AppConfig: ...
```

### Use Cases

**`src/application/use_cases/config/get.py`**
```python
from src.infrastructure.repositories.contract import AppConfigRepositoryInterface
from src.utils.exc import NotFoundError

class GetConfigUseCase:
    def __init__(self, repo: AppConfigRepositoryInterface) -> None:
        self._repo = repo

    async def execute(self, key: str) -> str:
        entry = await self._repo.get(key)
        if entry is None:
            raise NotFoundError(f"Config key '{key}' not set")
        return entry.value
```

**`src/application/use_cases/config/update.py`**
```python
from src.application.dto.config_dto import UpdateConfigDto, ConfigDto
from src.infrastructure.repositories.contract import AppConfigRepositoryInterface

class UpdateConfigUseCase:
    def __init__(self, repo: AppConfigRepositoryInterface) -> None:
        self._repo = repo

    async def execute(self, dto: UpdateConfigDto) -> ConfigDto:
        entry = await self._repo.upsert(dto.key, dto.value)
        return ConfigDto.model_validate(entry)
```

### DTO

**`src/application/dto/config_dto.py`**
```python
from pydantic import BaseModel, ConfigDict

class UpdateConfigDto(BaseModel):
    key: str
    value: str

class ConfigDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    value: str
    description: str | None
```

## Layer 3 — Settings UI

Every runtime config value exposed via Layer 2 **must** have a corresponding settings page in the frontend. Without the UI, admins must run raw SQL — that is not acceptable.

The settings page is an admin-only route. It fetches all `AppConfig` rows and renders a form. Each field saves on submit via a Server Action.

**`app/admin/settings/page.tsx`**
```tsx
import { getAppConfig } from "@/lib/config";
import { SettingsForm } from "./settings-form";

export default async function SettingsPage() {
  const config = await getAppConfig();   // server-side fetch
  return (
    <main>
      <h1>Runtime Settings</h1>
      <SettingsForm config={config} />
    </main>
  );
}
```

**`app/admin/settings/actions.ts`**
```ts
"use server";

import { revalidatePath } from "next/cache";
import { updateConfig } from "@/lib/api/config";
import { z } from "zod";

const schema = z.object({
  key: z.string().min(1),
  value: z.string(),
});

export async function updateConfigAction(formData: FormData) {
  const parsed = schema.safeParse({
    key: formData.get("key"),
    value: formData.get("value"),
  });
  if (!parsed.success) return { error: parsed.error.flatten() };

  await updateConfig(parsed.data);
  revalidatePath("/admin/settings");
}
```

Protect the route with middleware — only `admin` role can reach `/admin/**`.

## Product Reference Data — Tables, Not Code

The same principle that forbids hardcoded config values forbids hardcoded product lists. Any list that a user could ever want to extend, rename, or reorder belongs in a database table with full CRUD.

This is the single most common mistake made by AI agents and vibe-coded systems. The temptation is to model a "fixed list" as a Python enum, a `Literal` type, or a constant because it "seems stable for now." It never stays stable. The moment a user asks "can we add a new category?" or "rename this status?", a code change and a redeploy are required — which is unacceptable for a product feature.

### The Anti-Pattern (What AI Generates)

```python
# ❌ WRONG — Python enum in domain code
from enum import Enum

class Category(str, Enum):
    TECHNOLOGY = "technology"
    DESIGN = "design"
    MARKETING = "marketing"

# ❌ WRONG — Literal type in DTO
class CreateArticleDto(BaseModel):
    category: Literal["technology", "design", "marketing"]

# ❌ WRONG — hardcoded list in a route
@router.get("/categories")
def list_categories():
    return ["technology", "design", "marketing"]
```

Every one of these breaks the moment a user says "add Finance" or "rename Design to UX". A code change and a redeploy are required.

### The Correct Pattern

Every lookup list is its own table. The standard shape:

**`src/domain/entities/category.py`**
```python
import sqlalchemy as sq
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.db.base import Base, IdMixin

class Category(Base, IdMixin):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(sq.String(255), nullable=False)
    slug: Mapped[str] = mapped_column(sq.String(255), unique=True, nullable=False)
    order: Mapped[int] = mapped_column(sq.Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(sq.Boolean, default=True, nullable=False)
```

The entity that uses a category holds a **foreign key**, not an enum column:

**`src/domain/entities/article.py`**
```python
from sqlalchemy.orm import relationship

class Article(Base, IdMixin):
    __tablename__ = "articles"

    title: Mapped[str] = mapped_column(sq.String(255), nullable=False)
    category_id: Mapped[int] = mapped_column(
        sq.ForeignKey("categories.id"), nullable=False
    )
    category: Mapped["Category"] = relationship("Category", lazy="joined")
```

### What Every Reference-Data Table Requires

A table alone is not enough. Each lookup entity must have:

1. **Full CRUD use cases** — `ListCategoriesUseCase`, `CreateCategoryUseCase`, `UpdateCategoryUseCase`, `ArchiveCategoryUseCase` (soft-delete via `is_active`)
2. **Admin API routes** — `GET /admin/categories`, `POST /admin/categories`, `PATCH /admin/categories/{id}`, `DELETE /admin/categories/{id}`
3. **Public read route** — `GET /categories` (for dropdowns, no auth required)
4. **Frontend admin UI** — a sortable table with inline edit and add/archive controls
5. **Seed data migration** — initial rows so the system is usable on first deploy

### Seed Data Pattern

Pre-populate initial rows in a migration so the system is immediately usable without manual data entry:

**`alembic/versions/xxxx_seed_categories.py`**
```python
import sqlalchemy as sa
from alembic import op

def upgrade() -> None:
    op.bulk_insert(
        sa.table(
            "categories",
            sa.column("name", sa.String),
            sa.column("slug", sa.String),
            sa.column("order", sa.Integer),
            sa.column("is_active", sa.Boolean),
        ),
        [
            {"name": "Technology", "slug": "technology", "order": 1, "is_active": True},
            {"name": "Design",     "slug": "design",     "order": 2, "is_active": True},
            {"name": "Marketing",  "slug": "marketing",  "order": 3, "is_active": True},
        ],
    )

def downgrade() -> None:
    op.execute("DELETE FROM categories WHERE slug IN ('technology', 'design', 'marketing')")
```

Seed data is the starting point, not a permanent list. Users extend it through the UI.

### Frontend: Dropdown Always Fetches from the API

The frontend never has a hardcoded options array. Dropdowns and selects always call the public read route:

**`components/category-select.tsx`**
```tsx
// ❌ WRONG — hardcoded options
const options = ["Technology", "Design", "Marketing"];

// ✅ CORRECT — fetched from API; stays in sync with what's in the DB
async function CategorySelect() {
  const categories = await fetch("/api/categories").then(r => r.json());
  return (
    <select name="category_id">
      {categories.map((c: { id: number; name: string }) => (
        <option key={c.id} value={c.id}>{c.name}</option>
      ))}
    </select>
  );
}
```

### Common Reference Data to Model as Tables

| Looks static but isn't | Entity | Extra columns |
|---|---|---|
| Content / product categories | `Category` | slug, order, is_active |
| Record statuses (draft, published…) | `Status` | color, is_terminal |
| Priority levels (low, medium, high) | `Priority` | level (int), color |
| Document types (invoice, contract…) | `DocumentType` | template_id |
| Payment methods | `PaymentMethod` | provider, is_active |
| User roles | `Role` | permissions (JSON) |
| Tags / labels | `Tag` | color, is_active |
| Countries / currencies | `Country`, `Currency` | code, locale |
| Notification types | `NotificationType` | template, channel |

## Decision Guide

| The value is… | Where it belongs |
|---|---|
| A secret, token, or password | Layer 1 — `.env` / env var, no default |
| A service URL, port, or hostname | Layer 1 — `.env` / env var, no default |
| A build/deploy-time flag | Layer 1 — `.env` / env var |
| A user-adjustable limit or preference | Layer 2 — `app_config` table row |
| A feature flag toggleable without redeploy | Layer 2 — `app_config` table row |
| A list users can add to, rename, or reorder | Reference-data table + admin UI |
| Per-user preference (theme, timezone) | User profile table |
| Business data (orders, users, posts) | Regular domain entity table |

If you're unsure: ask "can a user ever need to change this without a code deploy?" — if yes, it's Layer 2 or reference data.

## Anti-Patterns

```python
# ❌ WRONG — hardcoded config value in source code
MAX_FILE_SIZE = 10 * 1024 * 1024

# ❌ WRONG — runtime preference in env var (requires redeploy to change)
class Settings(BaseSettings):
    DEFAULT_LANGUAGE: str = "en"

# ❌ WRONG — secret in the database
# Layer 2 is for user-visible settings, not for JWT_SECRET

# ✅ CORRECT — limit read from Layer 2 at request time
max_mb = int(await get_config.execute(C.MAX_UPLOAD_MB))
```

```python
# ❌ WRONG — product list hardcoded in code (AI generates this every time)
STATUSES = ["draft", "under_review", "published", "archived"]

class ArticleStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"

# ✅ CORRECT — status is a FK to a statuses table managed via admin UI
class Article(Base, IdMixin):
    status_id: Mapped[int] = mapped_column(ForeignKey("statuses.id"))
```

```python
# ❌ WRONG — Layer 2 value exists but no UI; ops must use raw SQL
UPDATE app_config SET value = '20' WHERE key = 'max_upload_mb';

# ❌ WRONG — reference data table exists but no admin UI; ops inserts manually
INSERT INTO categories (name, slug) VALUES ('Finance', 'finance');

# ✅ CORRECT — every DB-managed value has a settings or admin page
```

## Quick Checklist

- [ ] No literal string, number, or list that belongs to config or reference data appears in `src/`
- [ ] Every secret and service URL is in `BaseSettings` with no default
- [ ] `.env` is gitignored; `.env.example` is committed with placeholders
- [ ] Every user-adjustable config value is a row in `app_config`, not an env var
- [ ] `C.*` constants cover all `app_config` keys — no magic strings at call sites
- [ ] Every lookup list (categories, statuses, types…) is its own DB table with `is_active` soft-delete
- [ ] Every reference-data entity has full CRUD use cases, admin routes, and a frontend admin UI
- [ ] Every reference-data table has a seed migration with sensible initial rows
- [ ] Frontend dropdowns call the API — no hardcoded options arrays anywhere
- [ ] An admin settings page covers every Layer 2 key
- [ ] The settings and admin routes are protected by the `admin` role check

---
model: opus
effort: high
---

# Configuration Layers — Startup Env, Runtime DB, and Settings UI

Use when deciding where a configuration value lives — secrets, service URLs, user preferences, feature flags, or operational limits. Defines the three-layer rule: startup config belongs in .env / environment variables, runtime config that users can change belongs in the database, and every runtime config surface needs a frontend settings page. Hardcoded values anywhere in the codebase are always wrong.

Every value in the system belongs to exactly one configuration layer. Choosing the wrong layer causes operational pain (ops must redeploy to change a user preference) or security problems (secrets in the DB, user data in the source tree).

## The Three-Layer Rule

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
  const config = await getAppConfig();
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

## Decision Guide

| The value is… | Layer | Storage |
|---|---|---|
| A secret (key, password, token) | 1 | `.env` / env var, no default |
| A service URL or port | 1 | `.env` / env var, no default |
| A build-time or deploy-time flag | 1 | `.env` / env var |
| A user-adjustable limit (upload size) | 2 | `app_config` table |
| A user-adjustable preference (language) | 2 | `app_config` table |
| A feature flag toggleable without redeploy | 2 | `app_config` table |
| Per-user preference (dark mode, timezone) | — | User profile table |
| A list users can extend or rename | — | See `backend/25-reference-data` |

## Anti-Patterns

```python
# ❌ WRONG — hardcoded value in source code
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
# ❌ WRONG — Layer 2 value exists but no UI; ops must run raw SQL
UPDATE app_config SET value = '20' WHERE key = 'max_upload_mb';

# ✅ CORRECT — admin settings page lets any authorised user change it
```

## Quick Checklist

- [ ] No literal string or number that belongs to config appears anywhere in `src/`
- [ ] Every secret and service URL is in `BaseSettings` with no default
- [ ] `.env` is gitignored; `.env.example` is committed with placeholders
- [ ] Every user-adjustable value is a row in `app_config`, not an env var
- [ ] `C.*` constants cover all known `app_config` keys — no magic strings at call sites
- [ ] An admin settings page exists and covers every Layer 2 key
- [ ] The settings route is protected by the `admin` role check

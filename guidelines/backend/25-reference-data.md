---
model: opus
effort: high
---

# Reference Data — Lookup Tables, Not Hardcoded Lists

Use when building any feature that involves a list of options — categories, statuses, document types, payment methods, tags, priority levels, roles, or any other domain list. The rule: if a user could ever want to add to it, rename an item, or reorder it, it belongs in a database table with full CRUD and a frontend admin UI. Hardcoded enums, Literal types, and constant lists are always wrong for these cases.

This is the single most common mistake in AI-generated and vibe-coded systems. The list "seems stable for now" so it gets hardcoded. The moment a user asks "can we add Finance?" or "rename Design to UX?", a code change and a redeploy are required — which is unacceptable for a product feature.

## The Anti-Pattern (What AI Always Generates)

```python
# ❌ WRONG — Python enum in domain code
from enum import Enum

class Category(str, Enum):
    TECHNOLOGY = "technology"
    DESIGN = "design"
    MARKETING = "marketing"
```

```python
# ❌ WRONG — Literal type in a DTO
class CreateArticleDto(BaseModel):
    category: Literal["technology", "design", "marketing"]
```

```python
# ❌ WRONG — hardcoded list returned from a route
@router.get("/categories")
def list_categories():
    return ["technology", "design", "marketing"]
```

All three break identically: adding or renaming an option requires a code edit and a redeploy.

## The Standard Lookup Table Shape

Every reference-data entity follows the same structure:

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

| Column | Purpose |
|---|---|
| `name` | Display label shown in the UI |
| `slug` | Stable identifier used in code, URLs, and API responses — never changes even if `name` does |
| `order` | Controls display sort order without re-inserting rows |
| `is_active` | Soft-delete — hides without destroying FK relationships or history |

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

## What Every Reference-Data Entity Requires

A table alone is not enough. Each lookup entity must be fully wired end-to-end:

1. **Full CRUD use cases** — list (active only), get by id, create, update, soft-delete via `is_active`
2. **Admin API routes** — `GET /admin/categories`, `POST /admin/categories`, `PATCH /admin/categories/{id}`, `DELETE /admin/categories/{id}`
3. **Public read route** — `GET /categories` (for dropdowns; authenticated but not admin-only)
4. **Frontend admin UI** — sortable table with inline edit, add row, and archive controls
5. **Seed migration** — initial rows so the system is usable immediately on first deploy

Missing any of these makes the table operationally useless — admins would need raw SQL to manage it.

## Use Cases

**`src/application/use_cases/category/list.py`**
```python
from src.application.dto.category_dto import CategoryDto
from src.infrastructure.repositories.contract import CategoryRepositoryInterface

class ListCategoriesUseCase:
    def __init__(self, repo: CategoryRepositoryInterface) -> None:
        self._repo = repo

    async def execute(self, include_inactive: bool = False) -> list[CategoryDto]:
        items = await self._repo.get_all(include_inactive=include_inactive)
        return [CategoryDto.model_validate(c) for c in items]
```

**`src/application/use_cases/category/create.py`**
```python
from src.application.dto.category_dto import CreateCategoryDto, CategoryDto
from src.infrastructure.repositories.contract import CategoryRepositoryInterface
from src.utils.exc import ConflictError

class CreateCategoryUseCase:
    def __init__(self, repo: CategoryRepositoryInterface) -> None:
        self._repo = repo

    async def execute(self, dto: CreateCategoryDto) -> CategoryDto:
        if await self._repo.get_by_slug(dto.slug):
            raise ConflictError(f"Slug '{dto.slug}' already exists")
        category = await self._repo.create(dto.name, dto.slug, dto.order)
        return CategoryDto.model_validate(category)
```

## Seed Migration

Pre-populate initial rows so the system is usable immediately after deploy. Seed data is the starting point, not a permanent list — users extend it through the admin UI.

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
    op.execute(
        "DELETE FROM categories WHERE slug IN ('technology', 'design', 'marketing')"
    )
```

## Frontend: Dropdowns Always Fetch from the API

The frontend never has a hardcoded options array. Every dropdown or select that presents reference data calls the public read route at render time.

**`components/category-select.tsx`**
```tsx
// ❌ WRONG — hardcoded options in the component
const options = ["Technology", "Design", "Marketing"];

// ✅ CORRECT — fetched from API; always reflects what's in the database
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

Cache the response (Next.js `fetch` with `revalidate`) so the dropdown doesn't make a round-trip on every render, but ensure a revalidation happens when an admin updates the list.

## Common Reference Data to Model as Tables

| Domain concept | Entity name | Extra columns beyond the standard shape |
|---|---|---|
| Content / product categories | `Category` | — |
| Record statuses (draft, published…) | `Status` | `color`, `is_terminal` |
| Priority levels | `Priority` | `level` (int for ordering logic), `color` |
| Document types (invoice, contract…) | `DocumentType` | `template_id` |
| Payment methods | `PaymentMethod` | `provider`, `config` (JSON) |
| User roles | `Role` | `permissions` (JSON array) |
| Tags / labels | `Tag` | `color` |
| Notification types | `NotificationType` | `template`, `channel` |
| Countries / currencies | `Country`, `Currency` | `code`, `locale` |

## Quick Checklist

- [ ] No Python enum, `Literal` type, or constant list is used to represent a domain lookup
- [ ] Every lookup list is a DB table with `name`, `slug`, `order`, `is_active`
- [ ] Consuming entities hold a FK to the lookup table, not an enum column
- [ ] Full CRUD use cases exist (list active, get by id, create, update, archive)
- [ ] Admin API routes exist for full CRUD management
- [ ] A public read route exists for dropdowns (`GET /<entity>s`)
- [ ] A frontend admin UI exists — no raw SQL needed to add or rename an item
- [ ] A seed migration populates sensible initial rows
- [ ] Frontend dropdowns call the API — no hardcoded options arrays anywhere

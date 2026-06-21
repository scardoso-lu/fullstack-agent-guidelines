# API Pagination — Cursor, Offset, and Response Envelopes

Use when designing any list endpoint, when reviewing a route that returns a collection, or when an existing endpoint is paginating differently from the rest of the API. Defines the **default**: cursor-based pagination for everything user-facing, with a stable response envelope, capped `page_size`, and a documented sort/filter convention. Covers when offset pagination is acceptable (admin-only, small datasets), the bug patterns it produces on large data, and how to keep all list endpoints **shaped the same way** so clients aren't bespoke per endpoint.

A list endpoint without a pagination contract is a future production incident — the day the table has 50k rows, the response times out, the client OOMs, or both. Lock the contract on day one.

## The rule

> **Default to cursor-based pagination** for every list endpoint.
> **Every list endpoint returns the same envelope shape** (`items`, `next_cursor`, `prev_cursor`, `page_size`) so clients have one parser.
> **`page_size` is always capped server-side** (typical: `default=20`, `max=100`).
> **Sorts are explicit and small** — a documented enum of allowed sort keys, not "any column".
> **Filters use a documented query-param convention**, not `where=` strings.

Offset pagination is acceptable for admin tooling over small (< 10k row) datasets where the simpler UX is worth the cost. For anything user-facing or large, cursor.

## The response envelope (one shape for every list)

```python
# src/shared/dto/paginated.py
from typing import Generic, TypeVar
from pydantic import Field

from src.application.dto import BaseSchema

T = TypeVar("T")

class Page(BaseSchema, Generic[T]):
    items: list[T]
    next_cursor: str | None = Field(None, description="Pass as `cursor` to fetch the next page; null when no more.")
    prev_cursor: str | None = Field(None, description="Pass as `cursor` with `direction=prev` to fetch the previous page.")
    page_size: int
```

> **Relationship to `PagedItems[T]`.** `backend/04-infrastructure-layer` introduces a `PagedItems[T]` dataclass for **offset** pagination. `Page[T]` is the **cursor**-pagination envelope used at the API boundary — they are complementary, not duplicates. Use `Page[T]` as the default for any new list endpoint (see "Cursor pagination" below); keep `PagedItems[T]` only for the offset-pagination cases described in "Offset pagination — only when it's the right tool".

Why one shape:

- Every client (web, mobile, scripts) has one paginator helper.
- New endpoints are predictable — the contract is already known.
- A typed envelope lets you generate clients (OpenAPI) without bespoke handlers per endpoint.

A response **without** `next_cursor` ≠ "end of list" by accident — `next_cursor: null` is the explicit terminator. Clients should not infer.

## Cursor pagination — the default

A cursor is **an opaque string encoding the position to resume from**. It's opaque so the server can change the encoding without breaking clients.

Encode (server-side):

```python
# src/shared/pagination.py
import base64
import json
from datetime import datetime

def encode_cursor(created_at: datetime, id: int) -> str:
    raw = json.dumps({"c": created_at.isoformat(), "i": id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode()

def decode_cursor(cursor: str) -> tuple[datetime, int]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    data = json.loads(raw)
    return datetime.fromisoformat(data["c"]), data["i"]
```

Per `backend/04-infrastructure-layer`, the repository receives its `AsyncSession` in `__init__` and returns **entities**; the application layer maps to DTOs.

```python
# src/infrastructure/repositories/dataset_repository.py
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.dataset import Dataset
from src.infrastructure.repositories.contract import DatasetRepositoryInterface
from src.shared.pagination import Page, encode_cursor, decode_cursor


class DatasetRepository(DatasetRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_paginated(self, *, cursor: str | None, page_size: int) -> Page[Dataset]:
        stmt = (
            select(Dataset)
            .order_by(Dataset.created_at.desc(), Dataset.id.desc())
            .limit(page_size + 1)
        )
        if cursor is not None:
            ts, last_id = decode_cursor(cursor)
            stmt = stmt.where(tuple_(Dataset.created_at, Dataset.id) < tuple_(ts, last_id))

        rows = (await self.session.execute(stmt)).scalars().all()
        has_more = len(rows) > page_size
        items = rows[:page_size]
        next_cursor = (
            encode_cursor(items[-1].created_at, items[-1].id) if items and has_more else None
        )
        return Page[Dataset](
            items=items,                                # entities, not DTOs
            next_cursor=next_cursor,
            prev_cursor=None,                           # see "Backward / 'prev' pagination" below
            page_size=page_size,
        )
```

The use-case maps entities to DTOs at the application boundary (per `backend/03-application-layer` — repos return entities, use-cases return DTOs):

```python
# src/application/use_cases/dataset/list.py
from src.application.dto.dataset_dto import DatasetDto
from src.infrastructure.repositories.contract import DatasetRepositoryInterface
from src.shared.pagination import Page


class ListDatasetsUseCase:
    def __init__(self, dataset_repository: DatasetRepositoryInterface) -> None:
        self.dataset_repository = dataset_repository

    async def execute(self, *, cursor: str | None, page_size: int) -> Page[DatasetDto]:
        page = await self.dataset_repository.list_paginated(cursor=cursor, page_size=page_size)
        return Page[DatasetDto](
            items=[DatasetDto.model_validate(d) for d in page.items],   # from_attributes=True
            next_cursor=page.next_cursor,
            prev_cursor=page.prev_cursor,
            page_size=page.page_size,
        )
```

Things this gets right:

1. **Order by a stable composite key** — `created_at DESC, id DESC`. A single non-unique column (just `created_at`) produces flicker when two rows share a timestamp.
2. **Fetch `limit + 1`** — one extra row to detect "has more" without a separate `COUNT` query.
3. **`tuple_` comparison** for the seek — `WHERE (created_at, id) < (cursor_ts, cursor_id)` indexes properly in PostgreSQL.
4. **No COUNT(*)** — counting the whole table costs O(n); cursor doesn't need it.

### Why cursor over offset

- **Performance.** `OFFSET 10000 LIMIT 20` scans 10020 rows. Cursor's seek is O(log n) with the right index.
- **Stability.** With offset, inserting a row between calls duplicates an item across pages; deleting one skips an item. Cursor on a stable key sees the dataset at write-time, not page-fetch-time.
- **Indexability.** `(created_at DESC, id DESC)` is one index; `OFFSET` cannot use one efficiently past the first page.

### Backward / "prev" pagination

If your UI needs back-buttons, store a second cursor that walks the index the other way (reverse the sort, encode the same key). Many UIs don't need a real "prev" — a "back" button can just reuse the cursor from the previous request. Keep it out of the design unless it's required.

## Offset pagination — only when it's the right tool

Acceptable when **all** of these hold:

- The dataset is **bounded and small** (< ~10k rows).
- The endpoint is **admin or internal**, not user-facing.
- The UX **really wants page numbers** ("Page 12 of 47") and not infinite scroll.
- A consistent snapshot across pages isn't required.

```python
# src/infrastructure/repositories/user_repository.py
from sqlalchemy import func, select

from src.infrastructure.repositories.contract import PagedItems, UserRepositoryInterface


class UserRepository(UserRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_paged(self, *, page: int, page_size: int) -> PagedItems[User]:
        offset = (page - 1) * page_size
        stmt = select(User).order_by(User.email).offset(offset).limit(page_size)
        rows = (await self.session.execute(stmt)).scalars().all()
        total = (await self.session.execute(select(func.count()).select_from(User))).scalar_one()
        return PagedItems(items=rows, total_count=total, current_page=page, page_size=page_size)
```

The use-case then maps the entities into `UserDto`s via `model_validate` (per `backend/03-application-layer`) — repositories return domain entities, DTO conversion lives in the application layer.

Even here:

- **Cap `page_size`** (still `max=100`).
- **The COUNT(*) costs.** If the table grows, this becomes the slowest part of the request. Cache the count (every 30s) or remove the total from the response.
- **Don't expose `OFFSET` as the cursor.** Use page numbers (`?page=12`) — opaque to the client about what it's doing under the hood.

## Cap `page_size` server-side

```python
# src/shared/pagination.py
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

def clamp_page_size(requested: int | None) -> int:
    if requested is None:
        return DEFAULT_PAGE_SIZE
    return max(1, min(requested, MAX_PAGE_SIZE))
```

```python
from typing import Annotated
from fastapi import Depends, Query

@router.get("/datasets", response_model=Page[DatasetDto])
async def list_datasets(
    use_case: Annotated[ListDatasetsUseCase, Depends(get_list_datasets_use_case)],
    cursor: str | None = None,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> Page[DatasetDto]:
    return await use_case.execute(cursor=cursor, page_size=page_size)
```

`Query(...)` with `le=MAX_PAGE_SIZE` makes FastAPI reject `page_size=10000` with a 422 before it reaches the use-case. The use-case **also** clamps as defense-in-depth.

A client that requests 100k items is either a bug or an attack — return a structured 422, never serve the request.

## Sorts are an enum, not a string

```python
# good — explicit, validated
from enum import Enum

class DatasetSortKey(str, Enum):
    CREATED_AT = "created_at"
    NAME = "name"
    SIZE = "size"

@router.get("/datasets", response_model=Page[DatasetDto])
async def list_datasets(
    use_case: Annotated[ListDatasetsUseCase, Depends(get_list_datasets_use_case)],
    cursor: str | None = None,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    sort_by: DatasetSortKey = DatasetSortKey.CREATED_AT,
    sort_dir: Literal["asc", "desc"] = "desc",
) -> Page[DatasetDto]:
    return await use_case.execute(
        cursor=cursor, page_size=page_size, sort_by=sort_by, sort_dir=sort_dir,
    )

# bad — any column name from a query param
@router.get("/datasets")
async def list_datasets(sort: str = "created_at"):
    stmt = select(Dataset).order_by(text(f"{sort} desc"))  # ❌ SQLi
```

The bad version is a SQL-injection sink **and** a leaky abstraction (clients learn internal column names). The enum gives a documented, finite contract and the ORM picks the column safely.

For each sort key, **the cursor format must match the sort**. If you sort by `name`, the cursor encodes the name (and a tiebreaker `id`); don't mix sort-by-name with a `created_at` cursor.

## Filters use a documented convention

Pick one shape and apply it everywhere:

```
GET /datasets?status=archived&owner_id=42&created_after=2026-01-01
GET /users?role=admin&active=true
```

Document:

- **Equality** is the default (`?status=archived`).
- **Range** uses suffixes (`?created_after=`, `?created_before=`).
- **Multi-value** uses repeated params (`?status=archived&status=draft`) parsed into a list.
- **Search** uses a single `q=` parameter.
- Combine filters with `AND` (no `OR` in URL params — that's where SQL-string filters start).

If the team needs richer querying (boolean logic, nested filters), expose a dedicated endpoint with a JSON body — *not* a `?where=` string.

## No `total_count` unless asked

Returning a total on every list is tempting and expensive. For most user-facing lists, the user doesn't need "Page 12 of 9,432" — they need "next" / "previous". Drop the total.

If a use-case genuinely needs the count (admin pages, dashboards), expose it via a **separate** endpoint or query param (`?include_total=true`) so the cheap path stays cheap.

```python
# expensive — runs every request even when the client doesn't need it
class Page(BaseSchema, Generic[T]):
    items: list[T]
    total: int        # ❌ COUNT(*) cost per page fetch

# cheap — opt-in
class Page(BaseSchema, Generic[T]):
    items: list[T]
    next_cursor: str | None
    total: int | None = None   # populated only when ?include_total=true
```

## The shape of bugs this prevents

- **N+1 on list endpoints** — solved by selecting an explicit set of columns / eagerly loading relationships in the same query, not by paginating.
- **Page-2-shows-the-same-row-as-page-1** — caused by offset on a non-stable sort key; cursor on `(created_at DESC, id DESC)` eliminates it.
- **Endpoint times out on a tenant with 200k rows** — caused by `OFFSET 200000`; cursor's seek is O(log n).
- **Client OOM because someone passed `page_size=999999`** — server-side `le=MAX_PAGE_SIZE` catches it.
- **SQL injection via `?sort=created_at; DROP TABLE …`** — enum-typed sort keys reject it.

## Quick checklist

- [ ] Endpoint returns the canonical `Page[T]` envelope (`items`, `next_cursor`, `page_size`).
- [ ] Cursor-based by default; offset only with the four conditions above.
- [ ] Order-by is a **stable composite** (e.g. `(created_at DESC, id DESC)`), not a single non-unique column.
- [ ] `page_size` is capped server-side (FastAPI `Query(..., le=MAX_PAGE_SIZE)` + use-case clamp).
- [ ] Sort keys are an enum, not a free-form string.
- [ ] Filters follow the project's documented convention; no raw `where=` strings.
- [ ] `total_count` is opt-in or absent — never on by default.
- [ ] An integration test fetches **at least 2 pages** and asserts no duplicates / no skips.

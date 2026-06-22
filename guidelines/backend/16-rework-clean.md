---
model: sonnet
effort: high
---

# Rework & Refactor Clean

> "The best code is the code you never wrote."

Applies when changing *existing* code — bug fixes, targeted edits, and reworks that narrow a requirement. Covers over-touching, backwards-compatibility accumulation, and the rework workflow. For net-new code — new endpoints, new modules — see `backend/27-feature-discipline` (decision ladder, `ponytail:` convention).

AI agents over-touch. Given a bug fix, they rename surrounding variables "for clarity," extract helpers "while they're in there," and preserve old implementations "for safety." The result is a diff that obscures the real change, regressions in working code, and a codebase accumulating dead paths.

This guideline addresses two failure modes:

1. **Over-touching existing code** — refactoring, cleaning, or "improving" code adjacent to the task when only a targeted change was asked for
2. **Backwards-compatibility accumulation during reworks** — keeping old code alongside new code when the user has explicitly narrowed the requirement

---

## Over-Touching Existing Code

A bug fix fixes the bug. A config change changes the config. A one-line rename renames one thing. The task scope is the change scope — nothing else.

Agents routinely do more than asked: rename surrounding variables "for clarity," extract helpers "while they're in there," reformat files, upgrade related patterns. Every untasked touch is:

- A diff that obscures the real change
- A potential regression in working code
- Work the user did not ask for and cannot easily review

### Anti-pattern: Cleanup While Fixing

```python
# Task: fix the off-by-one error in pagination
# ❌ WRONG — agent fixes the bug AND refactors surrounding code
class DrugRepository:
    # Renamed from get_drugs_paginated (agent preferred shorter name)
    async def get_paged(
        self,
        page: int,
        size: int,
    ) -> list[Drug]:
        offset = (page - 1) * size  # bug fixed here
        # Agent also rewrote the query, added type hints, removed "unnecessary" blank lines
        return (await self._session.execute(
            select(Drug).offset(offset).limit(size)
        )).scalars().all()
```

```python
# ✅ CORRECT — one change, nothing else touched
async def get_drugs_paginated(self, page: int, size: int) -> list[Drug]:
    offset = (page - 1) * size  # was (page) * size — fixed
    result = await self._session.execute(
        select(Drug).offset(offset).limit(size)
    )
    return result.scalars().all()
```

### Rule

Change exactly what the task describes. Leave everything else exactly as it was — including formatting, naming, and structure you personally dislike. If you notice a separate problem, flag it in your reply; do not fix it silently.

---

## Backwards-Compatibility Accumulation — The Rework Problem

When a user reworks a feature, they are narrowing the requirement. The agent must narrow the code too — **not preserve the old breadth alongside the new implementation**.

The correct rule: **when you rework something, delete the old thing in the same commit. Update every call site. Merge nothing that leaves both paths alive.**

### Anti-pattern: Feature Flag With Dual Code Paths

```python
# ❌ WRONG — "temporary" flag; neither path can ever be removed
async def authenticate(
    body: AuthDto,
    session: AsyncSession = Depends(get_session),
    use_new_auth: bool = False,         # will never be deleted
) -> AuthSuccessDto:
    if use_new_auth:
        return await AuthUseCase(UserRepository(session)).execute(body)
    return await LegacyAuthUseCase(session).execute(body)
```

```python
# ✅ CORRECT — rework replaces; call sites updated; legacy deleted
async def authenticate(
    body: AuthDto,
    session: AsyncSession = Depends(get_session),
) -> AuthSuccessDto:
    return await AuthUseCase(UserRepository(session)).execute(body)
# LegacyAuthUseCase deleted. File deleted.
```

### Anti-pattern: v2 Function Alongside v1

```python
# ❌ WRONG — callers must choose; old one is never removed
async def create_drug(name: str, atc_code: str) -> Drug: ...
async def create_drug_v2(dto: CreateDrugDto) -> DrugDto: ...  # both kept
```

```python
# ✅ CORRECT — one function; signature updated; all callers updated in the same PR
async def create_drug(dto: CreateDrugDto) -> DrugDto: ...
# create_drug (old signature) deleted. Zero occurrences in codebase.
```

### Anti-pattern: Permanent Migration Shim

```python
# ❌ WRONG — adapter added "during migration"; TODO never executed
class LegacyDrugServiceAdapter:
    """TODO: remove once all callers updated."""   # 8 months ago
    def get(self, id: int) -> dict:
        drug = DrugRepository(session).get_by_id(id)
        return {"id": drug.id, "name": drug.inn}  # old dict shape
```

Update the callers and delete the adapter **in the same PR**. If you cannot update all callers now, do not merge the new implementation yet.

### Anti-pattern: Commented-Out Old Code

```python
# ❌ WRONG
async def get_invoice(invoice_id: int, ...) -> InvoiceDto:
    # Old query — kept for reference
    # result = await session.execute(text(f"SELECT * FROM invoices WHERE id = {invoice_id}"))
    # return dict(result.fetchone())
    return await GetInvoiceUseCase(InvoiceRepository(session)).execute(invoice_id, current_user.id)
```

Git history is the reference. Delete the old code.

### Anti-pattern: Use Case Narrowed by User, Broadened by Agent

```python
# User says: "remove bulk create, only single-item is needed"
# ❌ WRONG — agent keeps bulk to avoid "breaking" callers
class CreateDrugUseCase:
    async def execute(self, dto: CreateDrugDto | list[CreateDrugDto]) -> DrugDto | list[DrugDto]:
        if isinstance(dto, list):
            return [await self._create_one(d) for d in dto]   # no longer required
        return await self._create_one(dto)
```

```python
# ✅ CORRECT — implement exactly what was asked; callers that needed bulk now loop themselves
class CreateDrugUseCase:
    async def execute(self, dto: CreateDrugDto) -> DrugDto:
        ...
```

### Anti-pattern: Repository Interface With Zero-Caller Methods

```python
# ❌ WRONG — deprecated method preserved "for compatibility"
class DrugRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, id: int) -> Drug | None: ...
    @abstractmethod
    async def get_by_legacy_sku(self, sku: str) -> Drug | None: ...  # zero callers
```

```python
# ✅ CORRECT — removed from interface and from every concrete implementation
class DrugRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, id: int) -> Drug | None: ...
```

---

## The Rework Workflow

```
1. Understand the narrowed requirement exactly.
2. Implement the new version.
3. Update EVERY call site to the new version.
4. DELETE the old implementation, its imports, its tests, its fixtures.
5. Run the test suite. Fix breakage. Commit everything together.
```

Steps 3–4 are what agents skip. They implement step 2 and stop, leaving both paths alive. Merge only when step 4 is done.

---

## Rules Summary

- **Touch only what the task requires** — do not rename, reformat, or refactor adjacent code
- **When a requirement is narrowed, the code is narrowed** — not kept broad "for compatibility"
- **Deletion over addition**
- **No TODO: remove old implementation** — remove it now, or don't merge
- **No feature flags with both `True` and `False` paths active simultaneously**
- **No commented-out old code** — git history is the reference

---

## Quick Checklist

- [ ] Only code required by the task was changed — no adjacent renames, reformats, or refactors
- [ ] Reworked function replaces the old one — no parallel versions in the same codebase
- [ ] Old function deleted; all call sites updated before merging
- [ ] No feature flags with both `True` and `False` paths active simultaneously
- [ ] No commented-out old code — git history is the reference
- [ ] Unused imports and modules deleted, not left behind
- [ ] Use case narrowed by the user → implementation narrowed in code, not expanded
- [ ] Repository interface cleaned of methods with zero callers
- [ ] Validation, error handling, security, and auth are intact — minimizing never touches these

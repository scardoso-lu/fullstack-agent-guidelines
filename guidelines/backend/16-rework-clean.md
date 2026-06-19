# Rework Clean — The Ponytail Principle

When an AI agent reworks a function, route, or service, it defaults to preserving the old implementation alongside the new one. The reasoning sounds safe: "keep the old one while the new one is proven." In practice it creates debt that never gets paid — dead paths, compatibility flags, v2 functions next to v1 functions, and adapter layers that outlive the migration by years.

**The user narrows the concept → the agent widens the implementation. This is backwards.**

The [Ponytail principle](https://github.com/DietrichGebert/ponytail): the best code is code you never wrote. When you rework something, cut the old thing completely in the same change. A narrow, correct implementation that solves the actual problem beats a generalized one that tries to preserve all past behaviour.

---

## The Decision Ladder — Before Writing Anything

Before adding any new code, walk down this ladder:

1. **Does this need to exist?** — If the feature was removed or narrowed, delete code, don't replace it with an empty stub.
2. **Does the stdlib or framework already do it?** — Use that; don't wrap it.
3. **Is there an existing installed dependency that solves it?** — Use that.
4. **Can it be one function/class?** — Write one. Not one per "variant".
5. **Only then:** implement the minimum that solves the current requirement.

Non-negotiable even when minimizing: validation at trust boundaries, error handling, security checks, auth guards.

---

## Anti-Patterns: What Accumulates

### Feature Flag Left Alive Forever

```python
# ❌ WRONG — the flag means neither path can ever be removed
async def authenticate(
    body: AuthDto,
    session: AsyncSession = Depends(get_session),
    use_new_auth: bool = False,         # "temporary" — will never be deleted
) -> AuthSuccessDto:
    if use_new_auth:
        return await NewAuthUseCase(UserRepository(session)).execute(body)
    return await LegacyAuthUseCase(session).execute(body)  # old path kept "for safety"
```

```python
# ✅ CORRECT — rework replaces; call sites updated in the same PR
async def authenticate(
    body: AuthDto,
    session: AsyncSession = Depends(get_session),
) -> AuthSuccessDto:
    return await AuthUseCase(UserRepository(session)).execute(body)
# LegacyAuthUseCase deleted. legacy_auth.py deleted.
```

### v2 Function Next to v1

```python
# ❌ WRONG — callers must choose; old one never removed
async def create_drug(name: str, atc_code: str) -> Drug:
    ...

async def create_drug_v2(dto: CreateDrugDto) -> DrugDto:  # new — both kept
    ...
```

```python
# ✅ CORRECT — one function, all call sites updated
async def create_drug(dto: CreateDrugDto) -> DrugDto:
    ...
# create_drug (old signature) deleted. All callers updated.
```

### Permanent Adapter / Shim

```python
# ❌ WRONG — migration shim that was never removed
class LegacyDrugServiceAdapter:
    """Adapter added during migration. TODO: remove once all callers updated."""
    # "TODO" from 8 months ago — callers were never updated
    def get(self, id: int) -> dict:
        drug = DrugRepository(session).get_by_id(id)
        return {"id": drug.id, "name": drug.inn}  # old dict format
```

```python
# ✅ CORRECT — callers updated to use the repository directly; adapter deleted
drug = await DrugRepository(session).get_by_id(id)
return DrugDto.model_validate(drug)
```

### Commented-Out Code

```python
# ❌ WRONG — dead code preserved "just in case"
async def get_invoice(invoice_id: int, ...) -> InvoiceDto:
    # Old implementation — kept for reference
    # invoice = await session.execute(text(f"SELECT * FROM invoices WHERE id = {invoice_id}"))
    # return dict(invoice.fetchone())

    # New implementation
    return await GetInvoiceUseCase(InvoiceRepository(session)).execute(invoice_id, owner_id=user.id)
```

```python
# ✅ CORRECT — old code deleted, not commented. Git history is the reference.
async def get_invoice(invoice_id: int, ...) -> InvoiceDto:
    return await GetInvoiceUseCase(InvoiceRepository(session)).execute(invoice_id, owner_id=user.id)
```

### Unused Import / Module Kept "Just in Case"

```python
# ❌ WRONG
from src.infrastructure.db.legacy_session import get_legacy_session   # no longer used
from src.infrastructure.repositories.legacy_drug_repo import LegacyDrugRepo  # no callers
```

Ruff/linters catch unused imports, but entire legacy modules silently accumulate if no tool checks at the file level.

---

## The Correct Rework Workflow

```
1. Understand the NEW requirement exactly — what it does, what it no longer does.
2. Implement the narrow new version.
3. Update EVERY call site to the new version.
4. DELETE the old implementation, all its imports, its test fixtures.
5. Run tests. Fix breakage. Commit everything together.
```

Steps 3–4 are what AI agents skip. They implement step 2 and stop, leaving the old version "for the caller to choose." The caller never chooses — both paths rot in parallel.

---

## Applied to Use Cases

When a use case is narrowed (e.g., "stop supporting bulk operations, only single-item create"):

```python
# ❌ WRONG — agent keeps bulk to avoid "breaking" callers
class CreateDrugUseCase:
    async def execute(self, dto: CreateDrugDto | list[CreateDrugDto]) -> DrugDto | list[DrugDto]:
        if isinstance(dto, list):
            return [await self._create_one(d) for d in dto]  # bulk — no longer needed
        return await self._create_one(dto)
```

```python
# ✅ CORRECT — bulk removed; the one route that called it updated to loop if needed
class CreateDrugUseCase:
    async def execute(self, dto: CreateDrugDto) -> DrugDto:
        ...
```

If the caller still needs bulk, the caller loops. Business logic doesn't carry the weight of every caller's past needs.

---

## Applied to Repository Interfaces

When a method is removed from the contract:

```python
# ❌ WRONG — deprecated method kept on the interface
class DrugRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, id: int) -> Drug | None: ...
    @abstractmethod
    async def get_by_legacy_sku(self, sku: str) -> Drug | None: ...   # no callers, kept "for compatibility"
```

```python
# ✅ CORRECT — unused method removed from interface AND from the concrete implementation
class DrugRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, id: int) -> Drug | None: ...
```

---

## What NOT to Cut

The principle is about **dead paths**, not about correctness:

- Error handling → always keep
- Auth/permission checks → always keep  
- Input validation → always keep
- Logging of auth failures → always keep
- Database constraints → always keep

Cutting a compatibility shim is not the same as cutting a guard.

---

## Quick Checklist

- [ ] Reworked functions replace the old one in the same commit — no parallel versions
- [ ] Old function signature deleted; all call sites updated before merging
- [ ] No feature flags with both `True` and `False` paths active
- [ ] No "TODO: remove legacy implementation" comments — remove it now or don't merge
- [ ] No commented-out old code — git history is the reference
- [ ] Unused imports and modules deleted, not commented out
- [ ] Use case narrowed by the user → use case implementation narrowed in code, not expanded with "also handle old case"
- [ ] Repository interface cleaned of methods with zero callers

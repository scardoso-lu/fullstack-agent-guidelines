# Audit-on-Write — The Hard Gate for Every Mutation

Use when adding a use-case that writes (creates, updates, deletes, archives, mutates state), when reviewing such a slice, or when designing the base use-case / Unit of Work. Defines the **hard rule**: every write emits a structured audit event in the **same DB transaction** as the write — atomically, or neither. Defines the event schema, the base-use-case pattern that makes this automatic, the test that verifies it, and the DoD-blocking review check.

The audit trail is the system of record for "what changed, by whom, when, and as part of which request." Compliance, debugging, and security review all depend on it being **complete**. Completeness is achievable only if the audit write happens in the **same transaction** as the business write — anything else lets the two diverge.

## The rule (hard DoD gate)

> Every use-case that **writes** emits a structured audit event in the **same DB transaction** as the write.
>
> - If the business write commits, the audit event commits.
> - If the business write rolls back, the audit event rolls back.
> - There is no third state.
>
> A use-case with a write path that does not emit an audit event **fails the DoD gate**.

This is the **only** hard write gate. Observability (operational logs) is a soft check; audit-on-write is not.

## Why same-transaction matters

```python
# bad — two transactions, audit can diverge
async def archive_dataset(self, dataset_id: int) -> None:
    async with get_session() as session:                       # transaction 1: business write
        dataset = await self.dataset_repository.get_by_id(dataset_id)
        dataset.archive()
        await self.dataset_repository.save(dataset)
    async with get_session() as session:                       # transaction 2: audit
        await self.audit.write(action="dataset.archived", entity_id=dataset_id)
    # what if the process crashes between them?
```

The window between the two transactions is small but real. A process restart, a DB blip, or an exception in the audit write produces a state that's *forensically broken*: the dataset is archived, but the audit log doesn't show it. Compliance auditors and security reviewers cannot accept this.

```python
# good — one transaction, atomic (single session, commit at the context boundary)
async def archive_dataset(self, dataset_id: int) -> None:
    async with get_session() as session:                       # commits on clean exit, rolls back on raise
        dataset = await self.dataset_repository.get_by_id(dataset_id)
        dataset.archive()
        await self.dataset_repository.save(dataset)
        await self.audit.write(
            action="dataset.archived",
            entity_type="Dataset",
            entity_id=dataset_id,
            actor_id=self.actor.id,
            correlation_id=self.actor.correlation_id,
        )
```

Either both rows land in the database, or neither does. There is no partial commit.

## The event schema

A minimum audit event includes:

| Field | Source | Why |
|---|---|---|
| `id` | DB-generated | Primary key. |
| `created_at` | DB-default `now()` | When (DB clock; do not trust client). |
| `correlation_id` | Request middleware | Link to operational logs and across systems. |
| `actor_id` | Auth context | Who. May be a user, service account, or system actor. |
| `actor_type` | Auth context | `user` / `service` / `system`. |
| `tenant_id` | Auth context (if multi-tenant) | Whose data. |
| `action` | Use-case | Dotted verb: `dataset.archived`, `user.created`. |
| `entity_type` | Use-case | `Dataset`, `User`. |
| `entity_id` | Use-case | The primary key of the affected entity. |
| `payload` (optional) | Use-case | JSONB. Before/after deltas or other context. **No secrets, no PII.** |

The payload should be **small** and **purposeful**. "The whole entity, before and after" is tempting and wrong — it bloats the table and frequently contains data that shouldn't be re-stored.

## The base-use-case pattern

Don't make every use-case author this by hand — it'll be forgotten. Bake it into the base class / unit-of-work:

```python
# src/application/use_cases/base.py
from abc import ABC, abstractmethod
from typing import Any

from src.application.audit import AuditEvent, AuditWriter
from src.application.context import ActorContext
from src.infrastructure.db.engine import get_session


class WriteUseCase(ABC):
    def __init__(self, audit: AuditWriter, actor: ActorContext) -> None:
        self.audit = audit
        self.actor = actor

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        async with get_session() as session:                 # single session — single transaction
            result, audit_events = await self._do(*args, **kwargs)
            for event in audit_events:
                await self.audit.write(
                    actor_id=self.actor.id,
                    correlation_id=self.actor.correlation_id,
                    **event.model_dump(),
                )
            return result

    @abstractmethod
    async def _do(self, *args: Any, **kwargs: Any) -> tuple[Any, list[AuditEvent]]:
        ...
```

```python
# src/application/use_cases/dataset/archive.py
from src.application.audit import AuditEvent, AuditWriter
from src.application.context import ActorContext
from src.application.use_cases.base import WriteUseCase
from src.infrastructure.repositories.contract import DatasetRepositoryInterface


class ArchiveDatasetUseCase(WriteUseCase):
    def __init__(
        self,
        dataset_repository: DatasetRepositoryInterface,    # interface, not concrete (per backend/03)
        audit: AuditWriter,
        actor: ActorContext,
    ) -> None:
        super().__init__(audit=audit, actor=actor)
        self.dataset_repository = dataset_repository

    async def _do(self, dataset_id: int) -> tuple[None, list[AuditEvent]]:
        dataset = await self.dataset_repository.get_by_id(dataset_id)
        if dataset is None:
            raise DatasetNotFoundError(dataset_id)
        dataset.archive()
        await self.dataset_repository.save(dataset)
        return None, [
            AuditEvent(
                action="dataset.archived",
                entity_type="Dataset",
                entity_id=dataset_id,
            ),
        ]
```

The repository is injected via the **constructor** — per the rule in `backend/03-application-layer`, the use-case sees the **interface** from `contract.py`, never the concrete `DatasetRepository`. The concrete class is named only in the presentation/tools wiring (per `backend/04-infrastructure-layer`).

The author of `ArchiveDatasetUseCase` cannot forget the audit event — the base class refuses to commit without one (you can enforce: a write-shaped `_do` whose returned events list is empty is a defect; lint or runtime-check this).

## Action verbs are dotted and stable

Same convention as log event names:

```
dataset.created
dataset.archived
dataset.deleted
user.invited
user.role_changed
auth.login.success
auth.password_reset.confirmed
```

- `entity.action` form.
- Past tense — the audit records what **happened**, not what was attempted. (Attempts go in operational logs, not audit.)
- **Stable** once shipped — operations and compliance run reports against these strings.

## What counts as a "write"

- **INSERT / UPDATE / DELETE** on any persistent table.
- **State transitions** (publish, archive, restore).
- **Authentication events** that affect state (successful login that creates a session; not failed login attempts — those are warnings in logs).
- **Permission grants / revocations.**
- **External side effects with consequences** — sending an email that's part of a workflow (password reset), enqueuing an irreversible task (a bulk delete job).

What does NOT count:

- **Read operations.** A read isn't auditable in this sense; if you need read-access audit (e.g. PII access logs), that's a separate stream with its own design.
- **Cache writes, log writes, metric increments.** Those are operational, not business.
- **Failed writes** (validation rejected, permission denied). The fact of the attempt may be operationally interesting; it doesn't change persistent state, so it's a log, not an audit.

## Async / worker-split workflows

For long-running operations that split across an API request and a background worker (see `backend/11-async-patterns`), audit-on-write applies to **both halves**:

- **API leg.** The "started" event (`import.requested`, `dataset.bulk_delete.queued`) is written in the API's transaction.
- **Worker leg.** The "completed" or "failed" event (`import.completed`, `dataset.bulk_delete.failed`) is written in the worker's transaction.

The `correlation_id` is the same across both, so the full lifecycle of the request reconstructs into a single thread.

## The test

Every write use-case has a test that asserts the audit event was written **in the same transaction** as the business write:

```python
async def test_archive_dataset_writes_audit_in_same_transaction(session: AsyncSession):
    dataset = await create_dataset_fixture(session)
    repo = DatasetRepository(session)
    use_case = ArchiveDatasetUseCase(
        dataset_repository=repo,
        audit=AuditWriter(session),
        actor=fake_actor(),
    )

    await use_case.execute(dataset_id=dataset.id)

    audit_rows = (
        await session.execute(
            select(AuditEvent).where(AuditEvent.action == "dataset.archived")
        )
    ).scalars().all()
    assert len(audit_rows) == 1
    assert audit_rows[0].entity_id == dataset.id
    assert audit_rows[0].actor_id == fake_actor().id
```

And — crucially — a test that asserts **rollback rolls back the audit**:

```python
async def test_archive_dataset_failure_rolls_back_audit(session: AsyncSession, monkeypatch):
    dataset = await create_dataset_fixture(session)
    repo = DatasetRepository(session)
    use_case = ArchiveDatasetUseCase(
        dataset_repository=repo,
        audit=AuditWriter(session),
        actor=fake_actor(),
    )

    # Force the business write to fail after the audit row would be staged
    monkeypatch.setattr(DatasetRepository, "save", failing_save)
    with pytest.raises(DatasetWriteError):
        await use_case.execute(dataset_id=dataset.id)

    audit_rows = (
        await session.execute(
            select(AuditEvent).where(AuditEvent.action == "dataset.archived")
        )
    ).scalars().all()
    assert audit_rows == []   # rolled back with the business write
```

These two tests are the only way to be sure the same-transaction guarantee actually holds. Code review can't verify it by inspection alone.

## The DoD gate check

At gate time, the reviewer (and `qa-reviewer`) explicitly checks every new write path in the diff for:

1. An emitted audit event.
2. In the **same transaction** as the write.
3. With the canonical fields (actor, correlation_id, action, entity_type, entity_id).
4. A test that asserts (1)–(3).

A write without one of these is **routed back to the engineer** — it's a DoD failure, not a comment.

## Why not "we'll add it later"

The audit table without atomicity becomes a probabilistic record — *most* writes are audited, but some aren't. Once a single audit gap exists, the entire trail is suspect: a compliance auditor can no longer say "if it's not in the audit, it didn't happen." They have to say "if it's not in the audit, maybe it happened and we missed it." That's not a trail; that's noise.

Hard gate, every slice, from the start.

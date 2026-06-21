---
model: opus
effort: high
---

# Safe Migrations — Alembic, Online Schemas, and Backfills

Use when authoring an Alembic migration, when reviewing a slice that changes the schema, or when planning a deploy that includes a migration. Defines the **safe-migration ruleset**: additive-first, no `NOT NULL` on populated tables without a default, no destructive change in the same release as the code that depends on it, the **expand → migrate → contract** pattern, batch backfills, and how to author migrations so a rollback never strands the system.

Migrations are the riskiest single thing a backend slice can ship. A bad one locks a table for ten minutes in production, or — worse — leaves the schema and the deployed code disagreeing about reality. The mitigation is a small set of rules, applied to every migration, with no "this one is small enough to skip them".

## The rule

> Schema changes are **additive first**.
> Destructive changes (drops, renames, type changes, `NOT NULL` on populated columns) ship **after** the code that no longer depends on the old shape.
> Backfills run in **batches**, not one transaction.
> Every migration has a working `downgrade()` — or the migration is **explicitly one-way** and gated.
> The migration is reviewed against **production-scale data**, not the dev database with 12 rows.

## Expand → migrate → contract

The pattern that makes any non-trivial schema change safe:

1. **Expand** — add the new shape **alongside** the old. New column nullable, new table empty, new constraint as `NOT VALID`. Deploy. Old code keeps working.
2. **Migrate** — backfill data, dual-write from the application if the change is ongoing, validate constraints. Deploy code that *reads from the new shape* while still writing both.
3. **Contract** — once nothing depends on the old shape, drop it. Deploy.

The single-step alternative ("rename `username` to `handle`") *will* fail on a real production system because the application code and the schema deploy at different moments. Always at least two releases for a non-additive change.

## Safe operations — usually OK in one migration

| Operation | Risk | Why OK |
|---|---|---|
| `ADD COLUMN ... NULL` | Low | Existing rows get `NULL`; old code ignores the column. Metadata-only on Postgres ≥ 11. |
| `ADD COLUMN ... NOT NULL DEFAULT <const>` | Low (Postgres ≥ 11) | Constant default is metadata-only; no rewrite. **Volatile defaults (`now()`) still rewrite.** |
| `CREATE INDEX CONCURRENTLY` | Low | Does not lock writes. Cannot run in a transaction — see notes. |
| `CREATE TABLE` | Low | New table; nothing depends on it yet. |
| `ALTER COLUMN ... DROP NOT NULL` | Low | Relaxes the constraint; existing data still valid. |
| `ADD CONSTRAINT ... NOT VALID` then `VALIDATE CONSTRAINT` | Low | Constraint is added without a full-table scan; validation runs after, without locking. |
| `ALTER TABLE ... SET DEFAULT ...` | Low | Future rows only; doesn't touch existing rows. |

## Dangerous operations — never in one step on a real table

| Operation | Why | Safe approach |
|---|---|---|
| `ALTER COLUMN ... SET NOT NULL` on populated column | Full-table rewrite + exclusive lock | Add column nullable → backfill in batches → set `NOT NULL` after every row is populated. |
| `ADD CONSTRAINT` without `NOT VALID` | Full-table scan under lock | `ADD CONSTRAINT ... NOT VALID`, then `VALIDATE CONSTRAINT` separately. |
| `ALTER COLUMN ... TYPE ...` (incompatible cast) | Full-table rewrite + exclusive lock | Add new column → backfill with cast → swap in two releases → drop old column. |
| `DROP COLUMN` while old code still reads it | Old code errors after deploy | Stop reading in release N; drop in release N+1. |
| `RENAME COLUMN` | Old code references the old name | Add new column → dual-write → swap reads → drop old column. (Four releases for a true online rename.) |
| `CREATE INDEX` (non-concurrent) on a large table | Exclusive lock for the duration of the build | Always `CREATE INDEX CONCURRENTLY`. |
| `ADD FOREIGN KEY` to a populated table | Full-table scan under lock | `ADD CONSTRAINT ... NOT VALID`, then `VALIDATE CONSTRAINT`. |
| `lock_timeout` not set | A blocked DDL waits behind a long-running tx until it lands behind it | Set a short `lock_timeout` in the migration (e.g. 5s); fail fast and retry, don't queue. |

Every one of these has a "safe approach" — multi-step, but each step is cheap and reversible. There is no production-safe shortcut.

## The Alembic skeleton — Postgres example

```python
"""add archived_at to datasets

Revision ID: 2026_06_21_0001
Revises: 2026_06_20_0007
Create Date: 2026-06-21 14:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_06_21_0001"
down_revision = "2026_06_20_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Expand — additive column, nullable by default
    op.add_column(
        "datasets",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Index it concurrently so reads of "non-archived" stay fast
    op.execute("COMMIT")                            # required: CONCURRENTLY can't run in a tx
    op.create_index(
        "ix_datasets_archived_at",
        "datasets",
        ["archived_at"],
        postgresql_concurrently=True,
        if_not_exists=True,
    )

def downgrade() -> None:
    op.drop_index("ix_datasets_archived_at", table_name="datasets")
    op.drop_column("datasets", "archived_at")
```

Notes that the template gets right:

- **Nullable on add.** Existing rows get `NULL`; the column means "never archived" implicitly.
- **`CONCURRENTLY` outside a transaction.** Alembic wraps migrations in a transaction by default; for `CREATE INDEX CONCURRENTLY` you must commit first. Or set `transactional_ddl = False` per migration.
- **`if_not_exists`.** A retried failed migration doesn't double-create.
- **A working `downgrade`.** This one is simple; complex migrations get a real reverse path or are marked one-way.

## The `NOT NULL` ratchet — three releases, not one

The most common AI mistake: `nullable=False` on a populated table.

```python
# bad — locks the table, rewrites every row, blocks reads/writes
op.add_column("orders", sa.Column("customer_id", sa.Integer, nullable=False))
```

Safe pattern, across three deploys:

**Release N — Expand:**

```python
def upgrade() -> None:
    op.add_column("orders", sa.Column("customer_id", sa.Integer, nullable=True))
    op.execute("COMMIT")
    op.create_index(
        "ix_orders_customer_id", "orders", ["customer_id"], postgresql_concurrently=True
    )
```

Deploy code that:
- Writes `customer_id` on every new insert.
- Tolerates `NULL` on reads (legacy rows).

**Release N+1 — Backfill + constrain (gradually):**

```python
def upgrade() -> None:
    # Backfill in batches — no full-table UPDATE.
    conn = op.get_bind()
    batch_size = 5_000
    while True:
        result = conn.execute(sa.text("""
            WITH cte AS (
                SELECT id FROM orders
                WHERE customer_id IS NULL
                LIMIT :batch
                FOR UPDATE SKIP LOCKED
            )
            UPDATE orders
            SET customer_id = (SELECT lookup_customer_id(orders.legacy_ref))
            WHERE id IN (SELECT id FROM cte)
        """), {"batch": batch_size})
        if result.rowcount == 0:
            break

    # Add the constraint as NOT VALID — no full-table scan under lock.
    op.execute("""
        ALTER TABLE orders
        ADD CONSTRAINT orders_customer_id_not_null CHECK (customer_id IS NOT NULL) NOT VALID
    """)
```

**Release N+2 — Contract:**

```python
def upgrade() -> None:
    # Validate the constraint (online — concurrent reads/writes proceed)
    op.execute("ALTER TABLE orders VALIDATE CONSTRAINT orders_customer_id_not_null")
    # Promote to a real NOT NULL — fast now because the CHECK has already proven it
    op.alter_column("orders", "customer_id", nullable=False)
    op.drop_constraint("orders_customer_id_not_null", "orders")
```

Three releases. Each one is cheap and reversible. The single-step version locks `orders` for as long as it takes to scan every row.

## Batched backfills — never one transaction over a million rows

```python
def upgrade() -> None:
    conn = op.get_bind()
    batch = 1_000
    sleep_ms = 100   # let WAL ship, replicas catch up, autovacuum breathe
    while True:
        result = conn.execute(sa.text("""
            UPDATE my_table
            SET new_col = some_expr
            WHERE id IN (
                SELECT id FROM my_table
                WHERE new_col IS NULL
                ORDER BY id
                LIMIT :batch
                FOR UPDATE SKIP LOCKED
            )
        """), {"batch": batch})
        if result.rowcount == 0:
            break
        time.sleep(sleep_ms / 1000)
```

Reasons this matters:

- **WAL pressure.** A million-row UPDATE in one transaction generates a million WAL records before commit — replicas lag, disks fill, backups fail.
- **Lock duration.** Long transactions hold locks that block autovacuum and other writes.
- **Rollback cost.** If the migration fails 90% through a one-shot UPDATE, you roll back 100% of the work. Batched, you've committed the first 900k rows and only retry the rest.
- **`FOR UPDATE SKIP LOCKED`.** Concurrent writes to the same row don't deadlock — they're skipped and picked up later.

For very large backfills (tens of millions of rows), the backfill belongs in **application code** as a background task tracked in a job row, not in the migration. Migrations should be short.

## `lock_timeout` — fail fast

```python
def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    op.add_column(...)
```

Without `lock_timeout`, a DDL statement that's blocked behind a long transaction will wait — and **every other query that needs the same lock** queues behind the DDL. The result is a self-inflicted outage: one slow `SELECT` blocks the migration, the migration blocks every write to the table, the writes pile up.

With `lock_timeout = 5s`, the migration fails after 5 seconds; CI/operator retries when the blocker is gone. The application stays responsive.

## Two-step rename pattern

Renaming a column safely is not one migration:

**Release N — add `new_name`, dual-write from the app:**

```python
op.add_column("users", sa.Column("handle", sa.String, nullable=True))
op.execute("COMMIT")
op.create_index("ix_users_handle", "users", ["handle"], postgresql_concurrently=True)
```

Application writes to both `username` and `handle`; reads still come from `username`.

**Release N+1 — backfill + switch reads:**

```python
def upgrade() -> None:
    conn = op.get_bind()
    while conn.execute(sa.text(
        "UPDATE users SET handle = username WHERE handle IS NULL AND id IN ("
        " SELECT id FROM users WHERE handle IS NULL LIMIT 5000)"
    )).rowcount:
        time.sleep(0.1)
```

Application switches reads to `handle`; still writes both.

**Release N+2 — drop `username`:**

```python
op.drop_column("users", "username")
```

By this point, nothing reads or writes `username`. Drop is safe.

## `downgrade()` — write one, or mark the migration one-way

A `downgrade()` that's wrong is worse than no downgrade — it lies. Two acceptable patterns:

1. **Real downgrade.** Inverse of upgrade. Always for additive migrations; usually for type changes if you've kept the old column.
2. **Explicit one-way.** Some migrations genuinely can't be reversed (a destructive rename that has shipped through three releases). Document it:

```python
def downgrade() -> None:
    raise NotImplementedError(
        "This migration drops `users.username` after a four-release rename. "
        "Rollback requires restoring from backup."
    )
```

A migration without a downgrade and without an explicit one-way mark is a defect.

## Test the migration against production-scale data

A migration that works on a dev DB with 12 rows is meaningless. Before a release that contains a non-trivial migration:

- **Time it on a copy of production data** (snapshot, masked if needed).
- **Watch the lock graph** while it runs (`pg_locks`, `pg_stat_activity`).
- **Confirm rollback works** on the same copy.

If the timing exceeds the team's deploy window or the lock acquisition contends with normal traffic, redesign before shipping.

## Quick checklist

- [ ] The migration is additive (or part of an explicit expand → migrate → contract sequence).
- [ ] No `nullable=False` on a populated column in one step.
- [ ] No `ADD CONSTRAINT` without `NOT VALID` on a large table.
- [ ] `CREATE INDEX CONCURRENTLY` is used for index builds on populated tables (with the required `COMMIT` first).
- [ ] `lock_timeout` and `statement_timeout` are set in the migration.
- [ ] Backfills run in **batches**, with `FOR UPDATE SKIP LOCKED` and a short sleep between batches.
- [ ] `downgrade()` exists and is correct, **or** the migration is marked explicitly one-way.
- [ ] The migration has been timed and locked-checked against a production-scale copy.
- [ ] An integration test asserts the schema after `upgrade()` matches the model definitions.

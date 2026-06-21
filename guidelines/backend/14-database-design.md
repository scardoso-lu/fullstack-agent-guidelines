---
model: opus
effort: high
---

# Database Design: OLTP and Normalization

Use when designing a database schema, adding a new table, or writing a migration. Covers OLTP normalization, foreign key constraints, indexing strategy, and common schema mistakes that cause N+1 queries.

A SaaS backend lives and dies by its database schema. A poorly designed schema causes data inconsistencies, painful migrations, and N+1 queries that kill performance at scale. Normalization is the discipline that prevents these problems.

OLTP (Online Transaction Processing) workloads — the kind every SaaS app runs — are characterized by many small reads and writes. They demand schemas optimized for correctness and write speed, not for flat reports.

---

## The Three Normal Forms

### 1NF — First Normal Form: Atomic Values, No Repeating Groups

Every column holds exactly one value. No arrays, no comma-separated strings, no "phone1 / phone2 / phone3" columns.

**Violated:**
```python
class OrderBad(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_ids: Mapped[str] = mapped_column(String)   # "12,47,89" — violates 1NF
    tags: Mapped[str] = mapped_column(String)          # "urgent,vip" — violates 1NF
```

**Fixed — separate table for multi-valued data:**
```python
class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
```

### 2NF — Second Normal Form: No Partial Dependencies

Every non-key column depends on the **whole** primary key, not just part of it. Only applies to composite primary keys.

**Violated:**
```python
# Composite PK (order_id, product_id) — but product_name only depends on product_id
class OrderItemBad(Base):
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    product_name: Mapped[str] = mapped_column(String)   # partial dependency — violates 2NF
    quantity: Mapped[int] = mapped_column()
```

**Fixed — product_name belongs in the products table:**
```python
class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

class OrderItem(Base):
    __tablename__ = "order_items"
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)   # snapshot at time of order
```

`unit_price` is stored on `OrderItem` intentionally — it's the price at the time of purchase, not a dependency on `products.price`.

### 3NF — Third Normal Form: No Transitive Dependencies

Non-key columns must depend on the primary key directly, not through another non-key column.

**Violated:**
```python
class UserBad(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254))
    zip_code: Mapped[str] = mapped_column(String(10))
    city: Mapped[str] = mapped_column(String(100))    # depends on zip_code, not id — violates 3NF
    country: Mapped[str] = mapped_column(String(100)) # depends on zip_code, not id — violates 3NF
```

**Fixed — extract the dependent data:**
```python
class ZipCode(Base):
    __tablename__ = "zip_codes"
    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    zip_code: Mapped[str | None] = mapped_column(ForeignKey("zip_codes.code"), nullable=True)
```

---

## Entity Design Rules

### Always Use Surrogate Keys

Use a system-generated ID (`bigint` or snowflake), not a business key, as the primary key:

```python
_id_gen = SnowflakeGenerator(42)

class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True, default=lambda: next(_id_gen))
    # NOT: plan_code as PK — business keys change (rebrand, merge)
    stripe_subscription_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
```

### Foreign Keys Are Mandatory

Every relationship must have a FK constraint. Without FKs, orphaned rows accumulate silently:

```python
class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),   # prevent deleting customer with invoices
        nullable=False,
        index=True,                                         # always index FK columns
    )
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),  # delete invoices when subscription deleted
        nullable=False,
        index=True,
    )
```

`ondelete` options:
- `RESTRICT` — prevents deletion of the parent (use for business-critical relationships)
- `CASCADE` — deletes children automatically (use for owned/dependent records)
- `SET NULL` — nullifies the FK (use when the relationship is optional)

### `nullable=False` by Default

Columns should be `NOT NULL` unless you have a specific reason for nullability. NULL is a source of bugs:

```python
# ✅ Explicit about what can be null
email: Mapped[str] = mapped_column(String(254), nullable=False)
cancelled_at: Mapped[datetime | None] = mapped_column(nullable=True)   # intentionally nullable

# ❌ SQLAlchemy defaults to nullable=True — easy to forget
description: Mapped[str] = mapped_column(String)   # nullable by default, unintended
```

### Timestamps on Every Table

```python
from sqlalchemy import func

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

class Customer(TimestampMixin, Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    ...
```

---

## Indexing Strategy

Bad indexing is the most common cause of slow SaaS queries.

```python
from sqlalchemy import Index

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)          # PK = clustered index
    email: Mapped[str] = mapped_column(String(254), unique=True)  # unique = unique index
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)  # FK = index
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Composite index for the most common query pattern
    __table_args__ = (
        Index("ix_users_tenant_status", "tenant_id", "status"),  # WHERE tenant_id=? AND status=?
    )
```

**Index rules:**
- Primary key: automatic
- Every FK column: always add `index=True`
- `unique=True` columns: automatic unique index
- Columns used in `WHERE` clauses with high cardinality: add index
- Columns used only in `SELECT`: do NOT index (write overhead for no benefit)

---

## Anti-Patterns to Avoid

### JSON Blobs in Relational Tables

```python
# ❌ Tempting but wrong — you lose all relational integrity
class Order(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    items: Mapped[dict] = mapped_column(JSON)   # [{product_id: 1, qty: 2}, ...]
    # Can't query individual items, can't enforce FKs, can't aggregate across orders
```

Use a proper `OrderItem` table. Reserve JSON columns for truly schema-less data (user preferences, feature flags).

### Entity-Attribute-Value (EAV)

```python
# ❌ The "flexible schema" trap — destroys query performance
class Attribute(Base):
    entity_id: Mapped[int]
    key: Mapped[str]     # "price", "color", "weight"
    value: Mapped[str]   # everything is a string — no types, no constraints
```

Use proper columns. If you need dynamic attributes, use a JSONB column in PostgreSQL instead of EAV.

### Storing Derived Data

```python
# ❌ Total stored in DB — gets out of sync with line items
class Order(Base):
    total_amount: Mapped[Decimal]   # who keeps this in sync?

# ✅ Compute on read, or use a database view
@property
def total_amount(self) -> Decimal:
    return sum(item.unit_price * item.quantity for item in self.items)
```

---

## Multi-Tenant Schema Design

SaaS apps must isolate tenant data. The safest approach is a `tenant_id` column on every user-owned table:

```python
class TenantScopedMixin:
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

class Invoice(TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    ...
```

Every repository method that lists or fetches data must filter by `tenant_id`. This is enforced at the use case level, never left to the route handler.

---

## Quick Checklist

- [ ] No comma-separated values or arrays stored in a single column (1NF)
- [ ] No column that describes a non-key attribute of another non-key column (3NF)
- [ ] Every table has a surrogate integer/snowflake primary key
- [ ] Every FK column has `nullable=False` and `index=True`
- [ ] `ondelete` behavior is explicitly set on every FK (`RESTRICT`, `CASCADE`, or `SET NULL`)
- [ ] Every table has `created_at` and `updated_at` via a mixin
- [ ] No JSON blobs for data that needs querying or FK integrity
- [ ] Multi-tenant tables have `tenant_id` FK and every repository query filters by it
- [ ] Composite indexes match your most common `WHERE` clause patterns

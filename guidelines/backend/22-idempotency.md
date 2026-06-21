---
model: opus
effort: high
---

# Idempotency — Retry-Safe Writes, Keys, and Deduplication

Use when designing any POST endpoint that may be retried (payments, webhooks, bulk-job enqueues, user-triggered actions over flaky networks), when integrating a webhook receiver, or when a write must survive client retries without double-effect. Defines the **idempotency key** pattern (client-supplied `Idempotency-Key` header, server-stored result, replay on duplicate), the **at-most-once** vs **at-least-once** distinction, the **idempotent-by-design** alternative (UPSERT, natural keys), and how to make webhook consumers safe.

A POST that doesn't survive a retry is a bug waiting to ship. The internet drops packets; mobile networks fail; users mash buttons; webhook senders retry on a timeout. Any of these can cause "the request didn't reach the server" or "the request reached the server but the response didn't reach the client" — and the client will retry. Without idempotency, retries double-charge, double-create, double-everything.

## The rule

> Every write endpoint that **isn't naturally idempotent** accepts an `Idempotency-Key` header from the client.
> The server records the result keyed by `(actor, endpoint, key)` and **replays the original response** on duplicate.
> The key is stored with a TTL (typical: 24h).
> Webhook receivers verify the sender's delivery ID and dedupe on it.

PUT and DELETE on a specific resource are idempotent by definition. POST that creates a new resource, sends an email, charges a card, or enqueues a job is **not** — and needs the pattern.

## Two ways to be idempotent

There are two strategies. **Prefer the first** when the operation has a natural key.

### Strategy 1 — Idempotent by design (natural key + UPSERT)

The operation has a stable identifier the client can construct: an external order ID, a deduplication hash of the payload, a UUID the client generated. The server uses it as a uniqueness constraint and `INSERT ... ON CONFLICT DO NOTHING` (or `DO UPDATE`).

```python
# good — natural key + UPSERT — no extra storage, no race
class CreateOrderUseCase(WriteUseCase):
    def __init__(
        self,
        order_repository: OrderRepositoryInterface,
        audit: AuditWriter,
        actor: ActorContext,
    ) -> None:
        super().__init__(audit=audit, actor=actor)
        self.order_repository = order_repository

    async def _do(self, dto: CreateOrderDto) -> tuple[OrderDto, list[AuditEvent]]:
        # The repository owns the UPSERT (uses its self.session); the use-case stays at the domain level.
        order = await self.order_repository.upsert_by_external_id(
            external_id=dto.external_id,        # client-supplied, unique
            customer_id=dto.customer_id,
            amount_cents=dto.amount_cents,
        )
        return OrderDto.model_validate(order), [
            AuditEvent(action="order.created", entity_type="Order", entity_id=order.id),
        ]
```

The corresponding repository method (lives in infrastructure, per `backend/04-infrastructure-layer`):

**`src/infrastructure/repositories/order_repository.py`**
```python
from sqlalchemy.dialects.postgresql import insert

class OrderRepository(OrderRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_by_external_id(
        self, *, external_id: str, customer_id: int, amount_cents: int
    ) -> Order:
        stmt = (
            insert(Order)
            .values(external_id=external_id, customer_id=customer_id, amount_cents=amount_cents)
            .on_conflict_do_nothing(index_elements=["external_id"])
            .returning(Order)
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is not None:
            return row
        # The row already existed from a previous retry — load it.
        existing = (
            await self.session.execute(
                select(Order).where(Order.external_id == external_id)
            )
        ).scalar_one()
        return existing
```

This is the cheapest, most reliable idempotency you can build:

- No second storage system.
- No race condition — the DB's unique constraint handles concurrent retries.
- The audit event still emits once, in the same transaction as the row.

Prefer this when the client can supply a natural ID. Many systems can — payment intents, webhook event IDs, file-upload-tokens — and didn't.

### Strategy 2 — Generic `Idempotency-Key` (header-based)

When the operation has no natural key (a new payment with no client-side ID, an action that triggers side-effects, a multi-row create), the client sends an `Idempotency-Key` header (a UUID), and the server caches the result keyed by it.

**`src/shared/idempotency.py`**
```python
from datetime import datetime, timedelta
from sqlalchemy import select

KEY_TTL = timedelta(hours=24)

class IdempotencyStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find(self, actor_id: int, endpoint: str, key: str) -> IdempotencyRecord | None:
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.actor_id == actor_id,
            IdempotencyRecord.endpoint == endpoint,
            IdempotencyRecord.key == key,
            IdempotencyRecord.expires_at > func.now(),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save(
        self,
        actor_id: int,
        endpoint: str,
        key: str,
        request_hash: str,
        response_status: int,
        response_body: dict,
    ) -> None:
        record = IdempotencyRecord(
            actor_id=actor_id,
            endpoint=endpoint,
            key=key,
            request_hash=request_hash,
            response_status=response_status,
            response_body=response_body,
            expires_at=datetime.utcnow() + KEY_TTL,
        )
        self.session.add(record)
        await self.session.flush()           # per backend/04: flush in repo/store, commit in session ctx
```

**`src/payments/api.py`**
```python
from typing import Annotated
from fastapi import Depends, Header

@router.post("/charges", response_model=ChargeDto, status_code=201)
async def create_charge(
    dto: CreateChargeDto,
    actor: Annotated[ActorContext, Depends(get_actor)],
    use_case: Annotated[CreateChargeUseCase, Depends(get_create_charge_use_case)],
    store: Annotated[IdempotencyStore, Depends(get_idempotency_store)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ChargeDto:
    if idempotency_key:
        existing = await store.find(actor.id, "POST /payments/charges", idempotency_key)
        if existing is not None:
            _ensure_same_request(existing.request_hash, dto)
            return ChargeDto.model_validate(existing.response_body)

    result = await use_case.execute(dto)

    if idempotency_key:
        await store.save(
            actor_id=actor.id,
            endpoint="POST /payments/charges",
            key=idempotency_key,
            request_hash=_hash_request(dto),
            response_status=201,
            response_body=result.model_dump(),
        )
    return result
```

The route is shown inline for clarity, but it's right at the edge of the "≤10 lines" rule in `backend/05-presentation-layer`. In real code, lift the idempotency dance into a **FastAPI dependency** (`Depends(idempotent_request)`) that returns either the replayed response or `None`; the route then stays thin and the use-case stays oblivious to the idempotency machinery.

Things to get right:

1. **Scope keys to the actor.** Otherwise a client's key collides with another client's.
2. **Scope keys to the endpoint.** Same key against `POST /charges` and `POST /refunds` are different intents.
3. **Hash the request body** and store it. If the same key arrives with a *different* body, that's a client bug — reject with `409 Conflict`, never silently return the original result. The body hash is your safety net.
4. **Store the response** (status + body) so the replay is byte-identical.
5. **TTL the records** — 24h is typical; longer if the legal/business need requires it.
6. **The check + the write happen in the same transaction.** The actual side-effect (charge, enqueue, send email) is committed; *then* the idempotency record is written. If the side-effect fails, no record is written, and the retry will execute properly.

### Atomic transaction shape

The naive order — "store key first, then do the work" — has a window where the key exists but the work failed. The right order:

```
BEGIN
  acquire row lock on (actor_id, endpoint, key)  -- SELECT ... FOR UPDATE
  IF a stored record exists -> replay and return
  perform the work (charge, enqueue, send) — domain-side, in this tx if possible
  store the idempotency record with the result
COMMIT
```

The `FOR UPDATE` lock on the key serializes concurrent retries — only one wins; the others wait, then read the result. This makes the pattern safe against two-clients-retry-at-once.

If the work has external side-effects (a real payment gateway call) that can't be rolled back, the strategy shifts to: **call the gateway first using its own idempotency key**, then store our record with the gateway's response. The gateway's own idempotency does the heavy lifting; ours just shields our DB.

## "Same key, different body" → 409, not replay

```python
def _ensure_same_request(stored_hash: str, body: BaseSchema) -> None:
    if _hash_request(body) != stored_hash:
        raise IdempotencyKeyConflictError(
            "Idempotency-Key reused with a different request body"
        )
```

This is a contract violation — the client is using the key wrong. Returning the original response would silently misuse the key; rejecting with 409 makes the bug visible. Document this behavior in the API.

## Webhook receivers — dedupe on the sender's event ID

You don't control the sender's retry behavior. They will redeliver. The sender always provides a unique event ID — Stripe `event.id`, GitHub `X-GitHub-Delivery`, Slack `X-Slack-Request-Timestamp` plus signature. Use it.

**`src/webhooks/payments_router.py`**
```python
from typing import Annotated
from fastapi import Body, Depends, Header, Response

@router.post("/webhooks/payments")
async def receive(
    payload: Annotated[dict, Body()],
    signature: Annotated[str, Header(alias="Stripe-Signature")],
    use_case: Annotated[HandlePaymentWebhookUseCase, Depends(get_handle_payment_webhook_use_case)],
) -> Response:
    _verify_signature(payload, signature)               # always verify first
    event_id = payload.get("id")
    if not event_id:
        raise InvalidWebhookError("missing event id")
    await use_case.execute(event_id=event_id, payload=payload)
    return Response(status_code=204)
```

```python
class HandlePaymentWebhookUseCase(WriteUseCase):
    def __init__(
        self,
        webhook_event_repository: WebhookEventRepositoryInterface,
        payment_service: PaymentServiceInterface,
        audit: AuditWriter,
        actor: ActorContext,
    ) -> None:
        super().__init__(audit=audit, actor=actor)
        self.webhook_event_repository = webhook_event_repository
        self.payment_service = payment_service

    async def _do(self, event_id: str, payload: dict) -> tuple[None, list[AuditEvent]]:
        # The unique constraint on (source, event_id) is the dedupe — repo owns the SQL.
        was_new = await self.webhook_event_repository.try_insert(
            source="payments", event_id=event_id, payload=payload
        )
        if not was_new:
            return None, []                          # already processed; no audit
        await self.payment_service.dispatch(payload)
        return None, [
            AuditEvent(action="payment.webhook.processed", entity_type="WebhookEvent", entity_id=event_id),
        ]
```

The repository owns the `INSERT ... ON CONFLICT DO NOTHING` (per `backend/04-infrastructure-layer`); the use-case stays at the domain level and asks the repo "was this newly inserted?".

Three things this gets right:

1. **Signature verification first.** Never process a webhook whose authenticity isn't checked. (See `backend/13-owasp-top10` for the cryptographic details.)
2. **The DB constraint is the dedupe.** Same as Strategy 1 above — no race, no second store.
3. **Always return 204** — even on duplicates. The sender doesn't need to know it was a duplicate; they need to know "delivered". Don't return 200 with a "duplicate" body that the sender's parser doesn't understand.

## Retry semantics — at-most-once vs at-least-once

The internet is **at-least-once** by default. Pretending otherwise produces bugs.

| Semantic | Cost to achieve | When you actually want it |
|---|---|---|
| **At-most-once** | Drop on first failure; client takes the loss. | Almost never. |
| **Exactly-once** | Doesn't exist over an unreliable network. The closest approximation is **at-least-once + idempotency**. | The default goal. |
| **At-least-once + idempotency** | The patterns in this guide. | Default for every write. |

Design every write to **safely tolerate being delivered more than once**, and you've solved the problem. The opposite — "we'll just retry less" — adds latency for the user and still produces duplicates whenever a packet drops on the response leg.

## Storage choice for the idempotency record

The DB table works for most cases — same transaction as the work, same backup story. If the load is very high (millions of requests/day), a Redis-backed store with the same shape (atomic `SETNX` + value) is faster, at the cost of split storage and a different durability profile.

Don't reach for Redis on day one. The DB is fine until it isn't.

## Anti-patterns

- **No idempotency at all.** A retry double-charges. Ship one of the two strategies.
- **Generating the key server-side.** Defeats the purpose — the client can't dedupe its own retry if it doesn't supply the key.
- **Ignoring the body hash.** A client that reuses keys across different operations silently corrupts data; the hash catches it.
- **Replaying after the side-effect succeeded but before storing the record.** Without the same-transaction commit, retries can double-fire. Lock-then-do-then-store.
- **No TTL.** The table grows unbounded; the per-actor lookup gets slower; eventually you have a 50GB table of 6-month-old keys nobody will ever replay. 24h is a good default; document the longest legitimate retry window in your environment and use that.
- **Webhook without signature verification.** An attacker fakes a webhook; you process it. Verify first, always.
- **Returning a different status on the replay.** First call returned `201`; replay returns `200`. Clients parse `2xx` the same, but tools that match exact status codes break. Replay byte-identically.

## Quick checklist

- [ ] Every POST that has side-effects either uses a natural-key UPSERT or accepts `Idempotency-Key`.
- [ ] Keys are scoped to `(actor_id, endpoint, key)`.
- [ ] The body hash is stored; a key reused with a different body returns **409**.
- [ ] The check + work + record-write are in **one transaction** with a `FOR UPDATE` lock on the key.
- [ ] Records have a TTL (24h default).
- [ ] Webhooks verify the signature first, then dedupe on the sender's event ID.
- [ ] An integration test fires the same request twice with the same `Idempotency-Key` and asserts exactly one row / one charge / one audit event.
- [ ] An integration test fires the same key with a different body and asserts **409**.

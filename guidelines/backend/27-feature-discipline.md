---
model: sonnet
effort: high
---

# New Feature Discipline

> "The best code is the code you never wrote."

Applies when building new features, adding new endpoints, or writing net-new code. Covers the six-rung decision ladder, the `ponytail:` comment convention, and non-negotiable safeguards. For changes to *existing* code — reworks, refactors, bug fixes — see `backend/16-rework-clean`.

AI agents over-build. Given a task, they install dependencies, create wrapper classes, add configuration layers, and generalise everything "for future use." The result is 5× more code than necessary, slower execution, and a codebase the user can no longer navigate.

The task is narrow → the implementation must be equally narrow. This is the core principle.

---

## The Decision Ladder

Before writing any code, stop at the **first rung that holds**:

```
1. Does this need to exist?           → Skip it (YAGNI)
2. Does the stdlib provide it?        → Use that
3. Is it a native platform feature?   → Use that
4. Is it already installed?           → Use that
5. Can it be one function / one line? → Write that
6. Only then: the minimum that works
```

Apply this ladder **at every coding decision point** — not just at the start of a task. Each new function, each new import, each new class triggers the same check.

### What the ladder prevents

| Requested task | Agent default | Correct answer |
|---|---|---|
| Email validation | Install `email-validator`, write `EmailValidator` class with regex, format, MX-record check | `z.string().email()` (already installed) or `re.match(r"[^@]+@[^@]+\.[^@]+", email)` |
| Rate limiting on a route | Write `RateLimiter` class with Redis backend, sliding window, config file | `slowapi` is already installed — `@limiter.limit("5/minute")` |
| CSV column sum | Parse manually, handle edge cases, write `CsvProcessor` | `sum(float(row["amount"]) for row in csv.DictReader(f))` |
| Password hashing | Install `argon2-cffi`, write `PasswordHasher` with salt management | `bcrypt` is already installed — one line in the entity setter |

---

## Non-Negotiable Safeguards

Minimizing code **never** means cutting these:

- **Trust-boundary validation** — all inputs from users or external APIs are validated
- **Data-loss handling** — operations that can fail destructively have error handling
- **Security** — auth checks, secret handling, SQL parameterization
- **Error propagation** — errors are raised or returned, never swallowed

The goal is code that is small because it is **necessary**, not artificially compressed. This is not code golf.

---

## The `ponytail:` Comment Convention

When a deliberate simplification has a known limitation, mark it inline:

```python
# ponytail: linear scan — acceptable for <1000 drugs; replace with index if dataset grows
def find_drug_by_inn(drugs: list[Drug], inn: str) -> Drug | None:
    return next((d for d in drugs if d.inn.lower() == inn.lower()), None)
```

This makes the trade-off visible and the upgrade path explicit, without adding premature complexity now.

---

## Rules Summary

- **No abstractions that weren't explicitly requested**
- **No new dependency if the stdlib or an installed package already does it**
- **No boilerplate nobody asked for**
- **Deletion over addition**
- **Boring over clever**
- **Minimize file count** — the correct number of files is the minimum that keeps concerns separated

---

## Quick Checklist

- [ ] Decision ladder walked before writing anything: does this need to exist? stdlib? platform? installed? one line?
- [ ] `ponytail:` comment added for any deliberate simplification with a known upgrade path
- [ ] No new dependency installed when an existing package already covers it
- [ ] No wrapper class or abstraction layer added without a second concrete consumer
- [ ] Validation, error handling, security, and auth are intact — minimizing never touches these

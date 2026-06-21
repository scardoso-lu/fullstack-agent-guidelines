# Conventional Commits — One Commit per Checkpoint

Use when committing changes inside a slice, when reviewing commit history, or when configuring commitlint / release automation. Defines the Conventional Commits format (type, scope, description, body, footer), the type catalogue, the breaking-change syntax, and the "incremental along the slice" commit cadence.

A commit message is documentation for future-you (and for the release notes generator). It says **what changed**, **where**, **why**, and **whether it breaks anything** — in a format that humans skim and tools can parse. Conventional Commits is the format the team uses everywhere.

## The format

```
<type>(<scope>): <description>

<optional body — what and why, not how>

<optional footer — references, BREAKING CHANGE, Co-Authored-By>
```

- `<type>` (required) — one of the types below.
- `<scope>` (optional, recommended) — the area touched: a module name, `auth`, `api`, `ui`, `db`, etc. Use the project's actual module names.
- `<description>` (required) — present-tense, imperative, lowercase, no trailing period, **≤ 72 characters**. "add password reset use-case", not "added password reset use-case" or "Adds password reset use-case.".
- Body and footer are optional; blank line between header / body / footer.

## The type catalogue

| Type | Purpose |
|---|---|
| `feat` | A new feature visible to users or to API consumers. |
| `fix` | A bug fix. |
| `docs` | Documentation only — README, ADRs, code comments. |
| `style` | Formatting only (whitespace, trailing commas). **Not** styling/CSS — that's `feat` or `fix`. |
| `refactor` | Restructuring without changing behavior. No new feature, no bug fix. |
| `perf` | A performance improvement that is measurably better. |
| `test` | Adding or fixing tests only. |
| `build` | Build system, package manager, lockfile changes. |
| `ci` | CI/CD configuration. |
| `chore` | Maintenance, dependency bumps that aren't `build`, housekeeping. |
| `revert` | Reverts a previous commit. Body should name the reverted SHA. |

If two types fit, pick the one with the **stronger semantic**: `feat` over `refactor`, `fix` over `chore`.

## Breaking changes

A breaking change is **any** change that requires a consumer to act (API contract change, removed feature, schema migration that can't auto-apply). Mark it in one of two ways:

```
feat(auth)!: remove /v1/login in favor of /v2/login
```

Or with a footer:

```
feat(auth): add /v2/login with refresh tokens

BREAKING CHANGE: /v1/login is removed. Migrate clients to /v2/login;
refresh tokens replace long-lived sessions.
```

Either form makes the release tool bump the major version. Use the footer form when the explanation is non-trivial — the `!` alone hides the migration story.

## The body (when to write one)

Write a body when the **why** isn't obvious from the diff:

- A workaround for a third-party bug → name the bug.
- A non-obvious algorithmic choice → cite the constraint that forced it.
- A revert → name the commit being reverted and the symptom it caused.

Don't write a body that paraphrases the diff. "Adds the new function and exports it" is noise — the diff already says that.

## Footers

- `Closes #123` / `Refs #456` — issue references.
- `Co-Authored-By: Name <email>` — for pair-programming or AI assistance attribution.
- `BREAKING CHANGE: <explanation>` — see above.
- `Reviewed-by: …` — when the team uses sign-offs.

## Commit cadence inside a slice

**Commit incrementally along the slice — one commit per meaningful checkpoint, not a single end-of-slice dump.** A meaningful checkpoint is a moment where the work has a stable shape that future-you could roll back to:

1. `feat(auth): add PasswordResetToken entity` — domain layer locked.
2. `feat(auth): add RequestPasswordReset use-case` — use-case green with its unit tests.
3. `feat(auth): expose POST /auth/reset/request route` — API surface wired.
4. `feat(auth): add password-reset request page` — frontend wired.
5. `test(auth): add E2E for password-reset request flow` — DoD's E2E item green.

Incremental commits make `git bisect` work, make code review readable, and let you cherry-pick or revert a single layer if it goes wrong. The opposite ("one giant commit at the end") loses all of that.

## What never goes in a commit

- **Secrets.** Never commit `.env`, credentials, tokens, private keys. Even briefly — a force-push doesn't erase a leaked secret; rotate it.
- **Build artifacts** that aren't already in `.gitignore`.
- **Two unrelated changes.** "Fix login bug + add new dashboard widget" — split it.

## Git safety

- **Never amend a pushed commit.** Future-you and the rest of the team can't see what changed.
- **Never `--force` push to a shared branch** (default branch, release branches). On your own slice branch, `--force-with-lease` if you must rebase.
- **Never `--no-verify`** unless the user explicitly asks. Pre-commit hooks are the local DoD — bypassing them means CI catches what you didn't.
- **A failed pre-commit hook means the commit didn't happen.** Fix the issue, re-stage, and create a **new** commit — do not `--amend`, because `--amend` would modify the *previous* commit (which still exists) and you'd lose the change you were trying to land.

## A good commit, end to end

```
feat(auth): add password-reset request use-case

Adds RequestPasswordReset use-case with a TTL'd PasswordResetToken
entity. Emits an audit event in the same transaction as the token
write, per ADR-0014.

Closes #287
Refs #283
```

A bad commit:

```
stuff
```

```
WIP
```

```
fixed it
```

These tell future-you nothing. If a commit message could be replaced by `git diff` and lose no information, the message wasn't doing any work.

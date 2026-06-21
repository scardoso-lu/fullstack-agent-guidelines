# Pull Requests — One Slice, One Reviewable PR

Use when opening a PR for a finished slice, or when writing the PR template the team uses. Defines the PR template (summary, type, included changes, testing, checklist), the rule "one slice = one PR", the rebase-not-merge default, and the convention that draft PR bodies live as git-ignored `*.pr.md` files until the PR is created.

A pull request is the unit of review and the artifact that ships. The PR body is the changelog entry, the review prompt, and the audit trail — all at once. Treat it like documentation, not a chat message.

## The rule

> One slice → one PR. The PR's diff matches the slice's branch. The PR description follows the project template, filled in from the **actual** commits and diff.

A PR that bundles two slices forces the reviewer to evaluate two things at once; the gate can't either. If you discover work outside the ticket while the slice is in flight, file a new ticket — don't grow the PR.

## The template

The PR body shape lives in a single file (commonly `.github/pull_request_template.md` or `assets/pull_request_template.md`). Read it at runtime and fill it; don't retype the structure into each PR.

A solid template covers:

```markdown
## Summary

<2–4 sentences: what changed, why, and the ticket it traces to. Cite the ADR
if the slice consumes one.>

## Type of change

- [ ] feat — new user-visible capability
- [ ] fix — bug fix
- [ ] refactor — no behavior change
- [ ] docs — documentation only
- [ ] chore / build / ci — tooling

## Included changes

### Features
- …

### Fixes
- …

### Improvements
- …

(Delete sub-sections that don't apply.)

## Testing

- [ ] Unit tests added / updated
- [ ] Integration tests added / updated (testcontainers, not mocks)
- [ ] Playwright E2E added / updated for the affected flow
- [ ] DoD gate green locally (`make gate`)

Tick only what was **actually done**. Never claim a test that wasn't written.

## Related issues / tickets

Closes #<ticket>

## Reviewer checklist

- [ ] Audit event emitted on every write path (same transaction)
- [ ] Every new route has `require("<permission>")`
- [ ] No Critical/High security findings open
- [ ] ERD refreshed (if the slice changed a model / FK / constraint)
```

## Title

One concise, imperative line — typically the same as the slice's lead commit:

```
feat(auth): add password reset flow
```

If the repo's commit history follows Conventional Commits (it should — see `agile/03-conventional-commits`), the PR title follows the same shape. Reference the ticket in the title only if the repo's history does.

## Draft drafts as git-ignored `.pr.md` files

When generating the PR body before creating the PR, write it to `./<slug>.pr.md` (e.g. `password-reset.pr.md`). These files are **transient** — they exist so the user can review/edit the body, then feed it to `gh` / `az` / paste it manually. They never enter git history:

- Add `*.pr.md` to the repo's root `.gitignore` if it isn't already there.
- Delete them after the PR is created.

This keeps draft iterations out of commits while preserving the editable artifact during review.

## Creating the PR — the human picks the path

After the draft body is approved, **the human picks** how the PR is opened. Suggest a default based on the detected remote, but never auto-open:

| Choice | Command |
|---|---|
| GitHub CLI | `gh pr create --title "<title>" --body-file <slug>.pr.md --base <default>` |
| Azure DevOps CLI | `az repos pr create --title "<title>" --description @<slug>.pr.md --source-branch <branch> --target-branch <default>` |
| Manual | Paste the `.pr.md` contents into the platform's UI. |

Opening a PR is an outward, hard-to-undo action — confirm the exact command before running it.

## Rebase, don't merge (default)

Default to **rebase-and-merge** (or squash-and-merge if the team prefers a single tidy commit per PR), not merge-commit. The history reads as a clean sequence of slices instead of a tangle of merge bubbles. The exception: merge commits are appropriate when preserving the granular commit history of a long-lived branch matters more than linearity.

Whatever the team picks, **the project chooses one** and applies it consistently. Mixed strategies make `git log` unreadable.

## Review etiquette

- **Reviewer reads the PR body first**, then the diff. If the body doesn't make sense, the diff won't help.
- **One round-trip per concern.** A reviewer who comments "consider X" gets either "done, see commit Y" or "I considered X; here's why I went with the current approach" — not silence.
- **Block on Critical/High security findings.** A failing security check is on equal footing with a failing test.
- **Don't bikeshed.** Style/preference comments are suggestions, not blockers. The DoD's lint/format gate is the source of truth for style.

## When a PR drags

If a PR has been open for more than ~3 days without merging, something is wrong: the slice was too big, the gate is flaky, or the team is overloaded. Diagnose the root cause — don't keep the PR open indefinitely:

- **Slice too big** → split it. Cherry-pick the safe parts into a smaller PR, defer the rest.
- **Gate flaky** → fix the flake before merging anything else. A flaky gate erodes trust until everyone bypasses it.
- **No reviewer bandwidth** → either tighten the review SLA (e.g. "reviews within 24h") or rotate reviewers; don't let PRs rot.

## Anti-patterns

- **PR with 30 commits and no body.** The body is where the slice is explained; commits are the trail.
- **"Refactor + feature" PR.** Reviewers can't separate "did the feature work?" from "did the refactor break anything?". Split.
- **Force-push to `main` to fix a bad PR merge.** Always revert via a new PR; force-push to a shared branch breaks every other engineer's checkout.
- **Self-merging without review** (outside trivial doc fixes the team has agreed to self-merge). The second pair of eyes is part of the gate.

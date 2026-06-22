---
model: sonnet
effort: extract
---

# Definition of Done — Security Checklist

Hard gate — owned by the security review. Every item must be green before a slice merges. For the full DoD overview (how to run the gate, failure handling, why it's hard) see `agile/02-definition-of-done`.

## Security checklist

- [ ] **No open Critical or High finding** across code SAST, dependency CVEs, Docker image scan, secrets, and supply-chain checks (see `backend/13-owasp-top10` and `frontend/07-owasp-top10` for the catalog).
- [ ] **Slice honored the security guidance** set at slice start (threat model + secure-coding requirements).
- [ ] **Per-ticket security report** exists at the project's security-report location (e.g. `docs/security/<ticket>.md`).

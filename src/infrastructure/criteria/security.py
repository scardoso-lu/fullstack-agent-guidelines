from src.domain.entities.compliance import ComplianceCriterion

CRITERIA: list[ComplianceCriterion] = [
    # ── from backend/08-security.md ──────────────────────────────────────────
    ComplianceCriterion(
        id="security/secrets/no-hardcoded-defaults",
        guideline_slug="backend/08-security",
        stack="security",
        text="JWT_SECRET and DATABASE_URL have no default values in Settings — crash at startup if missing",
        category="secrets",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the Settings class from src/config/settings/__init__.py",
        forbidden_pattern=r"(JWT_SECRET|DATABASE_URL)\s*:\s*str\s*=\s*['\"]",
    ),
    ComplianceCriterion(
        id="security/auth/bcrypt-for-passwords",
        guideline_slug="backend/08-security",
        stack="security",
        text="Passwords are hashed with bcrypt — not SHA-256, MD5, or plain text",
        category="auth",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the entity class that handles password storage",
        required_pattern=r"bcrypt\.hashpw\s*\(|bcrypt\.checkpw\s*\(",
    ),
    ComplianceCriterion(
        id="security/auth/jwt-verified-decode",
        guideline_slug="backend/08-security",
        stack="security",
        text="jwt.decode() is used for token validation (verifies signature and expiry automatically)",
        category="auth",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the token validation function or auth middleware",
        required_pattern=r"jwt\.decode\s*\(",
    ),
    ComplianceCriterion(
        id="security/auth/token-expiry-set",
        guideline_slug="backend/08-security",
        stack="security",
        text="Access tokens include an exp claim — stolen tokens must not be valid forever",
        category="auth",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the token generation function",
        required_pattern=r"[\"']exp[\"']\s*:|timedelta\s*\(",
    ),
    ComplianceCriterion(
        id="security/auth/no-bare-except-in-auth",
        guideline_slug="backend/13-owasp-top10",
        stack="security",
        text="Auth functions never pass silently on exceptions — must fail closed (raise HTTPException), not open",
        category="auth",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the authentication dependency / get_current_user function",
        forbidden_pattern=r"except[^:]*:\s*\n\s*pass\b",
    ),
    # ── from backend/13-owasp-top10.md ───────────────────────────────────────
    ComplianceCriterion(
        id="security/owasp/no-sql-interpolation",
        guideline_slug="backend/13-owasp-top10",
        stack="security",
        text="No SQL string interpolation — all queries use ORM or bound :param placeholders",
        category="injection",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the repository methods that execute database queries for this slice",
        forbidden_pattern=r"text\s*\(\s*f['\"]|\.execute\s*\(\s*f['\"]",
    ),
    ComplianceCriterion(
        id="security/owasp/no-pickle-loads",
        guideline_slug="backend/13-owasp-top10",
        stack="security",
        text="No pickle.loads() on untrusted data — use Pydantic model_validate_json() instead",
        category="injection",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste any code that deserializes external or user-provided data",
        forbidden_pattern=r"pickle\.loads\s*\(",
    ),
    ComplianceCriterion(
        id="security/owasp/global-exception-handler",
        guideline_slug="backend/13-owasp-top10",
        stack="security",
        text="Global exception handler strips stack traces in production responses",
        category="error-handling",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the FastAPI app setup file where exception handlers are registered",
        required_pattern=r"@\w+\.exception_handler\s*\(\s*Exception\s*\)",
    ),
    ComplianceCriterion(
        id="security/owasp/pip-audit-in-ci",
        guideline_slug="backend/13-owasp-top10",
        stack="security",
        text="pip-audit, safety, or Trivy runs in CI and breaks the build on CVE findings",
        category="supply-chain",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the CI workflow file (.github/workflows/ci.yml)",
        required_pattern=r"pip.audit|safety\s+check|trivy",
    ),
    ComplianceCriterion(
        id="security/owasp/queries-owner-scoped",
        guideline_slug="backend/13-owasp-top10",
        stack="security",
        text="All data queries are scoped to owner_id or tenant_id — enforced in use cases, not routes",
        category="access-control",
        severity="required",
        check_type="manual",
        verification_hint=(
            "For each new repository query in the slice, confirm it filters by owner_id or tenant_id. "
            "Provide the query method name and the WHERE clause or filter used."
        ),
    ),
    ComplianceCriterion(
        id="security/owasp/rate-limiting-on-auth",
        guideline_slug="backend/13-owasp-top10",
        stack="security",
        text="Rate limiting applied to /auth/login and /auth/forgot-password endpoints",
        category="access-control",
        severity="recommended",
        check_type="code_pattern",
        verification_hint="Paste the login and forgot-password route handler(s)",
        required_pattern=r"@\w+\.limit\s*\(|RateLimiter\s*\(",
    ),
    # ── Security headers ─────────────────────────────────────────────────────
    ComplianceCriterion(
        id="security/headers/cors-not-wildcard",
        guideline_slug="backend/13-owasp-top10",
        stack="security",
        text="CORS allow_origins is not a wildcard (*) — only explicit origins are permitted",
        category="headers",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the FastAPI app setup or CORSMiddleware configuration",
        forbidden_pattern=r'allow_origins\s*=\s*\[["\']?\s*\*\s*["\']?\]|allow_origin_regex\s*=\s*["\'].*\.\*',
    ),
    ComplianceCriterion(
        id="security/headers/security-middleware",
        guideline_slug="backend/13-owasp-top10",
        stack="security",
        text=(
            "Security headers middleware is registered: TrustedHostMiddleware or equivalent "
            "that sets X-Content-Type-Options, X-Frame-Options, and HSTS"
        ),
        category="headers",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the FastAPI app setup file where middleware is added",
        required_pattern=r"TrustedHostMiddleware|X-Content-Type-Options|X-Frame-Options|Strict-Transport-Security|SecurityHeadersMiddleware",
    ),
    # ── Hardcoded secrets ─────────────────────────────────────────────────────
    ComplianceCriterion(
        id="security/secrets/no-provider-api-keys",
        guideline_slug="backend/08-security",
        stack="security",
        text="No provider API key literals in source (Stripe sk_live_*, AWS AKIA*, GitHub ghp_*, etc.)",
        category="secrets",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the files that integrate with payment, cloud, or third-party providers",
        forbidden_pattern=(
            r"sk_live_[a-zA-Z0-9_\-]{10,}"
            r"|sk_test_[a-zA-Z0-9_\-]{10,}"
            r"|whsec_[a-zA-Z0-9_\-]{10,}"
            r"|AKIA[0-9A-Z]{16}"
            r"|ghp_[a-zA-Z0-9]{36}"
            r"|AIza[0-9A-Za-z\-_]{35}"
            r"|xoxb-[0-9a-zA-Z\-]{10,}"
        ),
    ),
    # ── Sensitive data in logs ────────────────────────────────────────────────
    ComplianceCriterion(
        id="security/logging/no-sensitive-data-in-logs",
        guideline_slug="backend/13-owasp-top10",
        stack="security",
        text=(
            "Log statements never interpolate passwords, tokens, secrets, or card numbers — "
            "even at DEBUG level"
        ),
        category="logging",
        severity="required",
        check_type="code_pattern",
        verification_hint=(
            "Paste the logging calls in the auth, payment, and user management modules. "
            "Confirm no sensitive field value is formatted into any log message."
        ),
        forbidden_pattern=(
            r'(?:logger|logging|log)\.\w+\s*\([^)]*'
            r'(?:\{(?:password|passwd|token|secret|api_key|credit_card|cvv)\b'
            r'|,\s*(?:password|passwd|token|secret|api_key|credit_card|cvv)\b'
            r'|%\((?:password|passwd|token|secret|api_key|credit_card|cvv)\))'
        ),
    ),
    ComplianceCriterion(
        id="security/owasp/auth-events-logged",
        guideline_slug="backend/13-owasp-top10",
        stack="security",
        text="Login failures and access denials are logged with structured JSON — no passwords, tokens, or PAN",
        category="logging",
        severity="required",
        check_type="manual",
        verification_hint=(
            "Confirm login_failed and access_denied events are logged (e.g. structlog or logging). "
            "Provide the logger call(s) and confirm no sensitive fields (password, token, card number) are included."
        ),
    ),
]

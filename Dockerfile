# ── Stage 1: build virtualenv ─────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1

RUN pip install poetry --no-cache-dir

COPY pyproject.toml poetry.lock ./

# Install production dependencies only — no test/lint tools
RUN poetry install --only main --no-root

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy the pre-built virtualenv — no pip/poetry needed at runtime
COPY --from=builder /app/.venv ./.venv

# Copy application source and content directories
COPY src/        ./src/
COPY guidelines/ ./guidelines/
COPY examples/   ./examples/

ENV PATH="/app/.venv/bin:$PATH" \
    MCP_TRANSPORT=sse \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

EXPOSE 8000

# Non-root user for security
RUN adduser --disabled-password --gecos "" appuser
USER appuser

CMD ["python", "-m", "src.mcp_main"]

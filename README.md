# Fullstack Guidelines MCP Server

An MCP server that gives AI coding assistants access to curated fullstack architecture guidelines and annotated code examples. Connect it to Claude or Codex and it will read, cite, and apply the right patterns while it writes code.

**Live endpoint:** `https://fullstack-agent-guidelines.vercel.app/mcp`

---

## What's inside

| Category | Guidelines |
|---|---|
| **Backend** | Project structure, domain / application / infrastructure / presentation layers, SOLID, DRY/KISS/YAGNI, security, testing, async patterns, design patterns, OWASP Top 10, database design, tech debt, observability/logging, audit-on-write, error handling & exception hierarchy, API pagination, idempotency, safe Alembic migrations |
| **Frontend** | Project structure, server vs. client components, data fetching, forms & validation, authentication, state management, OWASP Top 10, supply chain, design patterns, loading/error/empty states, accessibility, Server Actions, component testing, performance, Playwright E2E |
| **Infra** | Docker Compose, testing in Docker, OpenTelemetry, Makefile as the gate |
| **Agile** | Vertical slices, definition of done, conventional commits, pull requests |
| **QA** | Code review, E2E-per-feature |
| **Architecture** | Technology selection (dependency adoption checklist) |

### Tools exposed

| Tool | Description |
|---|---|
| `list_guidelines` | List available guidelines; filter by `stack` (`backend` / `frontend`) |
| `get_guideline` | Fetch the full Markdown of a guideline by slug |
| `search_guidelines` | Keyword search across titles, content, and tags |
| `get_all_context` | Concatenate all guidelines into one document for full context injection |
| `list_examples` | List annotated code examples; filter by `stack` and/or `layer` |
| `get_example` | Fetch the full annotated source of a code example by name |
| `get_metadata` | Server metadata (version, available stacks and layers) |
| `health_check` | Liveness check |

---

## Connect to Claude

### Claude.ai (web)

1. Open [claude.ai](https://claude.ai) and go to **Settings → Integrations**.
2. Click **Add integration**.
3. Paste the URL:
   ```
   https://fullstack-agent-guidelines.vercel.app/mcp
   ```
4. Save — the tools appear automatically in any new conversation.

### Claude Code (CLI / VS Code / JetBrains)

Add the server to your project or user config:

```bash
claude mcp add fullstack-guidelines https://fullstack-agent-guidelines.vercel.app/mcp
```

Or add it manually to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "fullstack-guidelines": {
      "type": "http",
      "url": "https://fullstack-agent-guidelines.vercel.app/mcp"
    }
  }
}
```

Restart Claude Code (or run `/mcp` in the chat to reload). The tools are available immediately.

### Claude mobile (iOS / Android)

1. Open the Claude app and tap your profile icon.
2. Go to **Settings → Integrations**.
3. Tap **Add integration** and paste:
   ```
   https://fullstack-agent-guidelines.vercel.app/mcp
   ```
4. Save and start a new conversation — the tools are active.

---

## Connect to Codex

### Codex web (chatgpt.com)

1. Open [chatgpt.com](https://chatgpt.com) and go to **Settings → Connectors** (or **Tools**).
2. Click **Add connector → Custom**.
3. Set the URL:
   ```
   https://fullstack-agent-guidelines.vercel.app/mcp
   ```
4. Confirm — Codex discovers the tools automatically via MCP.

### Codex desktop

1. Open Codex and go to **Preferences → Extensions → MCP Servers**.
2. Click **Add** and enter:
   ```
   https://fullstack-agent-guidelines.vercel.app/mcp
   ```
3. Save and restart if prompted.

---

## Run locally

```bash
# Clone and install
git clone https://github.com/scardoso-lu/fullstack-agent-guidelines.git
cd fullstack-agent-guidelines
pip install -r requirements.txt

# Run with stdio transport (default — for Claude Code local config)
python -m src.mcp_main

# Run as HTTP server
MCP_TRANSPORT=sse MCP_HOST=127.0.0.1 MCP_PORT=8000 python -m src.mcp_main
```

For the local HTTP server, point your client at `http://127.0.0.1:8000/mcp`.

### Docker

```bash
docker build -t fullstack-guidelines .
docker run -p 8000:8000 fullstack-guidelines
```

---

## Deploy your own

The server runs as a single Vercel serverless function.

1. Fork this repo.
2. Import it in [vercel.com](https://vercel.com) — no build settings needed, `vercel.json` handles everything.
3. Update `MCP_BASE_URL` in your Vercel environment variables to your deployment URL.

---

## License

MIT

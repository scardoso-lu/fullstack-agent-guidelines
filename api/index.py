import sys
from pathlib import Path

# Ensure repo root is on sys.path when running from the api/ subdirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mcp_main import mcp  # noqa: E402

# Vercel detects and serves this ASGI app.
# MCP streamable-HTTP endpoint: POST /mcp  (and GET /mcp for SSE stream)
app = mcp.streamable_http_app()

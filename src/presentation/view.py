from mcp.server.fastmcp import FastMCP

from src.presentation.tools.health import register_health_tools
from src.presentation.tools.note import register_note_tools


def register_mcp_tools(mcp: FastMCP) -> None:
    register_health_tools(mcp)
    register_note_tools(mcp)

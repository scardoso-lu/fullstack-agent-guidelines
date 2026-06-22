from mcp.server.fastmcp import FastMCP

from src.presentation.resources.guideline import register_guideline_resources
from src.presentation.tools.compliance import register_compliance_tools
from src.presentation.tools.example import register_example_tools
from src.presentation.tools.guideline import register_guideline_tools
from src.presentation.tools.health import register_health_tools
from src.presentation.tools.metadata import register_metadata_tools


def register_mcp_tools(mcp: FastMCP) -> None:
    register_health_tools(mcp)
    register_metadata_tools(mcp)
    register_guideline_tools(mcp)
    register_guideline_resources(mcp)
    register_example_tools(mcp)
    register_compliance_tools(mcp)

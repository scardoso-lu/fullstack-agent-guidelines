from mcp.server.fastmcp import FastMCP

from src.application.use_cases.structure.validate import ValidateProjectStructureUseCase
from src.utils.logger import get_logger

_logger = get_logger("tools.structure")


def register_structure_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="validate_project_structure",
        description=(
            "Check whether the project's folder layout and module placement follow the fullstack "
            "engineering guidelines. Unlike verify_compliance() which validates code content, this "
            "tool validates file paths — detecting misplaced files such as repositories outside "
            "infrastructure/repositories/, DTOs outside application/dto/, PascalCase Python "
            "filenames, provider components outside providers/, and more.\n\n"
            "How to use:\n"
            "  Backend:  find src/ -type f -name '*.py'\n"
            "  Frontend: find src/ -type f \\( -name '*.ts' -o -name '*.tsx' \\)\n"
            "  Both:     run both commands, concatenate output, set stack='both'\n\n"
            "Parameters:\n"
            "  stack     — 'backend' | 'frontend' | 'both'\n"
            "  file_tree — raw output of the find command above (one path per line)\n\n"
            "Returns per-file violations with rule_id, severity ('required'|'recommended'), "
            "file_path, message, and a hint on how to fix it. "
            "Overall status is 'compliant', 'warnings' (recommended only), "
            "or 'non-compliant' (at least one required rule broken)."
        ),
    )
    async def validate_project_structure(stack: str, file_tree: str) -> dict:
        _logger.info("tool=validate_project_structure stack=%r", stack)
        try:
            result = await ValidateProjectStructureUseCase().execute(stack, file_tree)
            data = result.model_dump()
            _logger.info(
                "tool=validate_project_structure stack=%r files=%d violations=%d status=%r",
                stack,
                data["total_files"],
                len(data["violations"]),
                data["status"],
            )
            return data
        except ValueError as exc:
            _logger.warning("tool=validate_project_structure stack=%r error=%r", stack, str(exc))
            return {"error": str(exc)}

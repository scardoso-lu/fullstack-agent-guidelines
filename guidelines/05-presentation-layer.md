# Presentation Layer: MCP Tools and Routes

The presentation layer is the thinnest layer. It translates between the external protocol (HTTP, MCP) and the application layer. It contains zero business logic — only wiring.

## The Thin Layer Rule

If a tool or route handler exceeds ~10 lines, something that belongs in a use case has leaked into the presentation layer.

**Correct pattern — 4 lines of wiring:**

```python
@mcp.tool(name="create_note", description="Create a new note.")
async def create_note(title: str, content: str = "") -> dict:
    async with get_session() as session:
        use_case = CreateNoteUseCase(NoteRepository(session))
        note = await use_case.execute(CreateNoteDto(title=title, content=content))
        return note.model_dump()
```

The tool handler does exactly three things:
1. Sets up the dependency (session + repository)
2. Instantiates and calls the use case
3. Serializes the result

## The `register_*` Pattern

Tools and resources are grouped in registration functions — not declared at module level. This keeps `mcp_main.py` clean and makes the wiring explicit:

```python
# src/presentation/view.py
def register_mcp_tools(mcp: FastMCP) -> None:
    register_health_tools(mcp)
    register_guideline_tools(mcp)
    register_guideline_resources(mcp)
```

```python
# src/presentation/tools/guideline.py
def register_guideline_tools(mcp: FastMCP) -> None:
    @mcp.tool(name="list_guidelines", description="...")
    async def list_guidelines() -> dict: ...

    @mcp.tool(name="get_guideline", description="...")
    async def get_guideline(slug: str) -> dict: ...
```

This mirrors the FastAPI router pattern (`app.include_router(note_router, ...)`) from mdip-backend:

```python
# src/presentation/view.py (mdip-backend)
def register_api_routes(app: FastAPI):
    app.include_router(health_router, ...)
    app.include_router(auth_router, tags=["Authentication"], prefix=C.URL_PREFIX)
    app.include_router(note_router, tags=["Note"], prefix=C.URL_PREFIX)
```

## MCP Tools vs MCP Resources

| Concept | Use for | Returns | Example URI |
|---|---|---|---|
| `@mcp.tool()` | Actions and queries | `dict` or `str` | Called as function |
| `@mcp.resource()` | Content by identifier | `str` (markdown/text) | `guidelines://08-security` |

Tools are invoked explicitly by the agent. Resources can be referenced by URI in prompts:

```python
# src/presentation/resources/guideline.py
def register_guideline_resources(mcp: FastMCP) -> None:
    @mcp.resource("guidelines://{slug}")
    async def guideline_resource(slug: str) -> str:
        use_case = GetGuidelineBySlugUseCase(get_guideline_repository())
        try:
            result = await use_case.execute(slug)
            return result.content
        except NotFoundError:
            return f"Guideline '{slug}' not found."
```

## FastAPI Route Pattern (from mdip-backend)

```python
# src/presentation/routes/authentication.py
@auth_router.post("/login", response_model=AuthSuccessDto)
async def login(data: AuthDto, session: Annotated[AsyncSession, Depends(get_session)]):
    user_repository = IUserRepository(session)
    access_token_service = IAccessTokenService(get_config().JWT_SECRET)
    refresh_token_service = IRefreshTokenService(get_config().JWT_SECRET)
    login_use_case = UserLoginUseCase(
        user_repository, access_token_service, refresh_token_service
    )
    return await login_use_case.execute(AuthDto(username=data.username, password=data.password))
    except UnauthorizedAccessError as e:
        return e.as_response(status_code=status.HTTP_401_UNAUTHORIZED)
```

Key observations:
- `response_model=AuthSuccessDto` declares the return shape for docs and validation
- `Depends(get_session)` wires the DB session via FastAPI DI
- `IUserRepository` is the interface from `contract.py` — not the concrete `UserRepository`
- Exception mapping happens here (domain error → HTTP status)

## Error Handling in Tools

Catch domain errors in the tool handler and return structured dicts — never raise from a tool:

```python
@mcp.tool(name="delete_note", description="Delete a note by ID.")
async def delete_note(note_id: str) -> dict:
    async with get_session() as session:
        try:
            use_case = DeleteNoteUseCase(NoteRepository(session))
            await use_case.execute(int(note_id))
            return {"deleted": True, "note_id": note_id}
        except NotFoundError as exc:
            return {"deleted": False, "error": str(exc)}
```

## Server Factory (mcp_main.py)

```python
# src/mcp_main.py
def create_mcp_server() -> FastMCP:
    """MCP server factory — mirrors api_main.py from FastAPI projects."""
    config = get_config()
    server = FastMCP(name=C.TITLE, version=C.PROJECT_VERSION)
    server.settings.host = config.MCP_HOST
    server.settings.port = config.MCP_PORT
    register_mcp_tools(server)
    return server

mcp = create_mcp_server()

if __name__ == "__main__":
    mcp.run(transport=get_config().MCP_TRANSPORT)
```

The factory function makes it easy to create test instances and swap configuration.

## Quick Checklist

- [ ] Tool/route handlers are ≤ 10 lines
- [ ] No business logic, validation, or SQL in tool handlers
- [ ] Domain errors are caught and mapped to return values (MCP) or HTTP status (FastAPI)
- [ ] `response_model` is declared on FastAPI routes for documentation and validation
- [ ] Tools return `dict` or `str`, not Pydantic models or SQLAlchemy entities directly
- [ ] `register_*` functions group related tools — no module-level `@mcp.tool` decorators

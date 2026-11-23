from fastapi import HTTPException
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from sqlmodel import Session, col, select

from app.api.routes import deep_dive_list, repo_deep_dives, repos
from app.api.routes.deep_dives import get_html_reader
from app.config import engine
from app.deep_dive.page_text import page_text
from app.models import DeepDive, DeepDiveListItem, DeepDiveRead, RepoRead

from .repo_outline import repo_outline

# Read-only on purpose: the endpoint has no auth, like the REST read routes, and generating costs LLM money.
# The tools call the route functions, so the two surfaces can't drift; docstrings are what the agent is shown.
server = MCPServer(
    "deep-diver",
    instructions=(
        "Maps of indexed repos and written deep dives about their code areas. Start with list_repos, then get_map "
        "for a repo's areas; read_deep_dive returns the page for any deep dive id the map or list_deep_dives shows."
    ),
)


@server.tool()
def list_repos() -> list[RepoRead]:
    """Every indexed repo with its id, URL and the commit its map was built from."""
    with Session(engine) as session:
        return repos.list_repos(session)


@server.tool()
def get_map(repo_id: int) -> str:
    """A repo's code areas as an indented outline: each area's name, node id, files or folders, description, and
    its deep dive id when one is written. The first line is the whole-repo deep dive."""
    with Session(engine) as session:
        try:
            repo_map = repos.get_map(repo_id, session)
        except HTTPException as e:
            # The route's 404. As a ToolError its message reaches the agent; anything else reads "internal error".
            raise ToolError(str(e.detail)) from e
        root = repo_deep_dives.find_root_deep_dive(session, repo_id)
        # Served by the unique constraint on deep_dives.node_id.
        dives = session.exec(
            select(DeepDive).where(col(DeepDive.node_id).in_([node.id for node in repo_map.nodes]))
        ).all()
        pages = {dive.node_id: dive.id for dive in map(DeepDiveRead.model_validate, [*dives, *([root] if root else [])])}
    return repo_outline(repo_map, pages)


@server.tool()
def list_deep_dives() -> list[DeepDiveListItem]:
    """Every written deep dive of every repo, newest first, with its area name (null: the whole repo) and repo URL.
    `stale` marks a page written from an older commit than the repo's current map; get_map no longer shows those."""
    with Session(engine) as session:
        return deep_dive_list.list_deep_dives(session)


@server.tool()
def read_deep_dive(deep_dive_id: int) -> str:
    """A deep dive page as plain text: headings, prose, captions and code excerpts, without markup or diagrams."""
    with Session(engine) as session:
        row = session.get(DeepDive, deep_dive_id)
    if row is None:
        raise ToolError("deep dive not found")
    return page_text(get_html_reader()(row.object_key))

"""
Reads and updates the tasks of a project in the Plane tracker, through the Plane MCP server.

Tasks for this repository are kept in a Plane project. A session that has the MCP server's tools uses them; this
is the same server driven from a script, for a session that does not (one started before the server was added,
or a sub-agent), and for doing several updates at once. It starts the server exactly as ~/.claude.json defines
it, so the key stays there.

    uvx --from plane-mcp-server python claude/tools/tracker.py list --project PLANE --state Todo
    uvx --from plane-mcp-server python claude/tools/tracker.py show --project PLANE --number 7
    uvx --from plane-mcp-server python claude/tools/tracker.py apply --project PLANE changes.json

changes.json is a list of {"number": 7, "state": "Review", "comment_html": "<p>...</p>"}; state and comment_html
are each optional.
"""

import abc
import argparse
import asyncio
import dataclasses as dc
import html
import json
import pathlib as pl
import re
import sys
import typing as t

import fastmcp
import fastmcp.client.transports as transports

JSONObject: t.TypeAlias = t.Dict[str, t.Any]


async def call(client: fastmcp.Client, tool: str, **arguments: t.Any) -> t.Any:
    content: t.Any = (await client.call_tool(tool, arguments)).structured_content
    return (
        content["result"]
        if isinstance(content, dict) and "result" in content
        else content
    )


async def find_project(client: fastmcp.Client, identifier: str) -> JSONObject:
    projects: t.List[JSONObject] = (await call(client, "project", action="list"))[
        "results"
    ]
    project: JSONObject
    for project in projects:
        if project["identifier"] == identifier:
            return project
    raise SystemExit(
        f"No project {identifier}; there are: {sorted(p['identifier'] for p in projects)}"
    )


async def list_states(client: fastmcp.Client, project_id: str) -> t.Dict[str, str]:
    states: t.List[JSONObject] = (
        await call(client, "state", action="list", project_id=project_id)
    )["results"]
    return {state["name"]: state["id"] for state in states}


async def list_work_items(
    client: fastmcp.Client, project_id: str
) -> t.List[JSONObject]:
    listed: JSONObject = await call(
        client, "workitem", action="list", project_id=project_id, per_page=100
    )
    return sorted(listed["results"], key=lambda item: item["sequence_id"])


def get_text_of_html(text: str) -> str:
    text = re.sub(r"</(p|li|h[1-6]|pre|blockquote|tr)>|<br\s*/?>", "\n", text)
    text = re.sub(r"<li[^>]*>", "- ", text)
    return re.sub(
        r"\n{3,}", "\n\n", html.unescape(re.sub(r"<[^>]+>", "", text))
    ).strip()


class Command(abc.ABC):
    @abc.abstractmethod
    async def run(self, client: fastmcp.Client) -> None: ...


@dc.dataclass(frozen=True)
class ListTasks(Command):
    project: str
    state: t.Optional[str]

    async def run(self, client: fastmcp.Client) -> None:
        project_id: str = (await find_project(client, self.project))["id"]
        state_names: t.Dict[str, str] = {
            state_id: name
            for name, state_id in (await list_states(client, project_id)).items()
        }
        item: JSONObject
        for item in await list_work_items(client, project_id):
            state: str = state_names[item["state"]]
            if self.state is None or state == self.state:
                print(f"{self.project}-{item['sequence_id']} [{state}] {item['name']}")


@dc.dataclass(frozen=True)
class ShowTask(Command):
    project: str
    number: int

    async def run(self, client: fastmcp.Client) -> None:
        project_id: str = (await find_project(client, self.project))["id"]
        listed: t.List[JSONObject] = [
            item
            for item in await list_work_items(client, project_id)
            if item["sequence_id"] == self.number
        ]
        if not listed:
            raise SystemExit(f"No task {self.project}-{self.number}")
        item: JSONObject = await call(
            client,
            "workitem",
            action="retrieve",
            project_id=project_id,
            workitem_id=listed[0]["id"],
        )
        comments: JSONObject = await call(
            client,
            "workitem_comment",
            action="list",
            project_id=project_id,
            workitem_id=item["id"],
        )
        print(f"{self.project}-{self.number}: {item['name']}\n")
        print(get_text_of_html(item.get("description_html") or ""))
        comment: JSONObject
        for comment in comments["results"]:
            print(
                f"\n--- comment of {comment['created_at']}\n{get_text_of_html(comment.get('comment_html') or '')}"
            )


@dc.dataclass(frozen=True)
class ApplyChanges(Command):
    project: str
    changes: pl.Path

    async def run(self, client: fastmcp.Client) -> None:
        project_id: str = (await find_project(client, self.project))["id"]
        states: t.Dict[str, str] = await list_states(client, project_id)
        items: t.Dict[int, JSONObject] = {
            item["sequence_id"]: item
            for item in await list_work_items(client, project_id)
        }
        change: JSONObject
        for change in json.loads(self.changes.read_text()):
            item: JSONObject = items[change["number"]]
            if change.get("comment_html"):
                await call(
                    client,
                    "workitem_comment",
                    action="create",
                    project_id=project_id,
                    workitem_id=item["id"],
                    comment_html=change["comment_html"],
                )
            if change.get("state"):
                await call(
                    client,
                    "workitem",
                    action="update",
                    project_id=project_id,
                    workitem_id=item["id"],
                    state=states[change["state"]],
                )
            print(
                f"{self.project}-{change['number']}: state: {change.get('state')}, comment: {bool(change.get('comment_html'))}"
            )


async def run_with_server(command: Command, claude_config: pl.Path) -> None:
    server: JSONObject = json.loads(claude_config.read_text())["mcpServers"]["plane"]
    transport: transports.StdioTransport = transports.StdioTransport(
        command=server["command"], args=server["args"], env=server["env"]
    )
    async with fastmcp.Client(transport) as client:
        await command.run(client)


def parse_arguments(arguments: t.List[str]) -> t.Tuple[Command, pl.Path]:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--claude-config",
        type=pl.Path,
        default=pl.Path.home() / ".claude.json",
        help="file whose mcpServers.plane entry defines the server",
    )
    subparsers: t.Any = parser.add_subparsers(dest="command", required=True)
    list_parser: argparse.ArgumentParser = subparsers.add_parser(
        "list", help="the tasks of a project, one a line"
    )
    list_parser.add_argument(
        "--project", required=True, help="identifier of the project, such as PLANE"
    )
    list_parser.add_argument("--state", help="only the tasks in this state")
    show_parser: argparse.ArgumentParser = subparsers.add_parser(
        "show", help="a task's description and comments"
    )
    show_parser.add_argument("--project", required=True)
    show_parser.add_argument("--number", type=int, required=True)
    apply_parser: argparse.ArgumentParser = subparsers.add_parser(
        "apply", help="set states and add comments"
    )
    apply_parser.add_argument("--project", required=True)
    apply_parser.add_argument("changes", type=pl.Path)
    parsed: argparse.Namespace = parser.parse_args(arguments)
    commands: t.Dict[str, t.Callable[[], Command]] = {
        "list": lambda: ListTasks(parsed.project, parsed.state),
        "show": lambda: ShowTask(parsed.project, parsed.number),
        "apply": lambda: ApplyChanges(parsed.project, parsed.changes),
    }
    return commands[parsed.command](), parsed.claude_config


if __name__ == "__main__":
    asyncio.run(run_with_server(*parse_arguments(sys.argv[1:])))

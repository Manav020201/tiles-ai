"""Unit tests for the app-pack tile handlers (GitHub, Slack, Web Search).

These exercise handler *logic* — tool-call arg construction, the propose→gate
flow for draft tiles, input parsing, and graceful degradation on tool errors —
against fake tool/model contexts. They do NOT hit a real MCP server (that still
needs a token); they pin down everything up to the wire.
"""

import asyncio
from pathlib import Path

from tiles_ai.contracts import RunContext, ToolResult
from tiles_ai.registry import Registry

REPO_ROOT = Path(__file__).resolve().parents[1]
_REG = Registry.discover(REPO_ROOT)


class FakeTools:
    """Records tool calls; returns canned ToolResults (ok by default)."""

    def __init__(self, responses: dict | None = None):
        self.responses = responses or {}
        self.calls: list[tuple[str, dict]] = []

    async def call(self, name: str, args: dict | None = None) -> ToolResult:
        self.calls.append((name, args or {}))
        return self.responses.get(name, ToolResult(ok=True, output=f"output:{name}"))


class FakeModel:
    def __init__(self, reply: str = "MODEL_REPLY"):
        self.reply = reply

    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        return self.reply


def run_tile(tile_id: str, input, *, tools: FakeTools | None = None):
    loaded = _REG.tiles[tile_id]
    tools = tools or FakeTools()
    handler = loaded.handler_cls(loaded.manifest)
    ctx = RunContext(manifest=loaded.manifest, tools=tools, model=FakeModel())
    plan = asyncio.run(handler.run(input, ctx))
    return plan, tools


# --- GitHub --------------------------------------------------------------


def test_github_triage_lists_and_summarizes():
    plan, tools = run_tile("github-triage", "octocat/hello")
    assert ("list_issues", {"owner": "octocat", "repo": "hello", "state": "open"}) in tools.calls
    assert plan.result == "MODEL_REPLY"
    assert plan.actions == []  # read_only, nothing proposed


def test_github_triage_rejects_bad_repo():
    plan, _ = run_tile("github-triage", "no-slash")
    assert "owner/repo" in plan.result


def test_github_triage_degrades_on_tool_error():
    tools = FakeTools({"list_issues": ToolResult(ok=False, error="boom", side_effect=False)})
    plan, _ = run_tile("github-triage", "o/r", tools=tools)
    assert "boom" in plan.result


def test_github_comment_proposes_with_parsed_args():
    plan, tools = run_tile("github-comment", "octocat/hello#7: please fix the typo")
    assert any(c[0] == "get_issue" for c in tools.calls)
    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.tool == "add_issue_comment"
    assert action.side_effect is True
    assert action.args == {
        "owner": "octocat",
        "repo": "hello",
        "issue_number": 7,
        "body": "MODEL_REPLY",
    }


def test_github_comment_rejects_bad_ref():
    plan, _ = run_tile("github-comment", "just text")
    assert "owner/repo#issue" in plan.result
    assert plan.actions == []


# --- Slack ---------------------------------------------------------------


def test_slack_catchup_reads_channel_history():
    plan, tools = run_tile("slack-catchup", "#eng")
    assert ("slack_get_channel_history", {"channel_id": "eng", "limit": 50}) in tools.calls
    assert plan.result == "MODEL_REPLY"
    assert plan.actions == []


def test_slack_drafter_proposes_post():
    plan, tools = run_tile("slack-drafter", "#eng: ship it")
    assert any(c[0] == "slack_get_channel_history" for c in tools.calls)
    action = plan.actions[0]
    assert action.tool == "slack_post_message"
    assert action.side_effect is True
    assert action.args == {"channel_id": "eng", "text": "MODEL_REPLY"}


# --- Web search ----------------------------------------------------------


def test_web_search_digests_results():
    plan, tools = run_tile("web-search", "python asyncio")
    assert ("brave_web_search", {"query": "python asyncio", "count": 8}) in tools.calls
    assert plan.result == "MODEL_REPLY"


def test_research_answers_with_sources():
    plan, tools = run_tile("research", "what is mcp")
    assert any(c[0] == "brave_web_search" for c in tools.calls)
    assert plan.result == "MODEL_REPLY"
    assert plan.actions == []


# --- Local files (zero-credential "smart PC") ----------------------------


def test_summarize_folder_reads_and_summarizes():
    tools = FakeTools(
        {
            "list_dir": ToolResult(ok=True, output="a.txt\nb.md"),
            "read_file": ToolResult(ok=True, output="contents"),
        }
    )
    plan, _ = run_tile("summarize-folder", ".", tools=tools)
    assert plan.result == "MODEL_REPLY"
    assert any(c[0] == "read_file" for c in tools.calls)


def test_find_files_returns_matches_without_the_model():
    tools = FakeTools({"find_files": ToolResult(ok=True, output="notes/todo.txt")})
    plan, _ = run_tile("find-files", "todo", tools=tools)
    assert plan.result == "notes/todo.txt"


def test_find_files_rejects_empty_query():
    plan, _ = run_tile("find-files", "")
    assert "keyword" in plan.result


def test_tidy_folder_proposes_moves_grouped_by_type():
    tools = FakeTools({"list_dir": ToolResult(ok=True, output="report.pdf\nphoto.png\nnotes")})
    plan, _ = run_tile("tidy-folder", ".", tools=tools)
    assert len(plan.actions) == 3
    for action in plan.actions:
        assert action.tool == "move_file" and action.side_effect is True
    assert any(a.args["dst"] == "pdf/report.pdf" for a in plan.actions)
    assert any(a.args["dst"] == "other/notes" for a in plan.actions)  # no extension


def test_tidy_folder_nothing_to_do():
    tools = FakeTools({"list_dir": ToolResult(ok=True, output="(empty)")})
    plan, _ = run_tile("tidy-folder", ".", tools=tools)
    assert plan.actions == []
    assert "Nothing to tidy" in plan.result

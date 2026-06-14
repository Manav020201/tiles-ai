"""GitHub Triage — read open issues for a repo and prioritize them.

Input is "owner/repo". Reads through ctx.tools (allow-listed, read-only) and
degrades gracefully if a call fails, so a slightly different server version
surfaces a clear message rather than crashing.
"""

from __future__ import annotations

from tiles_ai.contracts import ActionPlan, Tile


class GithubTriage(Tile):
    async def run(self, input, context) -> ActionPlan:
        owner, repo = _split_repo(input)
        if not owner:
            return ActionPlan(result="Enter a repo as 'owner/repo'.")

        issues = await context.tools.call(
            "list_issues", {"owner": owner, "repo": repo, "state": "open"}
        )
        if not issues.ok:
            return ActionPlan(result=f"Couldn't list issues for {owner}/{repo}: {issues.error}")

        digest = await context.model.complete(
            f"Triage the open issues for {owner}/{repo}:\n{issues.output}",
            system=context.manifest.instructions,
        )
        return ActionPlan(result=digest)


def _split_repo(value) -> tuple[str, str]:
    text = str(value or "").strip()
    if "/" not in text:
        return "", ""
    owner, _, repo = text.partition("/")
    return owner.strip(), repo.strip()

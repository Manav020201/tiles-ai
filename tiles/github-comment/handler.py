"""GitHub Comment — draft an issue comment and propose posting it.

Input: "owner/repo#123: what to say". Reads the issue for context, drafts a
comment with the brain, then PROPOSES add_issue_comment (side_effect=True). Under
the draft tier the gate queues it for approval — nothing posts on its own.
"""

from __future__ import annotations

from tiles_ai.contracts import ActionPlan, ProposedAction, Tile


class GithubComment(Tile):
    async def run(self, input, context) -> ActionPlan:
        ref, _, intent = str(input or "").partition(":")
        owner, repo, number = _parse_ref(ref)
        if not owner:
            return ActionPlan(result="Enter a target as 'owner/repo#issue: your intent'.")

        issue = await context.tools.call(
            "get_issue", {"owner": owner, "repo": repo, "issue_number": number}
        )
        context_text = issue.output if issue.ok else "(issue could not be fetched)"

        body = await context.model.complete(
            f"Intent: {intent.strip() or 'a helpful reply'}\nIssue:\n{context_text}",
            system=context.manifest.instructions,
        )

        propose = ProposedAction(
            tool="add_issue_comment",
            args={"owner": owner, "repo": repo, "issue_number": number, "body": body},
            side_effect=True,
            summary=f"Comment on {owner}/{repo}#{number}",
        )
        return ActionPlan(result={"draft": body, "target": f"{owner}/{repo}#{number}"}, actions=[propose])


def _parse_ref(ref) -> tuple[str, str, int]:
    text = str(ref or "").strip()
    if "/" not in text or "#" not in text:
        return "", "", 0
    owner, _, rest = text.partition("/")
    repo, _, num = rest.partition("#")
    try:
        return owner.strip(), repo.strip(), int(num)
    except ValueError:
        return "", "", 0

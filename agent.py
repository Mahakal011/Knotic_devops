"""
Agent loop using Gemini 2.0 Flash via the google-genai SDK.
"""

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

import tools

load_dotenv()

MODEL_NAME = "gemini-2.0-flash"
BUG_KEYWORDS = ("bug", "fix", "hotfix", "revert", "crash", "error", "fail")

SYSTEM = """You are a release engineering agent.

Your job, in order:
1. Read the recent commits from GitHub.
2. For any commit that looks like an unresolved bug, a revert, or a hotfix,
   file a Jira issue describing it. Do not file duplicates.
3. Trigger a Netlify deployment.
4. Write a release report to Notion containing: a one-paragraph summary, a
   bulleted list of changes grouped by type (features, fixes, chores), the
   Jira issues you filed, and the deploy status.

Be decisive. Call the tools yourself rather than asking permission."""

TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_commits",
        description="Read recent commits from the GitHub repository.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "limit": types.Schema(
                    type=types.Type.INTEGER,
                    description="How many commits to fetch",
                )
            },
        ),
    ),
    types.FunctionDeclaration(
        name="create_jira_issue",
        description="File a Jira issue for a bug or task found in the commit history.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "summary": types.Schema(
                    type=types.Type.STRING,
                    description="Short issue title",
                ),
                "description": types.Schema(
                    type=types.Type.STRING,
                    description="What the issue is and why it matters",
                ),
            },
            required=["summary", "description"],
        ),
    ),
    types.FunctionDeclaration(
        name="trigger_deploy",
        description="Trigger a Netlify production deployment.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "reason": types.Schema(
                    type=types.Type.STRING,
                    description="Why this deploy is happening",
                )
            },
        ),
    ),
    types.FunctionDeclaration(
        name="write_notion_report",
        description="Write the final release report as a Notion page.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "title": types.Schema(type=types.Type.STRING),
                "markdown_body": types.Schema(
                    type=types.Type.STRING,
                    description="Full report text",
                ),
            },
            required=["title", "markdown_body"],
        ),
    ),
]

DISPATCH = {
    "get_commits": tools.get_commits,
    "create_jira_issue": tools.create_jira_issue,
    "trigger_deploy": tools.trigger_deploy,
    "write_notion_report": tools.write_notion_report,
}


def _client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def _text_from_parts(parts):
    return "".join(part.text for part in parts if getattr(part, "text", None))


def _friendly_model_error(exc):
    text = str(exc)
    if "RESOURCE_EXHAUSTED" in text or "429" in text:
        return (
            "Gemini quota is exhausted for this API key/model. "
            "The app will continue with the deterministic Track 3 fallback."
        )
    return f"Gemini call failed: {exc}"


def _emit(on_event, kind, payload):
    if on_event:
        on_event(kind, payload)


def _call_tool(name, args, on_event=None):
    _emit(on_event, "tool_call", {"name": name, "input": args})
    try:
        output = DISPATCH[name](**args)
    except Exception as exc:
        output = {"error": str(exc)}
    _emit(on_event, "tool_result", {"name": name, "output": output})
    return output


def _looks_like_bug(commit):
    message = commit.get("message", "").lower()
    return any(keyword in message for keyword in BUG_KEYWORDS)


def _group_commits(commits):
    groups = {"features": [], "fixes": [], "chores": []}
    for commit in commits:
        message = commit.get("message", "")
        lower = message.lower()
        if _looks_like_bug(commit):
            groups["fixes"].append(message)
        elif lower.startswith(("feat", "feature", "add")):
            groups["features"].append(message)
        else:
            groups["chores"].append(message)
    return groups


def _format_report(commits, jira_issues, deploy_result, reason):
    groups = _group_commits(commits)
    issue_lines = [
        issue.get("key") or issue.get("status") or issue.get("error") or str(issue)
        for issue in jira_issues
    ]
    deploy_status = deploy_result.get("status") or deploy_result.get("error") or str(deploy_result)

    lines = [
        "Release Pipeline Report",
        "",
        f"Summary: Processed {len(commits)} recent commits for request: {reason}",
        "",
        "Features:",
    ]
    lines.extend([f"- {item}" for item in groups["features"]] or ["- None"])
    lines.extend(["", "Fixes:"])
    lines.extend([f"- {item}" for item in groups["fixes"]] or ["- None"])
    lines.extend(["", "Chores:"])
    lines.extend([f"- {item}" for item in groups["chores"]] or ["- None"])
    lines.extend(["", "Jira issues filed:"])
    lines.extend([f"- {item}" for item in issue_lines] or ["- None"])
    lines.extend(["", f"Deploy status: {deploy_status}"])
    return "\n".join(lines)


def _fallback_pipeline(user_request, on_event=None, reason=None):
    _emit(
        on_event,
        "thought",
        reason
        or "Gemini is unavailable, so I am running the release pipeline with deterministic rules.",
    )

    commits = _call_tool("get_commits", {"limit": 10}, on_event)
    if isinstance(commits, dict) and "error" in commits:
        final = f"Could not read commits: {commits['error']}"
        _emit(on_event, "done", final)
        return final

    jira_issues = []
    for commit in commits:
        if _looks_like_bug(commit):
            issue = _call_tool(
                "create_jira_issue",
                {
                    "summary": f"Review release risk: {commit['message']}"[:250],
                    "description": (
                        f"Commit {commit['sha']} by {commit['author']} looks like a "
                        f"bug, revert, or hotfix and should be reviewed before release.\n\n"
                        f"Message: {commit['message']}"
                    ),
                },
                on_event,
            )
            jira_issues.append(issue)

    deploy_result = _call_tool(
        "trigger_deploy",
        {"reason": "Release pipeline run from Track 3 DevOps agent"},
        on_event,
    )
    report = _format_report(commits, jira_issues, deploy_result, user_request)
    notion_result = _call_tool(
        "write_notion_report",
        {"title": "Release Pipeline Report", "markdown_body": report},
        on_event,
    )

    final = report
    if isinstance(notion_result, dict) and notion_result.get("page_url"):
        final = f"{report}\n\nNotion page: {notion_result['page_url']}"
    elif isinstance(notion_result, dict) and notion_result.get("error"):
        final = f"{report}\n\nNotion report failed: {notion_result['error']}"

    _emit(on_event, "done", final)
    return final


def run(user_request="Run the release pipeline for the latest commits.", on_event=None):
    """Run the agent. on_event(kind, payload) lets a UI show live progress."""
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM,
        tools=[types.Tool(function_declarations=TOOL_DECLARATIONS)],
    )
    messages = [types.Content(role="user", parts=[types.Part(text=user_request)])]
    client = _client()

    for _ in range(12):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=messages,
                config=config,
            )
        except Exception as exc:
            return _fallback_pipeline(
                user_request,
                on_event,
                reason=_friendly_model_error(exc),
            )

        if not response.candidates:
            raise RuntimeError("Gemini returned no candidates")

        candidate = response.candidates[0]
        parts = candidate.content.parts or []
        messages.append(types.Content(role="model", parts=parts))

        for part in parts:
            if getattr(part, "text", None) and part.text.strip():
                _emit(on_event, "thought", part.text)

        fn_calls = [part.function_call for part in parts if part.function_call]
        if not fn_calls:
            final = _text_from_parts(parts)
            _emit(on_event, "done", final)
            return final

        result_parts = []
        for fc in fn_calls:
            name = fc.name
            args = dict(fc.args or {})

            output = _call_tool(name, args, on_event)

            result_parts.append(
                types.Part.from_function_response(
                    name=name,
                    response={"result": output},
                )
            )

        messages.append(types.Content(role="user", parts=result_parts))

    return "Stopped after 12 turns."


if __name__ == "__main__":
    run(on_event=lambda kind, payload: print(f"[{kind}] {payload}"))

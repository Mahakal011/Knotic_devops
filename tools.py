"""
Four API functions. Nothing here is DevOps - it's all HTTP requests.

Every outbound call goes through call() below. That is deliberate: when you get
the Swytchcode CLI/SDK syntax at the venue, you change ONE function and the
whole agent routes through Swytchcode. Judges score that at 30%.
"""

import os
import base64
import json
import subprocess
import requests
from dotenv import load_dotenv

load_dotenv()

USE_SWYTCHCODE = os.getenv("USE_SWYTCHCODE", "false").lower() == "true"


def call(method, url, headers=None, json_body=None, integration=None):
    """Single choke point for every outbound API call.

    Direct mode (default): plain requests. Use this to get working first.
    Swytchcode mode: routes through the CLI so you get auth, retries and
    schema validation handled for you.

    Swap the subprocess line below for the exact command shown in the
    Swytchcode docs at the venue. Check `swytchcode --help` for flags.
    """
    if USE_SWYTCHCODE and integration:
        payload = {"method": method, "url": url, "body": json_body or {}}
        result = subprocess.run(
            ["swytchcode", "exec", integration, "--input", json.dumps(payload)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"swytchcode failed: {result.stderr}")
        return json.loads(result.stdout)

    resp = requests.request(
        method, url, headers=headers, json=json_body, timeout=30
    )
    resp.raise_for_status()
    return resp.json() if resp.text else {"ok": True}


# ---------------------------------------------------------------- GitHub

def get_commits(repo=None, limit=10):
    """Read recent commits from a GitHub repo."""
    repo = repo or os.getenv("GITHUB_REPO")  # e.g. "yourname/demo-repo"
    headers = {
        "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github+json",
    }
    data = call(
        "GET",
        f"https://api.github.com/repos/{repo}/commits?per_page={limit}",
        headers=headers,
        integration="github",
    )
    return [
        {
            "sha": c["sha"][:7],
            "message": c["commit"]["message"].split("\n")[0],
            "author": c["commit"]["author"]["name"],
            "date": c["commit"]["author"]["date"],
        }
        for c in data
    ]


# ------------------------------------------------------------------ Jira

def create_jira_issue(summary, description, issue_type="Task"):
    """File a Jira issue. Returns the issue key, e.g. DEMO-14."""
    if not os.getenv("JIRA_TOKEN") or not os.getenv("JIRA_PROJECT_KEY"):
        return {"status": "skipped (Jira not configured)", "summary": summary}

    email = os.getenv("JIRA_EMAIL")
    token = os.getenv("JIRA_TOKEN")
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()

    body = {
        "fields": {
            "project": {"key": os.getenv("JIRA_PROJECT_KEY")},
            "summary": summary[:250],
            "issuetype": {"name": issue_type},
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            },
        }
    }
    data = call(
        "POST",
        f"https://{os.getenv('JIRA_DOMAIN')}/rest/api/3/issue",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
        },
        json_body=body,
        integration="jira",
    )
    return {"key": data.get("key"), "url": f"https://{os.getenv('JIRA_DOMAIN')}/browse/{data.get('key')}"}


# --------------------------------------------------------------- Netlify

def trigger_deploy(reason="Triggered by AI DevOps agent"):
    """Fire a Netlify build hook. This is the entire deployment."""
    hook = os.getenv("NETLIFY_BUILD_HOOK")
    if not hook:
        return {"status": "skipped (no build hook configured)", "reason": reason}
    resp = requests.post(hook, json={"trigger_title": reason}, timeout=30)
    resp.raise_for_status()
    return {"status": "deploy triggered", "code": resp.status_code, "reason": reason}


# ---------------------------------------------------------------- Notion

def write_notion_report(title, markdown_body):
    """Create a Notion page under your parent page."""
    lines = [ln for ln in markdown_body.split("\n") if ln.strip()][:90]
    children = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": ln[:1900]}}]
            },
        }
        for ln in lines
    ]

    body = {
        "parent": {"page_id": os.getenv("NOTION_PAGE_ID")},
        "properties": {
            "title": {"title": [{"type": "text", "text": {"content": title[:100]}}]}
        },
        "children": children,
    }
    data = call(
        "POST",
        "https://api.notion.com/v1/pages",
        headers={
            "Authorization": f"Bearer {os.getenv('NOTION_TOKEN')}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json_body=body,
        integration="notion",
    )
    return {"page_url": data.get("url"), "id": data.get("id")}


if __name__ == "__main__":
    # Run this FIRST. Do not write agent code until all four print sensibly.
    print("commits ->", get_commits(limit=3))
    print("jira    ->", create_jira_issue("Smoke test", "Created by setup check"))
    print("deploy  ->", trigger_deploy("smoke test"))
    print("notion  ->", write_notion_report("Smoke test", "It works."))

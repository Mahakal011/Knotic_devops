# Knotic: AI DevOps & Deployment Agent

An autonomous release engineering agent built for Build with Swytchcode, Track 3.

Knotic reads recent GitHub commit activity, identifies release risks such as
bugs, hotfixes, and reverts, files Jira issues, triggers a Netlify deployment,
and publishes a release report to Notion.

## What it does

Give it one instruction, such as "run the release pipeline", and it:

1. Fetches recent commits from GitHub.
2. Detects unresolved bugs, reverts, and hotfixes.
3. Files Jira issues for risky commits.
4. Triggers a Netlify production deploy.
5. Writes a structured release report to Notion.

## Why Swytchcode

Every outbound integration call passes through the single `call()` function in
`tools.py`. Setting `USE_SWYTCHCODE=true` routes configured integrations through
the Swytchcode execution layer.

This keeps the agent architecture simple: GitHub, Jira, Netlify, and Notion can
all be controlled through one integration boundary for auth, retries, schema
validation, and future provider changes.

## Architecture

```text
Streamlit UI
     |
Agent loop
     |
Swytchcode-ready call layer
     |
  +--------+--------+---------+
GitHub   Jira    Netlify   Notion
     |
Release report
```

## Stack

- Python
- Streamlit
- Gemini API via `google-genai`
- GitHub API
- Jira API
- Netlify build hooks
- Notion API
- Swytchcode-ready integration layer

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env
python tools.py
streamlit run app.py
```

Fill `.env` with your own credentials before running. Never commit `.env`.

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI showing the agent pipeline live |
| `agent.py` | Gemini tool loop and deterministic fallback pipeline |
| `tools.py` | GitHub, Jira, Netlify, and Notion integrations |
| `src/` | Demo repository files used to create realistic commit history |

## Safety

The app includes a deterministic fallback pipeline so a Gemini quota error does
not crash the demo. Missing Jira or Netlify credentials are reported as skipped
instead of failing silently.

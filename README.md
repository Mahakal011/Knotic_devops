# AI DevOps & Deployment Agent

An autonomous release engineer. It reads GitHub commit activity, files Jira
issues for problems it finds, triggers a Netlify deployment, and publishes a
release report to Notion — driven end to end by an LLM tool loop, with every
outbound API call routed through Swytchcode.

Built for Build with Swytchcode, Track 3.

## What it does

Give it one instruction — "run the release pipeline" — and it decides the rest:

1. Fetches recent commits from GitHub
2. Reads the commit history and identifies unresolved bugs, reverts and hotfixes
3. Files a Jira issue for each one, written in its own words
4. Triggers a production deploy via a Netlify build hook
5. Writes a structured release report to Notion covering changes, issues filed,
   and deploy status

Nothing in step 2 onward is hardcoded. The model chooses which tools to call,
in what order, and how many times.

## Why Swytchcode

Every outbound call passes through a single `call()` function in `tools.py`.
Setting `USE_SWYTCHCODE=true` routes all four integrations through the
Swytchcode CLI, which handles auth, retries with backoff, idempotency and
schema validation.

That matters for an agent specifically. A model that gets a `200` with a `422`
buried in the body will report success and move on — the deploy never happened
and nothing surfaces the failure. Schema validation at the execution layer
catches drift before it reaches the agent's reasoning, so the model fails loudly
instead of hallucinating a completed pipeline.

## Architecture

```
Streamlit UI
     |
Agent loop  (LLM selects the next tool)
     |
Swytchcode  (auth, retries, schema validation)
     |
  +--------+--------+---------+
GitHub   Jira    Netlify   Notion
     |
Release report
```

## Stack

Python, the Gemini API tool-use loop, Streamlit for the interface, and
Swytchcode as the execution layer across GitHub, Jira, Netlify and Notion.

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env      # fill in your credentials
python tools.py           # verify all four integrations respond
streamlit run app.py
```

## Files

| File | Purpose |
|---|---|
| `tools.py` | The four integrations, plus the single `call()` layer that routes through Swytchcode |
| `agent.py` | Tool schemas, dispatch table, and the agent loop |
| `app.py` | Streamlit interface showing each tool call live |

## Design decisions

**One choke point for I/O.** Every API call goes through `call()`. Swapping
between direct HTTP and Swytchcode execution is a single environment variable,
and adding a fifth integration means adding one function, not touching the loop.

**The loop is capped.** Twelve turns maximum. An agent that loses the thread
stops rather than burning tokens indefinitely.

**Errors go back to the model.** Failed tool calls return the exception as a
`tool_result` with `is_error` set, so the agent can adapt — retry with different
arguments, or report the failure in the release notes rather than silently
omitting it.

## Limitations

Duplicate Jira detection relies on the model reading its own prior tool results
within a single run; it does not query existing Jira issues before filing.
Deploy status is fire-and-forget — the agent confirms the hook accepted the
request but does not poll Netlify for build completion.

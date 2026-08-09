"""
Demo UI. Run with:  streamlit run app.py

The point of this file is the jury demo. Showing each tool call as it happens
is what makes the agent legible in 2.5 minutes.
"""

import streamlit as st
import agent

st.set_page_config(page_title="AI DevOps Agent", layout="centered")
st.title("AI DevOps & Deployment Agent")
st.caption("GitHub to Jira to Netlify to Notion, routed through Swytchcode")

request = st.text_area(
    "Instruction",
    "Run the release pipeline for the latest commits.",
    height=80,
)

ICONS = {
    "get_commits": "Reading GitHub commits",
    "create_jira_issue": "Filing Jira issue",
    "trigger_deploy": "Triggering Netlify deploy",
    "write_notion_report": "Writing Notion report",
}

if st.button("Run pipeline", type="primary"):
    log = st.container()

    def on_event(kind, payload):
        if kind == "thought":
            log.markdown(f"_{payload}_")
        elif kind == "tool_call":
            log.info(f"{ICONS.get(payload['name'], payload['name'])}")
            log.json(payload["input"], expanded=False)
        elif kind == "tool_result":
            out = payload["output"]
            if isinstance(out, dict) and "error" in out:
                log.error(out["error"])
            else:
                log.success("Done")
                log.json(out, expanded=False)
        elif kind == "done":
            log.markdown("---")
            log.markdown(payload)

    with st.spinner("Agent working..."):
        agent.run(request, on_event=on_event)

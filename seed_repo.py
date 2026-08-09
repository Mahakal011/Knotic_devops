"""Seed the GitHub repo with realistic fake commits via the Contents API."""
import base64, os, requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["GITHUB_TOKEN"]
REPO  = os.environ["GITHUB_REPO"]
BASE  = f"https://api.github.com/repos/{REPO}/contents"
HDR   = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}

COMMITS = [
    ("README.md",      "init: project scaffold",               "# Knotic DevOps Demo"),
    ("src/auth.py",    "feat: add JWT authentication",          "# JWT auth module"),
    ("src/export.py",  "feat: add export button endpoint",      "# export route"),
    ("src/login.py",   "fix: login redirect loop on OAuth",     "# login fix"),
    ("src/cache.py",   "fix: null pointer in cache handler",    "# cache fix"),
    ("src/deploy.py",  "hotfix: deployment fails on prod",      "# deploy hotfix"),
    ("src/db.py",      "feat: add pagination to DB queries",    "# db pagination"),
    ("src/notify.py",  "fix: email notification not firing",    "# notify fix"),
    ("src/api.py",     "revert: revert broken API refactor",    "# api revert"),
    ("src/utils.py",   "chore: update dependencies",            "# utils"),
]

for path, message, content in COMMITS:
    encoded = base64.b64encode(content.encode()).decode()
    body = {"message": message, "content": encoded}

    # check if file exists so we can pass its sha for updates
    check = requests.get(f"{BASE}/{path}", headers=HDR)
    if check.status_code == 200:
        body["sha"] = check.json()["sha"]

    r = requests.put(f"{BASE}/{path}", headers=HDR, json=body)
    r.raise_for_status()
    print(f"✓ {message}")

print("\nDone — repo seeded with", len(COMMITS), "commits.")

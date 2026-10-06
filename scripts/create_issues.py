"""Create the GitHub milestones, labels and issues defined in docs/backlog.md.

docs/backlog.md is the source of truth. Safe to re-run: existing labels are updated,
existing milestones and issues (matched by title) are skipped.

Requires the GitHub CLI, authenticated:  gh auth login

    python scripts/create_issues.py --dry-run   # show what would be created
    python scripts/create_issues.py             # create in the current repo
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

BACKLOG = Path(__file__).resolve().parent.parent / "docs" / "backlog.md"

LABEL_COLOURS = {
    "priority:P0": "b60205", "priority:P1": "d93f0b", "priority:P2": "fbca04", "priority:P3": "c2e0c6",
    "area:self-service": "1d76db", "area:lifecycle": "0e8a16", "area:provisioning": "5319e7",
    "area:deployment": "006b75", "area:reliability": "0052cc", "area:governance": "b4a8ff",
    "area:observability": "bfd4f2", "area:day-2": "c5def5",
}

MILESTONE_RE = re.compile(r"^## (M\d) — (.+)$")
ISSUE_RE = re.compile(r"^### \[(M\d-\d+)\] (.+)$")


def parse(text: str) -> tuple[dict[str, str], list[dict]]:
    """Return ({'M1': 'M1 — Production Foundations', ...}, [issue, ...])."""
    milestones: dict[str, str] = {}
    issues: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        if m := MILESTONE_RE.match(line):
            milestones[m.group(1)] = f"{m.group(1)} — {m.group(2)}"
            current = None
            continue
        if m := ISSUE_RE.match(line):
            issue_id, title = m.groups()
            current = {
                "id": issue_id,
                "title": f"[{issue_id}] {title}",
                "milestone": issue_id.split("-")[0],
                "labels": [],
                "body": [],
            }
            issues.append(current)
            continue
        if current is None:
            continue
        if line.startswith("**Labels:**"):
            current["labels"] = [l.strip() for l in line.split(":**", 1)[1].split(",")]
        current["body"].append(line)
    for issue in issues:
        issue["milestone"] = milestones[issue["milestone"]]
        issue["body"] = "\n".join(issue["body"]).strip() + "\n\n_Source: docs/backlog.md_\n"
    return milestones, issues


def gh(*args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["gh", *args], input=input_text, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        sys.exit(f"gh {' '.join(args[:3])} ... failed:\n{result.stderr.strip()}")
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print the plan, change nothing")
    args = parser.parse_args()

    milestones, issues = parse(BACKLOG.read_text(encoding="utf-8"))
    labels = sorted({l for i in issues for l in i["labels"]})
    print(f"Parsed {len(milestones)} milestones, {len(labels)} labels, {len(issues)} issues from {BACKLOG.name}")

    if args.dry_run:
        for title in milestones.values():
            print(f"  milestone  {title}")
        for label in labels:
            print(f"  label      {label}")
        for i in issues:
            print(f"  issue      {i['title']}  [{', '.join(i['labels'])}]  -> {i['milestone']}")
        return

    repo = json.loads(gh("repo", "view", "--json", "nameWithOwner"))["nameWithOwner"]
    print(f"Target repository: {repo}")

    for label in labels:
        gh("label", "create", label, "--color", LABEL_COLOURS.get(label, "ededed"), "--force")
    print(f"  labels ready ({len(labels)})")

    existing_ms = {m["title"] for m in json.loads(gh("api", f"repos/{repo}/milestones?state=all&per_page=100"))}
    for title in milestones.values():
        if title in existing_ms:
            print(f"  milestone exists: {title}")
            continue
        gh("api", "-X", "POST", f"repos/{repo}/milestones", "-f", f"title={title}")
        print(f"  milestone created: {title}")

    existing = {i["title"] for i in json.loads(gh("issue", "list", "--state", "all", "--limit", "500", "--json", "title"))}
    for i in issues:
        if i["title"] in existing:
            print(f"  issue exists: {i['title']}")
            continue
        cmd = ["issue", "create", "--title", i["title"], "--body-file", "-", "--milestone", i["milestone"]]
        for label in i["labels"]:
            cmd += ["--label", label]
        url = gh(*cmd, input_text=i["body"]).strip()
        print(f"  created {i['title']}  {url}")

    print("Done.")


if __name__ == "__main__":
    main()

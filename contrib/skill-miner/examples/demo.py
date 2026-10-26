#!/usr/bin/env python3
"""Run skill-miner end to end on invented data, without touching your real sessions.

    python3 tools/skill-miner/examples/demo.py          # prints the summary and one candidate
    python3 tools/skill-miner/examples/demo.py --keep   # leaves the temp dir for inspection

Builds a throwaway git repo plus fake ~/.claude and ~/.codex directories in a temp
dir, writes a few synthetic sessions into them, and points the miner at them with
--claude-home / --codex-home.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import skill_miner  # noqa: E402

TS = "2099-01-01T00:00:00Z"
REQUESTS = [
    "regenerate the changelog from merged pull requests and group entries by component",
    "regenerate the changelog from merged pull requests, grouped by component",
    "can you regenerate changelog from the merged pull requests and group by component",
]
CORRECTION = "no, run the formatter before committing"


def claude_session(home: Path, repo: Path, sid: str, prompts: list[str]) -> None:
    d = home / "projects" / skill_miner.encode_claude_project(repo)
    d.mkdir(parents=True, exist_ok=True)
    base = {"cwd": str(repo), "sessionId": sid, "timestamp": TS}
    recs = []
    for p in prompts:
        recs.append({**base, "type": "user", "promptSource": "typed", "message": {"content": p}})
        recs.append({**base, "type": "assistant", "message": {"content": [{"type": "text", "text": "done"}]}})
    (d / f"{sid}.jsonl").write_text("\n".join(map(json.dumps, recs)) + "\n")


def codex_session(home: Path, repo: Path, sid: str, prompts: list[str]) -> None:
    d = home / "sessions" / "2099" / "01" / "01"
    d.mkdir(parents=True, exist_ok=True)
    recs = [{"timestamp": TS, "type": "session_meta", "payload": {"id": sid, "cwd": str(repo)}}]
    for p in prompts:
        recs.append({"timestamp": TS, "type": "event_msg", "payload": {"type": "user_message", "message": p}})
        recs.append({"timestamp": TS, "type": "event_msg", "payload": {"type": "agent_message", "message": "done"}})
    (d / f"rollout-{sid}.jsonl").write_text("\n".join(map(json.dumps, recs)) + "\n")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="skill-miner-demo-")).resolve()
    try:
        repo = tmp / "example-repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / ".gitignore").write_text(".skill-candidates/\n")
        claude, codex = tmp / "claude", tmp / "codex"
        claude_session(claude, repo, "0001demo", [REQUESTS[0], CORRECTION])
        claude_session(claude, repo, "0002demo", [REQUESTS[1], CORRECTION])
        codex_session(codex, repo, "0003demo", [REQUESTS[2], CORRECTION])

        rc = skill_miner.main([
            "--repo", str(repo), "--claude-home", str(claude), "--codex-home", str(codex), "--since", "all",
        ])
        out = sorted((repo / ".skill-candidates").rglob("*.md"))
        if out:
            print("\n--- " + out[0].name + " ---\n" + out[0].read_text())
        return rc
    finally:
        if "--keep" in sys.argv:
            print(f"kept {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

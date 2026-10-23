"""
Import Antigravity (~/.gemini/antigravity/brain/<id>/.system_generated/logs/transcript.jsonl) or Claude Code
(~/.claude/projects/<project>/<session>.jsonl) session transcripts into Neo4j Aura or NAMS through the
neo4j-agent-memory SDK, with the same capture code as bin/agent-memory-hook: so a recorded session looks like one
the hooks captured live (prompt and answer as messages, tool calls as reasoning steps).

  venv/bin/python harness/import_transcripts.py --story                      # latest Aura run of demo/story.json
  venv/bin/python harness/import_transcripts.py <session-or-conversation-id> # Claude session id, Antigravity conv id, or file path
  venv/bin/python harness/import_transcripts.py --backend nams <id>          # import into NAMS instead of Aura
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
CLAUDE_DIR = Path.home() / ".claude" / "projects" / str(ROOT).replace("/", "-")
ANTIGRAVITY_BRAIN = Path.home() / ".gemini" / "antigravity" / "brain"


def clean_prompt(raw: str) -> str:
    if "<USER_REQUEST>" in raw and "</USER_REQUEST>" in raw:
        raw = raw.split("<USER_REQUEST>", 1)[1].split("</USER_REQUEST>", 1)[0]
    return raw.strip()


def turns(path: Path) -> list[dict]:
    """[{prompt, ts, harness, tools: [(name, input, result)], answer}] from one Antigravity or Claude transcript."""
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if any(r.get("type") in ("USER_INPUT", "PLANNER_RESPONSE") for r in records):
        out, pending = [], []
        for rec in records:
            kind = rec.get("type")
            if kind == "USER_INPUT" and rec.get("content"):
                out.append({"prompt": clean_prompt(rec["content"]), "ts": rec.get("created_at"),
                            "harness": "antigravity", "tools": [], "answer": []})
                pending = []
            elif kind == "PLANNER_RESPONSE" and out:
                for tc in rec.get("tool_calls") or []:
                    item = [tc.get("name", "?"), tc.get("args") or {}, ""]
                    out[-1]["tools"].append(item)
                    pending.append(item)
                if rec.get("content", "").strip():
                    out[-1]["answer"].append(rec["content"].strip())
            elif kind == "GENERIC" and pending:
                pending.pop(0)[2] = rec.get("content", "")
        for t in out:
            t["tools"] = [tuple(x) for x in t["tools"]]
            t["answer"] = "\n".join(t["answer"]).strip()
        return out

    out, results = [], {}
    for rec in records:  # tool results arrive in later user records, keyed by tool_use_id
        for c in ((rec.get("message") or {}).get("content") or []) if rec.get("type") == "user" else []:
            if isinstance(c, dict) and c.get("type") == "tool_result":
                body = c.get("content")
                results[c["tool_use_id"]] = body if isinstance(body, str) else " ".join(
                    x.get("text", "") for x in body or [] if isinstance(x, dict))
    for rec in records:
        content = (rec.get("message") or {}).get("content")
        if rec.get("type") == "user" and isinstance(content, str):
            out.append({"prompt": clean_prompt(content), "ts": rec.get("timestamp"),
                        "harness": "claude", "tools": [], "answer": []})
        elif rec.get("type") == "assistant" and out:
            for c in content or []:
                if c.get("type") == "tool_use":
                    out[-1]["tools"].append((c["name"], c.get("input") or {}, results.get(c["id"], "")))
                elif c.get("type") == "text" and c.get("text", "").strip():
                    out[-1]["answer"].append(c["text"])
    for t in out:
        t["answer"] = "\n".join(t["answer"]).strip()
    return out


def resolve_transcript(sid: str) -> tuple[str, Path]:
    p = Path(sid)
    if p.exists():
        session_id = p.parent.parent.parent.name if p.name == "transcript.jsonl" else p.stem
        return session_id, p
    agy = ANTIGRAVITY_BRAIN / sid / ".system_generated" / "logs" / "transcript.jsonl"
    if agy.exists():
        return sid, agy
    return sid, CLAUDE_DIR / f"{sid}.jsonl"


def latest_story_run() -> list[str]:
    """Session ids of the most recent day-1, day-2, day-3 runs that used the agent-memory MCP server."""
    story = {s["prompt"].strip(): s["id"] for s in json.loads((ROOT / "demo" / "story.json").read_text())["sessions"]}
    latest = {}
    for path in (list(CLAUDE_DIR.glob("*.jsonl")) if CLAUDE_DIR.exists() else []):
        ts = turns(path)
        if not ts or ts[0]["prompt"].strip() not in story:
            continue
        if not any(name.startswith("mcp__agent-memory__") or name.startswith("memory_") for name, _, _ in ts[0]["tools"]):
            continue
        day = story[ts[0]["prompt"].strip()]
        if day not in latest or (ts[0]["ts"] or "") > latest[day][0]:
            latest[day] = (ts[0]["ts"] or "", str(path))
    return [latest[d][1] for d in sorted(latest)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sessions", nargs="*")
    parser.add_argument("--story", action="store_true", help="import the latest Aura run of the demo story")
    parser.add_argument("--backend", choices=("aura", "nams"), default="aura")
    args = parser.parse_args()
    sessions = latest_story_run() if args.story else args.sessions
    if not sessions:
        sys.exit("no sessions to import")

    from aura_hooks_daemon import Capture
    from memory_tools import AgentMemory

    capture = Capture(AgentMemory(args.backend))
    try:
        for raw_sid in sessions:
            sid, path = resolve_transcript(raw_sid)
            for t in turns(path):
                meta = {"harness": t.get("harness", "claude"), "source": "import_transcripts",
                        "project": str(ROOT), "projectDirectory": str(ROOT), "original_ts": t["ts"]}
                capture.prompt(sid, t["prompt"], meta)
                for name, tool_input, result in t["tools"]:
                    capture.tool(sid, name, tool_input, result, meta)
                if t["answer"]:
                    capture.answer(sid, t["answer"], meta)
                print(f"{sid[:8]}  {t['ts']}  {len(t['tools'])} tool calls  {t['prompt'][:60]!r}")
    finally:
        capture.memory.close()


if __name__ == "__main__":
    main()

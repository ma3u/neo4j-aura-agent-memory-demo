"""
Import Claude Code session transcripts (~/.claude/projects/<project>/<session>.jsonl) into Neo4j Aura through the
neo4j-agent-memory SDK, with the same capture code as bin/agent-memory-hook: so a session recorded before the hooks
existed looks like one the hooks captured live (prompt and answer as messages, tool calls as reasoning steps).

  venv/bin/python harness/import_transcripts.py --story          # the latest Aura run of demo/story.json (day-1..3)
  venv/bin/python harness/import_transcripts.py <session-id> ...  # any sessions of this project
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
PROJECT_DIR = Path.home() / ".claude" / "projects" / str(ROOT).replace("/", "-")


def turns(path: Path) -> list[dict]:
    """[{prompt, ts, tools: [(name, input, result)], answer}] from one transcript."""
    out, results = [], {}
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    for rec in records:  # tool results arrive in later user records, keyed by tool_use_id
        for c in ((rec.get("message") or {}).get("content") or []) if rec.get("type") == "user" else []:
            if isinstance(c, dict) and c.get("type") == "tool_result":
                body = c.get("content")
                results[c["tool_use_id"]] = body if isinstance(body, str) else " ".join(
                    x.get("text", "") for x in body or [] if isinstance(x, dict))
    for rec in records:
        content = (rec.get("message") or {}).get("content")
        if rec.get("type") == "user" and isinstance(content, str):
            out.append({"prompt": content, "ts": rec.get("timestamp"), "tools": [], "answer": []})
        elif rec.get("type") == "assistant" and out:
            for c in content or []:
                if c.get("type") == "tool_use":
                    out[-1]["tools"].append((c["name"], c.get("input") or {}, results.get(c["id"], "")))
                elif c.get("type") == "text" and c.get("text", "").strip():
                    out[-1]["answer"].append(c["text"])
    for t in out:
        t["answer"] = "\n".join(t["answer"]).strip()
    return out


def latest_story_run() -> list[str]:
    """Session ids of the most recent day-1, day-2, day-3 runs that used the agent-memory MCP server."""
    story = {s["prompt"].strip(): s["id"] for s in json.loads((ROOT / "demo" / "story.json").read_text())["sessions"]}
    latest = {}
    for path in PROJECT_DIR.glob("*.jsonl"):
        ts = turns(path)
        if not ts or ts[0]["prompt"].strip() not in story:
            continue
        if not any(name.startswith("mcp__agent-memory__") for name, _, _ in ts[0]["tools"]):
            continue
        day = story[ts[0]["prompt"].strip()]
        if day not in latest or ts[0]["ts"] > latest[day][0]:
            latest[day] = (ts[0]["ts"], path.stem)
    return [latest[d][1] for d in sorted(latest)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sessions", nargs="*")
    parser.add_argument("--story", action="store_true", help="import the latest Aura run of the demo story")
    args = parser.parse_args()
    sessions = latest_story_run() if args.story else args.sessions
    if not sessions:
        sys.exit("no sessions to import")

    from aura_hooks_daemon import Capture
    from memory_tools import AgentMemory

    capture = Capture(AgentMemory("aura"))
    try:
        for sid in sessions:
            for t in turns(PROJECT_DIR / f"{sid}.jsonl"):
                meta = {"harness": "claude", "source": "import_transcripts", "project": str(ROOT), "original_ts": t["ts"]}
                capture.prompt(sid, t["prompt"], meta)
                for name, tool_input, result in t["tools"]:
                    capture.tool(sid, name, tool_input, result)
                if t["answer"]:
                    capture.answer(sid, t["answer"], meta)
                print(f"{sid[:8]}  {t['ts']}  {len(t['tools'])} tool calls  {t['prompt'][:60]!r}")
    finally:
        capture.memory.close()


if __name__ == "__main__":
    main()

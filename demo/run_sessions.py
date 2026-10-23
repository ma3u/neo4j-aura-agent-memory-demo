"""
Run the demo story: three separate headless sessions (Antigravity or Claude Code) that share nothing but long-term memory.

  day-1  Mara briefs the agent about her project
  day-2  Mara corrects a fact (fraud-api moved from Jonas to Lena)
  day-3  a question that needs 2 hops through the memory plus the correction

Backends (one at a time, so the result shows what each memory does on its own):
  aura  Neo4j Labs Agent Memory (neo4j-agent-memory) on your Neo4j Aura instance, through the SDK's MCP server
        (bin/agent-memory-mcp) and bin/agent-memory-hook --backend aura (session capture + recall).
  nams  Neo4j Agent Memory Service: in Antigravity, bin/nams-mcp and bin/agent-memory-hook --backend nams store
        every prompt, answer and tool call and inject recalled memory; in Claude Code, the nams-hooks plugin and
        demo/nams-mcp.json provide the same pair.

Each session is isolated (harness/claude_backends.py): no chat history, no file memory, no peeking into this repo.
Only the memory backend. Transcripts go to demo/transcripts/<backend>/<day>.md.

Run:  venv/bin/python demo/run_sessions.py --backend aura      # Antigravity MCP + hooks on Aura (default)
      venv/bin/python demo/run_sessions.py --backend nams      # Antigravity MCP + hooks on NAMS
      venv/bin/python demo/run_sessions.py --backend aura --only day-3
      venv/bin/python demo/run_sessions.py --backend aura --harness claude
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
load_dotenv(ROOT / ".env")

from claude_backends import BACKENDS, run_antigravity, write_aura_mcp_config  # noqa: E402

STORY = json.loads((ROOT / "demo" / "story.json").read_text())
TRANSCRIPTS = ROOT / "demo" / "transcripts"
TARGET = {"aura": "neo4j-agent-memory MCP -> Neo4j Aura", "nams": "NAMS MCP -> memory.neo4jlabs.com"}


def run_claude(prompt: str, backend: str, model: str) -> dict:
    """One headless Claude Code session. Returns memory tool calls (name, input, result), the answer, turns and cost."""
    cfg = BACKENDS[backend]
    prefix = f"mcp__{cfg['server']}__"
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose", "--model", model,
           "--strict-mcp-config", "--setting-sources", "project", *cfg["args"]]
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900, env={**os.environ, **cfg["env"]})
    calls, results, final = [], {}, {}
    for line in out.stdout.splitlines():
        event = json.loads(line)
        message = event.get("message")
        content = (message.get("content") if isinstance(message, dict) else None) or []
        if event.get("type") == "assistant":
            calls += [c for c in content if c.get("type") == "tool_use" and c["name"].startswith(prefix)]
        elif event.get("type") == "user":
            for c in content:
                if c.get("type") == "tool_result":
                    body = c.get("content")
                    results[c["tool_use_id"]] = body if isinstance(body, str) else " ".join(x.get("text", "") for x in body)
        elif event.get("type") == "result":
            final = event
    if not final:
        raise RuntimeError(f"claude -p failed: {out.stderr[-500:]}")
    return {
        "calls": [{"tool": c["name"].removeprefix(prefix), "input": c["input"], "result": results.get(c["id"], "")}
                  for c in calls],
        "answer": final.get("result", ""), "turns": final.get("num_turns"), "cost_usd": final.get("total_cost_usd"),
    }


def to_markdown(session: dict, backend: str, run: dict, harness: str = "antigravity") -> str:
    lines = [f"# {session['title']} ({backend})", "", "**Prompt**", "", "> " + session["prompt"].replace("\n", "\n> "), ""]
    if run["calls"]:
        lines += [f"**Memory tool calls ({TARGET[backend]})**", ""]
        for c in run["calls"]:
            args = ", ".join(f"{k}={v!r}" for k, v in c["input"].items())
            result = c["result"].strip().replace("\n", "\n    ")
            lines += [f"- `{c['tool']}({args})`", f"  - {result[:1500]}"]
    if harness == "antigravity":
        lines += ["", f"_agent-memory-hook ({backend}) also stored this prompt, tool calls, and answer and injected recalled memory via PreInvocation._"]
    elif backend == "nams":
        lines += ["", "_nams-hooks also stored this prompt and answer and injected recalled memory into the prompt._"]
    cost = run.get("cost_usd") or 0.0
    lines += ["", "**Answer**", "", run["answer"].strip(), "", f"_{run['turns']} turns, ${cost:.3f}_", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=list(BACKENDS), default="aura")
    parser.add_argument("--harness", choices=["antigravity", "claude"], default="antigravity")
    parser.add_argument("--only", help="run one session id, e.g. day-3")
    parser.add_argument("--model", default="sonnet")
    args = parser.parse_args()
    if args.backend == "nams" and not os.getenv("NAMS_API_KEY"):
        sys.exit("Set NAMS_API_KEY in .env (memory.neo4jlabs.com -> API Keys)")

    write_aura_mcp_config()
    out_dir = TRANSCRIPTS / args.backend
    out_dir.mkdir(parents=True, exist_ok=True)
    for session in STORY["sessions"]:
        if args.only and session["id"] != args.only:
            continue
        print(f"\n=== {session['title']} ({args.backend}, {args.harness}) ===")
        if args.harness == "antigravity":
            run = run_antigravity(session["prompt"], args.backend)
        else:
            run = run_claude(session["prompt"], args.backend, args.model)
        for c in run["calls"]:
            print(f"  [{c['tool']}] {json.dumps(c['input'])[:300]}")
        cost = run.get("cost_usd") or 0.0
        print(f"\n{run['answer'].strip()}\n  ({run['turns']} turns, ${cost:.3f})")
        (out_dir / f"{session['id']}.md").write_text(to_markdown(session, args.backend, run, args.harness))
        if args.harness == "antigravity" or args.backend == "aura":
            flush_hooks()


def flush_hooks() -> None:
    """Wait until bin/agent-memory-hook's daemon has written (and extracted) everything from the last session."""
    req = urllib.request.Request(f"http://127.0.0.1:{os.getenv('AGENT_MEMORY_HOOKS_PORT', '8787')}",
                                 data=json.dumps({"event": "flush"}).encode(), headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=600).read()
    except OSError as e:
        print(f"  (hook daemon not reachable: {e})")


if __name__ == "__main__":
    main()

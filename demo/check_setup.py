"""
Smoke test for both setups (Aura and NAMS) in both Antigravity and Claude Code.
Read-only: nothing is written to Aura or NAMS. Run it before the live demo.

  Aura   connection, SDK schema and memory, session history (agent-memory-hook), the SDK's MCP server
         (bin/agent-memory-mcp starts, lists its tools), the Haystack tool (neo4j-agent-memory over Bolt) finds the
         day-3 facts, Antigravity PreInvocation hook recalls memory from Aura, eval results
  NAMS   API key, active ontology, conversations captured, the hosted MCP server and bin/nams-mcp stdio proxy list
         their tools, the Haystack tool (neo4j-agent-memory, NAMS backend) finds the entities, Antigravity
         PreInvocation hook recalls memory from NAMS, hooks & MCP configs wired
  both   the ontology file is valid for the SDK

Run:  venv/bin/python demo/check_setup.py
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
load_dotenv(ROOT / ".env")

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""), flush=True)


def safely(name: str, fn) -> None:
    try:
        fn()
    except Exception as e:  # a smoke test reports, it does not stop at the first problem
        check(name, False, f"{type(e).__name__}: {str(e)[:160]}")


# ---------- shared ----------

def ontology() -> None:
    out = subprocess.run([str(ROOT / "venv/bin/neo4j-agent-memory"), "ontology", "validate",
                          str(ROOT / "ontology/agent-memory-software-team.json")], capture_output=True, text=True)
    check("ontology file is valid for the SDK", "is valid" in out.stdout, out.stdout.strip().splitlines()[0][:80])


def antigravity_configs() -> None:
    mcp_cfg = json.loads((ROOT / ".agents/mcp_config.json").read_text()).get("mcpServers", {})
    check("Antigravity .agents/mcp_config.json has agent-memory and nams",
          "agent-memory" in mcp_cfg and "nams" in mcp_cfg, ", ".join(mcp_cfg))
    hooks = json.loads((ROOT / ".agents/hooks.json").read_text()).get("hooks", {})
    events = ("SessionStart", "PreInvocation", "PostToolUse", "Stop")
    aura_ok = all("agent-memory-hook" in " ".join(h["command"] for h in hooks.get("agent-memory-aura", {}).get(e, []))
                  for e in events)
    nams_ok = all("--backend nams" in " ".join(h["command"] for h in hooks.get("agent-memory-nams", {}).get(e, []))
                  for e in events)
    check("Antigravity .agents/hooks.json wired for Aura and NAMS", aura_ok and nams_ok, "SessionStart/PreInvocation/PostToolUse/Stop")


def antigravity_hook_recall(backend: str, expected: str) -> None:
    with tempfile.TemporaryDirectory(prefix="agy-check-") as tmp:
        transcript = Path(tmp) / "transcript.jsonl"
        transcript.write_text(json.dumps({
            "step_index": 0, "type": "USER_INPUT",
            "content": "<USER_REQUEST>\nWho owns fraud-api?\n</USER_REQUEST>",
        }) + "\n")
        payload = {"conversationId": "check-setup-readonly", "invocationNum": 1,
                   "transcriptPath": str(transcript), "workspacePaths": [str(ROOT)]}
        out = subprocess.run(
            [str(ROOT / "bin/agent-memory-hook"), "--backend", backend, "--event", "PreInvocation"],
            input=json.dumps(payload), cwd=ROOT, capture_output=True, text=True, timeout=60,
            env={**os.environ, "AGENT_MEMORY_HOOKS": "1", "AGENT_MEMORY_HOOKS_BACKEND": backend,
                 "AGENT_MEMORY_HOOKS_READONLY": "1"},
        )
        reply = json.loads(out.stdout) if out.stdout.strip() else {}
        msg = ((reply.get("injectSteps") or [{}])[0]).get("ephemeralMessage", "")
        check(f"Antigravity PreInvocation hook ({backend}) injects recalled memory",
              expected in msg, f"{len(msg)} chars recalled")


# ---------- Aura ----------

def aura_graph() -> None:
    from neo4j import GraphDatabase

    with GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"])) as d:
        d.verify_connectivity()
        check("Aura reachable", True, os.environ["NEO4J_URI"].split("//")[-1].split(".")[0][:4] + "...")
        with d.session() as s:
            n = lambda q: s.run(q).single()[0]  # noqa: E731
            entities, rels, facts = n("MATCH (e:Entity) RETURN count(e)"), n("MATCH (:Entity)-[r:RELATED_TO]->() RETURN count(r)"), n("MATCH (f:Fact) RETURN count(f)")
            check("SDK memory present (entities, relationships, facts)", entities > 0 and rels > 0, f"{entities} / {rels} / {facts}")
            extracted = n("MATCH ()-[r:RELATED_TO]->() WHERE r.extractor IS NOT NULL RETURN count(r)")
            check("ontology-driven extraction produced relationships", extracted > 0, f"{extracted} extracted")
            owners = [r["o"] for r in s.run("MATCH (p:Entity)-[:RELATED_TO {type: 'OWNS'}]->(:Entity {name: 'fraud-api'}) RETURN p.name AS o")]
            check("correction stored (Lena OWNS fraud-api)", "Lena" in owners, f"owners: {', '.join(owners)}")
            sessions = n("MATCH (c:Conversation) WHERE EXISTS { (c)-[:HAS_MESSAGE]->(:Message {role: 'user'}) } "
                         "AND EXISTS { (c)-[:HAS_MESSAGE]->(:Message {role: 'assistant'}) } RETURN count(c)")
            check("session history in Aura (prompt + answer per session)", sessions >= 3, f"{sessions} sessions")
            traces, calls = n("MATCH (t:ReasoningTrace) RETURN count(t)"), n("MATCH (tc:ToolCall) RETURN count(tc)")
            check("tool calls as reasoning traces in Aura", traces >= 3 and calls > 0, f"{traces} traces, {calls} tool calls")
            variants = n("MATCH (v:DemoEvalVariant) RETURN count(v)")
            check("eval results stored in Aura", variants >= 5, f"{variants} variants")


async def _list_tools_stdio(command: str) -> list[str]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=command, args=[], cwd=str(ROOT))
    with open(os.devnull, "w") as devnull:
        async with stdio_client(params, errlog=devnull) as (r, w), ClientSession(r, w) as s:
            await s.initialize()
            return [t.name for t in (await s.list_tools()).tools]


def aura_mcp() -> None:
    tools = asyncio.run(asyncio.wait_for(_list_tools_stdio(str(ROOT / "bin/agent-memory-mcp")), 180))
    check("SDK MCP server (bin/agent-memory-mcp) starts on Aura and lists its tools",
          len(tools) >= 16 and "memory_search" in tools, f"{len(tools)} tools")


def haystack_tool(backend: str, must: list[str]) -> None:
    from memory_tools import AgentMemory

    memory = AgentMemory(backend)
    try:
        text = memory.search("fraud-api owner") + "\n" + memory.search("Ines")
    finally:
        memory.close()
    found = [m for m in must if m in text]
    check(f"Haystack tool ({backend}) finds {', '.join(must)}", found == must, f"found {found}")


# ---------- NAMS ----------

def nams_get(path: str) -> dict:
    req = urllib.request.Request(os.environ.get("NAMS_BASE_URL", "https://memory.neo4jlabs.com") + path,
                                 headers={"Authorization": "Bearer " + os.environ["NAMS_API_KEY"]})
    return json.load(urllib.request.urlopen(req, timeout=30))


def nams_api() -> None:
    check("NAMS API key valid", True, f"{nams_get('/v1/entities/count')['count']} entities")
    active = nams_get("/v1/ontologies/active")
    name = ((active.get("ontology") or {}).get("domain") or {}).get("id") or active.get("name")
    check("NAMS ontology active", name == "agent-memory-software-team", str(name))
    convs = nams_get("/v1/conversations?limit=50")["conversations"]
    captured = [c for c in convs if (c.get("metadata") or {}).get("harness") in ("claude", "antigravity")]
    check("session history captured in NAMS", len(captured) > 0, f"{len(captured)} of {len(convs)} conversations")


def nams_mcp() -> None:
    tools = asyncio.run(asyncio.wait_for(_list_tools_stdio(str(ROOT / "bin/nams-mcp")), 60))
    check("NAMS MCP launcher (bin/nams-mcp) connects and lists its tools",
          len(tools) >= 40 and "memory_search_entities" in tools, f"{len(tools)} tools")


def aura_hooks() -> None:
    hooks = json.loads((ROOT / ".claude/settings.json").read_text()).get("hooks", {})
    wired = all(any("agent-memory-hook" in h["command"] for m in hooks.get(e, []) for h in m["hooks"])
                for e in ("SessionStart", "UserPromptSubmit", "PostToolUse", "Stop"))
    check("Claude Code .claude/settings.json wired for agent-memory-hook", wired)


def nams_plugin() -> None:
    settings = json.loads((ROOT / ".claude/settings.json").read_text())
    check("Claude Code nams-hooks plugin enabled for this repo",
          settings.get("enabledPlugins", {}).get("nams-hooks@nams-plugins") is True)


def main() -> None:
    print("shared")
    safely("ontology", ontology)
    safely("Antigravity configs", antigravity_configs)
    print("Aura (neo4j-agent-memory)")
    safely("Aura graph", aura_graph)
    safely("SDK MCP server", aura_mcp)
    safely("Claude Code hooks", aura_hooks)
    safely("Haystack tool (aura)", lambda: haystack_tool("aura", ["Lena", "Ines"]))
    safely("Antigravity hook recall (aura)", lambda: antigravity_hook_recall("aura", "Lena"))
    print("NAMS")
    safely("NAMS API", nams_api)
    safely("NAMS MCP", nams_mcp)
    safely("Claude Code nams-hooks", nams_plugin)
    safely("Haystack tool (nams)", lambda: haystack_tool("nams", ["Lena", "Ines"]))
    safely("Antigravity hook recall (nams)", lambda: antigravity_hook_recall("nams", "Lena"))
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

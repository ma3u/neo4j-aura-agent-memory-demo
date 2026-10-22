"""
Smoke test for both setups. Read-only: nothing is written to Aura or NAMS. Run it before the live demo.

  Aura   connection, SDK schema and memory, Claude Code session history (agent-memory-hook), the SDK's MCP server
         (starts, lists its tools), the Haystack tool (neo4j-agent-memory over Bolt) finds the day-3 facts, eval results
  NAMS   API key, active ontology, conversations captured from Claude Code, the hosted MCP server lists its tools,
         the Haystack tool (neo4j-agent-memory, NAMS backend) finds the entities, hooks plugin enabled
  both   the ontology file is valid for the SDK

Run:  venv/bin/python demo/check_setup.py
"""
import asyncio
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
            msgs = n("MATCH (m:Message) RETURN count(m)")
            sessions = n("MATCH (c:Conversation) WHERE EXISTS { (c)-[:HAS_MESSAGE]->(:Message {role: 'user'}) } "
                         "AND EXISTS { (c)-[:HAS_MESSAGE]->(:Message {role: 'assistant'}) } RETURN count(c)")
            check("Claude Code session history in Aura (prompt + answer per session)", sessions >= 3, f"{sessions} sessions")
            traces, calls = n("MATCH (t:ReasoningTrace) RETURN count(t)"), n("MATCH (tc:ToolCall) RETURN count(tc)")
            check("tool calls as reasoning traces in Aura", traces >= 3 and calls > 0, f"{traces} traces, {calls} tool calls")
            variants = n("MATCH (v:DemoEvalVariant) RETURN count(v)")
            check("eval results stored in Aura", variants == 5, f"{variants} variants")


async def _list_tools_stdio() -> list[str]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=str(ROOT / "bin/agent-memory-mcp"), args=[], cwd=str(ROOT))
    with open(os.devnull, "w") as devnull:
        async with stdio_client(params, errlog=devnull) as (r, w), ClientSession(r, w) as s:
            await s.initialize()
            return [t.name for t in (await s.list_tools()).tools]


def aura_mcp() -> None:
    tools = asyncio.run(asyncio.wait_for(_list_tools_stdio(), 180))
    check("SDK MCP server starts on Aura and lists its tools", len(tools) >= 16 and "memory_search" in tools, f"{len(tools)} tools")


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
    claude = [c for c in convs if (c.get("metadata") or {}).get("harness") == "claude"]
    check("Claude Code history captured in NAMS (nams-hooks)", len(claude) > 0, f"{len(claude)} of {len(convs)} conversations")


async def _list_tools_http() -> list[str]:
    from mcp import ClientSession
    from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

    client = create_mcp_http_client(headers={"Authorization": "Bearer " + os.environ["NAMS_API_KEY"]})
    async with client, streamable_http_client("https://memory.neo4jlabs.com/mcp", http_client=client) as streams:
        async with ClientSession(streams[0], streams[1]) as s:
            await s.initialize()
            return [t.name for t in (await s.list_tools()).tools]


def nams_mcp() -> None:
    tools = asyncio.run(asyncio.wait_for(_list_tools_http(), 60))
    check("NAMS hosted MCP server lists its tools", len(tools) >= 40, f"{len(tools)} tools")


def aura_hooks() -> None:
    hooks = json.loads((ROOT / ".claude/settings.json").read_text()).get("hooks", {})
    wired = all(any("agent-memory-hook" in h["command"] for m in hooks.get(e, []) for h in m["hooks"])
                for e in ("SessionStart", "UserPromptSubmit", "PostToolUse", "Stop"))
    check("agent-memory-hook wired for SessionStart, UserPromptSubmit, PostToolUse, Stop", wired)


def nams_plugin() -> None:
    settings = json.loads((ROOT / ".claude/settings.json").read_text())
    check("nams-hooks plugin enabled for this repo", settings.get("enabledPlugins", {}).get("nams-hooks@nams-plugins") is True)


def main() -> None:
    print("shared");  safely("ontology", ontology)
    print("Aura (neo4j-agent-memory)")
    safely("Aura graph", aura_graph)
    safely("SDK MCP server", aura_mcp)
    safely("agent-memory-hook", aura_hooks)
    safely("Haystack tool (aura)", lambda: haystack_tool("aura", ["Lena", "Ines"]))
    print("NAMS")
    safely("NAMS API", nams_api)
    safely("NAMS MCP", nams_mcp)
    safely("nams-hooks", nams_plugin)
    safely("Haystack tool (nams)", lambda: haystack_tool("nams", ["Lena", "Ines"]))
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

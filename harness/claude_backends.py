"""
Headless Antigravity and Claude Code runners and MCP/hook configuration per memory backend,
shared by demo/run_sessions.py and eval/eval_memory.py.

  aura  Neo4j Labs Agent Memory (neo4j-agent-memory) on your Neo4j Aura instance: the SDK's own MCP server
        (bin/agent-memory-mcp -> `neo4j-agent-memory mcp serve --backend bolt`) plus bin/agent-memory-hook, which
        stores every prompt, answer and tool call and injects recalled memory (the Aura counterpart of nams-hooks).
        nams-hooks is switched off.
  nams  Neo4j Agent Memory Service (memory.neo4jlabs.com): in Antigravity, bin/nams-mcp bridges stdio to the hosted
        NAMS MCP server and bin/agent-memory-hook --backend nams stores every prompt, answer and tool call and
        injects recalled memory via PreInvocation; in Claude Code, the nams-hooks plugin (.claude/settings.json)
        and demo/nams-mcp.json provide the same pair.

Isolation, so a run measures the memory backend and nothing else:
  - Claude Code's own file memory (~/.claude/projects/<project>/memory/MEMORY.md, loaded into every session) is off.
    The env var alone did not stop it in headless runs, so the settings flag is set too.
  - No file, shell or web tools: a session must not read the answers from this repo or write notes to disk.
  - No raw Cypher (`graph_query`) or full export on Aura: the database also holds the eval's reference answers.
  - Eval runs are read-only: only search/get tools, and all hooks are off (nams-hooks and agent-memory-hook).
    Otherwise every eval question and answer is stored and becomes memory for the next question.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
ISOLATION = ["--disallowedTools", "Read,Grep,Glob,LS,Write,Edit,MultiEdit,NotebookEdit,Bash,WebFetch,WebSearch,Task,Agent"]
NO_AUTO_MEMORY = {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}
AURA_HOOKS_OFF = {"AGENT_MEMORY_HOOKS": "0"}  # read by bin/agent-memory-hook

AURA_MCP = ROOT / "demo" / "aura-mcp.json"  # generated: absolute path to the launcher, git-ignored
AURA_TOOLS = ["memory_store_message", "memory_add_entity", "memory_create_relationship", "memory_add_fact",
              "memory_add_preference", "memory_search", "memory_get_context", "memory_get_entity",
              "memory_get_conversation", "memory_get_observations", "memory_list_sessions"]
AURA_READ_TOOLS = ["memory_search", "memory_get_context", "memory_get_entity", "memory_get_conversation",
                   "memory_get_observations", "memory_list_sessions"]
NAMS_TOOLS = ["memory_search_entities", "memory_search_messages", "memory_get_entity", "memory_get_entity_by_name",
              "memory_get_entity_history", "memory_get_context", "memory_add_entity", "memory_create_relation",
              "memory_add_messages", "memory_create_conversation", "memory_resolve_entity"]
NAMS_READ_TOOLS = ["memory_search_entities", "memory_search_messages", "memory_get_entity", "memory_get_entity_by_name",
                   "memory_get_entity_history", "memory_get_context"]

ANTIGRAVITY_SESSION_PROMPT = """You are a coding assistant in Google Antigravity with long-term memory MCP tools.
- When the user shares project facts, people, services, ownership changes, or preferences, store them in memory using your MCP tools and confirm briefly.
- When the user asks a question about their project, look up the answer in memory before answering (facts may span multiple hops: service -> owner -> manager, and newer facts supersede older ones).
- Be concise."""


def tool_names(server: str, tools: list[str]) -> str:
    return ",".join(f"mcp__{server}__{t}" for t in tools)


def write_aura_mcp_config() -> None:
    AURA_MCP.write_text(json.dumps({"mcpServers": {"agent-memory": {
        "type": "stdio", "command": str(ROOT / "bin" / "agent-memory-mcp"), "args": []}}}, indent=2) + "\n")


BACKENDS = {
    "aura": {
        "server": "agent-memory",
        "mcp_command": str(ROOT / "bin" / "agent-memory-mcp"),
        "tools": AURA_TOOLS,
        "read_tools": AURA_READ_TOOLS,
        "args": ["--mcp-config", str(AURA_MCP), "--allowedTools", tool_names("agent-memory", AURA_TOOLS),
                 "--settings", json.dumps({"autoMemoryEnabled": False, "enabledPlugins": {"nams-hooks@nams-plugins": False}}),
                 *ISOLATION],
        "read_only_tools": tool_names("agent-memory", AURA_READ_TOOLS),
        "read_only_settings": {"autoMemoryEnabled": False, "enabledPlugins": {"nams-hooks@nams-plugins": False}},
        "env": {**NO_AUTO_MEMORY, "AGENT_MEMORY_HOOKS": "1", "AGENT_MEMORY_HOOKS_BACKEND": "aura"},
        "read_only_env": AURA_HOOKS_OFF,
    },
    "nams": {
        "server": "nams",
        "mcp_command": str(ROOT / "bin" / "nams-mcp"),
        "tools": NAMS_TOOLS,
        "read_tools": NAMS_READ_TOOLS,
        "args": ["--mcp-config", str(ROOT / "demo" / "nams-mcp.json"), "--allowedTools", tool_names("nams", NAMS_TOOLS),
                 "--settings", json.dumps({"autoMemoryEnabled": False}), *ISOLATION],
        "read_only_tools": tool_names("nams", NAMS_READ_TOOLS),
        "read_only_settings": {"autoMemoryEnabled": False, "enabledPlugins": {"nams-hooks@nams-plugins": False}},
        "env": {**NO_AUTO_MEMORY, **AURA_HOOKS_OFF, "NAMS_API_KEY": os.getenv("NAMS_API_KEY", ""),
                "NAMS_BASE_URL": os.getenv("NAMS_BASE_URL", "https://memory.neo4jlabs.com")},
        "read_only_env": AURA_HOOKS_OFF,
    },
}


def _call_antigravity_hook(backend: str, event: str, payload: dict) -> dict:
    out = subprocess.run(
        [str(ROOT / "bin" / "agent-memory-hook"), "--backend", backend, "--event", event],
        input=json.dumps(payload),
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "AGENT_MEMORY_HOOKS": "1", "AGENT_MEMORY_HOOKS_BACKEND": backend},
    )
    try:
        return json.loads(out.stdout) if out.stdout.strip() else {}
    except json.JSONDecodeError:
        return {}


async def _run_antigravity_async(
    prompt: str, backend: str, *, read_only: bool = False, system_prompt: str | None = None
) -> dict:
    from haystack.components.agents import Agent
    from haystack.dataclasses import ChatMessage
    from haystack.tools import Tool
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    from llm import chat_generator

    cfg = BACKENDS[backend]
    allowed = set(cfg["read_tools"] if read_only else cfg["tools"])
    session_id = f"agy-{backend}-{uuid.uuid4().hex[:10]}"
    calls: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="agy-session-") as tmp_dir:
        transcript = Path(tmp_dir) / "transcript.jsonl"
        base_payload = {"conversationId": session_id, "transcriptPath": str(transcript), "workspacePaths": [str(ROOT)]}
        effective_prompt = prompt

        if not read_only:
            transcript.write_text(
                json.dumps({"step_index": 0, "type": "USER_INPUT", "content": f"<USER_REQUEST>\n{prompt}\n</USER_REQUEST>"}) + "\n"
            )
            _call_antigravity_hook(backend, "SessionStart", base_payload)
            pre = _call_antigravity_hook(backend, "PreInvocation", base_payload)
            steps = pre.get("injectSteps") or []
            if steps and steps[0].get("ephemeralMessage"):
                effective_prompt = f"{steps[0]['ephemeralMessage']}\n\n{prompt}"

        params = StdioServerParameters(command=cfg["mcp_command"], args=[], cwd=str(ROOT))
        loop = asyncio.get_running_loop()
        with open(os.devnull, "w") as devnull:
            async with stdio_client(params, errlog=devnull) as (r, w), ClientSession(r, w) as mcp_session:
                await mcp_session.initialize()
                mcp_tools = [t for t in (await mcp_session.list_tools()).tools if t.name in allowed]

                def make_tool(t) -> Tool:
                    name = t.name
                    schema = dict(t.inputSchema or {"type": "object", "properties": {}})

                    def invoke(**kwargs) -> str:
                        clean_args = {k: v for k, v in kwargs.items() if v is not None}
                        res = asyncio.run_coroutine_threadsafe(
                            mcp_session.call_tool(name, clean_args), loop
                        ).result(timeout=120)
                        text = "\n".join(getattr(c, "text", str(c)) for c in (res.content or []))
                        calls.append({"tool": name, "input": clean_args, "result": text})
                        if not read_only:
                            _call_antigravity_hook(
                                backend,
                                "PostToolUse",
                                {**base_payload, "toolName": name, "toolInput": clean_args, "toolResponse": text},
                            )
                        return text or "(ok)"

                    return Tool(name=name, description=t.description or name, parameters=schema, function=invoke)

                hs_tools = [make_tool(t) for t in mcp_tools]
                agent = Agent(
                    chat_generator=chat_generator(),
                    tools=hs_tools,
                    system_prompt=system_prompt or ANTIGRAVITY_SESSION_PROMPT,
                    max_agent_steps=8,
                )
                result = await asyncio.to_thread(agent.run, messages=[ChatMessage.from_user(effective_prompt)])
                answer = result["messages"][-1].text or "(no answer)"
                turns = sum(1 for m in result["messages"] if m.role.value == "assistant")

        if not read_only:
            with transcript.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"step_index": 1, "type": "PLANNER_RESPONSE", "content": answer}) + "\n")
            _call_antigravity_hook(backend, "Stop", base_payload)

    return {"calls": calls, "answer": answer, "turns": turns, "cost_usd": 0.0}


def run_antigravity(
    prompt: str, backend: str, *, read_only: bool = False, system_prompt: str | None = None
) -> dict:
    """Run one isolated Antigravity MCP + hooks session without needing Claude Code credits."""
    return asyncio.run(_run_antigravity_async(prompt, backend, read_only=read_only, system_prompt=system_prompt))


async def _run_antigravity_batch_async(
    prompts: list[str], backend: str, *, system_prompt: str | None = None
) -> list[str]:
    from concurrent.futures import ThreadPoolExecutor

    from haystack.components.agents import Agent
    from haystack.dataclasses import ChatMessage
    from haystack.tools import Tool
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    from llm import chat_generator

    cfg = BACKENDS[backend]
    allowed = set(cfg["read_tools"])
    params = StdioServerParameters(command=cfg["mcp_command"], args=[], cwd=str(ROOT))
    loop = asyncio.get_running_loop()
    lock = asyncio.Lock()

    with open(os.devnull, "w") as devnull:
        async with stdio_client(params, errlog=devnull) as (r, w), ClientSession(r, w) as mcp_session:
            await mcp_session.initialize()
            mcp_tools = [t for t in (await mcp_session.list_tools()).tools if t.name in allowed]

            async def _call(name: str, args: dict):
                async with lock:
                    return await mcp_session.call_tool(name, args)

            def make_tool(t) -> Tool:
                name = t.name
                schema = dict(t.inputSchema or {"type": "object", "properties": {}})

                def invoke(**kwargs) -> str:
                    clean_args = {k: v for k, v in kwargs.items() if v is not None}
                    res = asyncio.run_coroutine_threadsafe(_call(name, clean_args), loop).result(timeout=120)
                    text = "\n".join(getattr(c, "text", str(c)) for c in (res.content or []))
                    return text or "(ok)"

                return Tool(name=name, description=t.description or name, parameters=schema, function=invoke)

            hs_tools = [make_tool(t) for t in mcp_tools]

            def ask_one(p: str) -> str:
                agent = Agent(
                    chat_generator=chat_generator(),
                    tools=hs_tools,
                    system_prompt=system_prompt or ANTIGRAVITY_SESSION_PROMPT,
                    max_agent_steps=8,
                )
                reply = agent.run(messages=[ChatMessage.from_user(p)])["messages"][-1]
                return reply.text or "(no answer)"

            with ThreadPoolExecutor(4) as pool:
                return await asyncio.to_thread(lambda: list(pool.map(ask_one, prompts)))


def run_antigravity_batch(prompts: list[str], backend: str, *, system_prompt: str | None = None) -> list[str]:
    """Run independent read-only Antigravity MCP sessions sharing one stdio MCP server process."""
    return asyncio.run(_run_antigravity_batch_async(prompts, backend, system_prompt=system_prompt))


"""
Headless Claude Code flags per memory backend, shared by demo/run_sessions.py and eval/eval_memory.py.

  aura  Neo4j Labs Agent Memory (neo4j-agent-memory) on your Neo4j Aura instance: the SDK's own MCP server
        (bin/agent-memory-mcp -> `neo4j-agent-memory mcp serve --backend bolt`). nams-hooks is switched off.
  nams  Neo4j Agent Memory Service (memory.neo4jlabs.com): the nams-hooks plugin (enabled in .claude/settings.json)
        stores every prompt and answer and injects recalled memory into each prompt, and the hosted NAMS MCP server
        (demo/nams-mcp.json, key from NAMS_API_KEY) gives the agent explicit memory tools.

Isolation, so a run measures the memory backend and nothing else:
  - Claude Code's own file memory (~/.claude/projects/<project>/memory/MEMORY.md, loaded into every session) is off.
    The env var alone did not stop it in headless runs, so the settings flag is set too.
  - No file, shell or web tools: a session must not read the answers from this repo or write notes to disk.
  - No raw Cypher (`graph_query`) or full export on Aura: the database also holds the eval's reference answers.
  - Eval runs are read-only: only search/get tools, and on NAMS the hooks are off. Otherwise every eval question and
    answer is stored by the hooks and becomes memory for the next question.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
ISOLATION = ["--disallowedTools", "Read,Grep,Glob,LS,Write,Edit,MultiEdit,NotebookEdit,Bash,WebFetch,WebSearch,Task,Agent"]
NO_AUTO_MEMORY = {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}

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


def tool_names(server: str, tools: list[str]) -> str:
    return ",".join(f"mcp__{server}__{t}" for t in tools)


def write_aura_mcp_config() -> None:
    AURA_MCP.write_text(json.dumps({"mcpServers": {"agent-memory": {
        "type": "stdio", "command": str(ROOT / "bin" / "agent-memory-mcp"), "args": []}}}, indent=2) + "\n")


BACKENDS = {
    "aura": {
        "server": "agent-memory",
        "args": ["--mcp-config", str(AURA_MCP), "--allowedTools", tool_names("agent-memory", AURA_TOOLS),
                 "--settings", json.dumps({"autoMemoryEnabled": False, "enabledPlugins": {"nams-hooks@nams-plugins": False}}),
                 *ISOLATION],
        "read_only_tools": tool_names("agent-memory", AURA_READ_TOOLS),
        "read_only_settings": {"autoMemoryEnabled": False, "enabledPlugins": {"nams-hooks@nams-plugins": False}},
        "env": NO_AUTO_MEMORY,
    },
    "nams": {
        "server": "nams",
        "args": ["--mcp-config", str(ROOT / "demo" / "nams-mcp.json"), "--allowedTools", tool_names("nams", NAMS_TOOLS),
                 "--settings", json.dumps({"autoMemoryEnabled": False}), *ISOLATION],
        "read_only_tools": tool_names("nams", NAMS_READ_TOOLS),
        "read_only_settings": {"autoMemoryEnabled": False, "enabledPlugins": {"nams-hooks@nams-plugins": False}},
        "env": {**NO_AUTO_MEMORY, "NAMS_API_KEY": os.getenv("NAMS_API_KEY", ""),
                "NAMS_BASE_URL": os.getenv("NAMS_BASE_URL", "https://memory.neo4jlabs.com")},
    },
}

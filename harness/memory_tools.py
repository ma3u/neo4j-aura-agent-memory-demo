"""
Neo4j Labs Agent Memory (neo4j-agent-memory) as a Haystack tool, on either backend:

  aura  MemoryClient over Bolt to your Neo4j Aura instance (same LLM and embedding model as bin/agent-memory-mcp,
        so queries hit the vectors the MCP server wrote)
  nams  MemoryClient against the hosted Neo4j Agent Memory Service workspace (NAMS_API_KEY)

Haystack tools are synchronous and the SDK is async, so one event loop runs in a background thread and keeps one
open client for all tool calls.
"""
import asyncio
import os
import threading
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from haystack.tools import Tool, create_tool_from_function
from pydantic import SecretStr

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

EMBEDDING = os.getenv("AGENT_MEMORY_EMBEDDING", "BAAI/bge-small-en-v1.5")
ONTOLOGY = Path(__file__).resolve().parent.parent / "ontology" / "agent-memory-software-team.json"
os.environ.setdefault("NAM_SCHEMA_CONFIG__ONTOLOGY_PATH", str(ONTOLOGY))  # same as bin/agent-memory-mcp
os.environ.setdefault("NAM_EXTRACTION__EXTRACTOR_TYPE", "llm")
os.environ.setdefault("LITELLM_DROP_PARAMS", "true")  # gpt-5-mini rejects the SDK's temperature=0.0


def _settings(backend: str):
    from neo4j_agent_memory import MemorySettings
    from neo4j_agent_memory.config.settings import NamsConfig, Neo4jConfig
    from neo4j_agent_memory.llm import from_provider

    if backend == "nams":
        return MemorySettings(backend="nams", nams=NamsConfig(
            api_key=SecretStr(os.environ["NAMS_API_KEY"]),
            endpoint=os.getenv("NAMS_BASE_URL", "https://memory.neo4jlabs.com").rstrip("/") + "/v1"))
    if os.getenv("AZURE_OPENAI_ENDPOINT"):  # same mapping as bin/agent-memory-mcp
        os.environ.setdefault("AZURE_API_KEY", os.environ["AZURE_OPENAI_API_KEY"])
        os.environ.setdefault("AZURE_API_BASE", os.environ["AZURE_OPENAI_ENDPOINT"])
        os.environ.setdefault("AZURE_API_VERSION", os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"))
        llm = from_provider(f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-5-mini')}", kind="llm")
    else:
        llm = from_provider(f"openai/{os.getenv('OPENAI_MODEL', 'gpt-5-mini')}", kind="llm")
    return MemorySettings(
        backend="bolt",
        neo4j=Neo4jConfig(uri=os.environ["NEO4J_URI"], username=os.environ["NEO4J_USERNAME"],
                          password=SecretStr(os.environ["NEO4J_PASSWORD"])),
        llm=llm,
        embedding=from_provider(EMBEDDING, kind="embedding"),
    )


class AgentMemory:
    """One open neo4j-agent-memory client on a background event loop."""

    def __init__(self, backend: str):
        from neo4j_agent_memory import MemoryClient

        self.backend = backend
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()
        self._client = MemoryClient(_settings(backend))
        self._run(self._client.__aenter__())

    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=120)

    def search(self, query: str) -> str:
        """Entities matching the query, each with its relationships, on both backends. On Bolt also facts and messages
        from all earlier sessions: the SDK's NAMS backend has no facts, scopes message search to one conversation, and
        its long-term get_context returns "" by design, so entity search + relationships is the common ground."""
        lines = []
        for entity in self._run(self._client.long_term.search_entities(query, limit=8)):
            lines.append(f"{entity.name} ({entity.type}): {entity.description or ''}".rstrip(": "))
            lines += [f"  {fact}" for fact in self._run(self._relationships(entity))[:12]]
        if self.backend == "aura":  # facts and cross-session message search exist on the Bolt backend only
            for fact in self._run(self._client.long_term.search_facts(query, limit=8, threshold=0.5)):
                since = f" (valid from {fact.valid_from:%Y-%m-%d})" if fact.valid_from else ""
                lines.append(f"fact: {fact.subject} {fact.predicate} {fact.object}{since}")
            messages = self._run(self._client.short_term.search_messages(query, limit=8, threshold=0.5))
            lines += [f"message ({m.role}): {m.content[:400]}" for m in messages]
        return "\n".join(lines) or f"No memories found for '{query}'."

    async def _relationships(self, entity) -> list[str]:
        # Undirected: on Bolt, SDK 0.7.0's get_related_entities matches -[:RELATED_TO]- both ways and always sets
        # source_id to the queried entity, so the stored direction is not available through the public API.
        if self.backend == "aura":
            facts = [(entity.name, rel, other.name) for other, rel in await self._client.long_term.get_related_entities(entity)]
        else:
            rels = await self._client.long_term.get_entity_relationships(entity.id)
            facts = [(entity.name, rel, (rel.attributes or {}).get("target_name") or rel.target_id) for rel in rels]
        return [f"{a} —{rel.type}— {b}" + (f" (until {rel.valid_until:%Y-%m-%d})" if rel.valid_until else "")
                for a, rel, b in facts]

    def close(self) -> None:
        self._run(self._client.__aexit__(None, None, None))
        self._loop.call_soon_threadsafe(self._loop.stop)

    def tools(self) -> list[Tool]:
        def search_memory(
            query: Annotated[str, "What to look up, e.g. 'fraud-api owner' or 'release freeze'."],
        ) -> str:
            """Search long-term memory (Neo4j Agent Memory): earlier conversations, extracted entities with
            their relationships, and facts. Call it again with a different query if the first one misses."""
            return self.search(query)

        return [create_tool_from_function(search_memory)]

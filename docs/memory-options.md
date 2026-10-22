# neo4j-agent-memory on Aura vs. NAMS

Both come from Neo4j Labs and share one data model (short-term conversations, long-term entity graph, reasoning
traces). The difference is who runs it and where the graph lives.

| | **neo4j-agent-memory (SDK) on Aura** | **NAMS** (Neo4j Agent Memory Service) |
|---|---|---|
| What it is | open-source Python/TypeScript library + MCP server ([docs](https://neo4j.com/labs/agent-memory/), [GitHub](https://github.com/neo4j-labs/agent-memory)) | hosted service: REST API, hosted MCP server, console, background workers ([memory.neo4jlabs.com](https://memory.neo4jlabs.com)) |
| Where the graph lives | **your** Neo4j/Aura via Bolt, next to your other data | a NAMS workspace database (free managed Aura, removed after 2 days idle) or your own Neo4j ("External") |
| Graph model | `Conversation -HAS_MESSAGE-> Message -MENTIONS-> Entity`, `Entity -RELATED_TO {type, confidence, evidence, extractor}-> Entity`, `Fact`, `Preference`, `ReasoningTrace` / `ReasoningStep` / `ToolCall` | the same three layers, plus observations and reflections, managed by NAMS |
| Extraction | in the SDK, in your process: spaCy / GLiNER2.5 / LLM (here: LLM via LiteLLM, Azure gpt-5-mini) | in NAMS background workers (spaCy → GLiNER2 → LLM) |
| Ontology | a document (JSON/YAML), `NAM_SCHEMA_CONFIG__ONTOLOGY_PATH`; drives extraction, drops relations without a pattern | workspace ontologies (28 templates incl. "Agent Memory"), versioned, activate one; `nams-default` if none |
| Claude Code | MCP server over stdio: `neo4j-agent-memory mcp serve --backend bolt` (16 tools on Bolt, 6 in the `core` profile); session capture + recall via this repo's `bin/agent-memory-hook` (the SDK ships no Claude Code hooks) | hosted MCP over HTTP with OAuth or API key (47 tools) + `nams-hooks` plugin (automatic capture + recall injection) |
| Who decides what is stored | the agent (tools) + hooks capture prompts, answers, tool calls; the SDK extracts from stored messages | everything is captured by the hooks; the agent can also add entities/relations |
| Corrections | add new facts (`valid_from`) and relations; no MCP tool retires a relation (`valid_until` exists in the model) | add new relations; no MCP tool retires one; entity resolution review (human in the loop) and entity history |
| Inspect | Aura console: Query, Bloom, Dashboards; any Cypher | NAMS console: Entity Explorer, Memory Browser, Observations, Review, Query Console |
| Ops | you run the MCP server and pay for the LLM/embeddings; data stays in your Aura | nothing to run; metering, multi-tenant workspaces, API keys, OAuth |
| Extras | integrations (LangChain, Pydantic AI, Google ADK, CrewAI, Strands, ...), enrichment, geospatial | skill distillation (`SKILL.md` from memory), observations/reflections |

## What the demo showed

Same story, same ontology, fresh sessions, see the [README](../README.md#evaluation-haystack):

- **Ontology-driven extraction works on both.** On Aura, 9 of 13 relations came from the extractor with ontology types
  (`OWNS`, `REPORTS_TO`, `CALLS`, `DEPLOYS_TO`, `AFFECTS`, `DECIDED_FOR`); the agent added the rest itself.
- **Corrections are the weak spot of both.** After "Lena owns fraud-api now", `Jonas OWNS fraud-api` stays live on both
  backends. On Aura the day-2 session also rewrote the entity description and day 3 answered Lena; on NAMS the
  description could not be overwritten and day 3 answered **Jonas**.
- **Cross-agent works.** Claude Code writes, a Haystack agent reads the same memory through the same SDK.

## Connect NAMS in an interactive Claude Code session

[.mcp.json](../.mcp.json) declares `nams` as `{"type": "http", "url": "https://memory.neo4jlabs.com/mcp"}`. Approve it,
then `/mcp` → `nams` → **Authenticate** (OAuth). Details: [setup-nams.md](setup-nams.md#step-4-connect-claude-code).

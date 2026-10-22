# Neo4j Agent Memory for Claude Code and GitHub Copilot

Hacknight demo for [**Graphs Gone Wild**](https://globalai.community/e/ack9t53d) (NODES 2026 pop-up, Global AI Berlin,
23 October 2026).

**The question:** can a coding agent remember a project across sessions, keep a correction, and still say "I don't know"
when it doesn't? With the memory as a graph in Neo4j that other agents and dashboards can read.

**Two ways to give Claude Code Neo4j memory**, same story, same ontology, same evaluation:

| | **1. neo4j-agent-memory on Aura** | **2. NAMS** |
| --- | --- | --- |
| What | Neo4j Labs open-source SDK [`neo4j-agent-memory`](https://neo4j.com/labs/agent-memory/) 0.7.0 with **its own MCP server** (16 tools in the extended Bolt profile) | hosted [Neo4j Agent Memory Service](https://memory.neo4jlabs.com): hosted MCP server (47 tools observed in this setup; visibility depends on deployment and scopes) + `nams-hooks` plugin |
| Where the graph lives | **your Neo4j Aura instance**, next to your data | a NAMS workspace (managed Aura, or bring your own) |
| Extraction | in the SDK (LLM via LiteLLM), driven by the ontology file | in NAMS (background workers), driven by the workspace ontology |
| Claude Code | `.mcp.json` → `bin/agent-memory-mcp` + `bin/agent-memory-hook` (session capture + recall) | `.mcp.json` → `https://memory.neo4jlabs.com/mcp` (OAuth) + `nams-hooks` |
| GitHub Copilot (VS Code) | `.vscode/mcp.json` → the same `bin/agent-memory-mcp` launcher | `.vscode/mcp.json` → the hosted NAMS endpoint (OAuth) |
| Session history | every prompt, answer and tool call as messages + reasoning traces in Aura | every prompt and answer as conversations in NAMS |
| You see it in | Aura console: Query, Bloom, **Dashboards** | NAMS console: Entity Explorer, Memory Browser, Review |
| Setup guide | **[docs/setup-aura.md](docs/setup-aura.md)** | **[docs/setup-nams.md](docs/setup-nams.md)** |

Both use **one ontology**: the NAMS "Agent Memory" template extended with a software team's vocabulary
([ontology/](ontology/)). Pitch script with all links: **[docs/live-demo.md](docs/live-demo.md)**.

## Final results: what to take away

**Memory survived a fresh session and transferred between agents.** Claude Code wrote the project memory;
both Claude Code and a separate Haystack agent could then answer questions from it.

| Memory setup | Claude Code | Haystack | What the audience should notice |
| --- | --- | --- | --- |
| No memory | Not tested | **2/10 (20 %)** | Only the two deliberately unanswerable questions were correct. |
| SDK on our Aura instance | **10/10 (100 %)** | **10/10 (100 %)** | Recalled the project, the corrected owner and the manager; abstained on missing facts. |
| Hosted NAMS workspace | **8/10 (80 %)** | **8/10 (80 %)** | Recalled the project, but used the old owner in two answers affected by the same correction. |

**The lesson is not "Aura always beats NAMS".** This is one fictional story, 10 questions per variant and an LLM judge,
not a general benchmark. Both Aura ownership edges remained live: the successful answers used an updated description
and a dated fact, not automatic retirement of the old relationship. The demo shows that storing memory is useful;
retrieving all relevant memory and resolving conflicting updates are separate engineering tasks.

![Agent Memory on Neo4j Aura](docs/screenshots/setup/aura-5-dashboard.png)

## The story

A fictional team (so no model can answer from pre-training), told to Claude Code over three days
([demo/story.json](demo/story.json); prompts never name a tool):

| Session | Mara says | Memory has to |
| --- | --- | --- |
| Day 1 | Briefing: payments team at Kestrel Labs, checkout-service (FastAPI, Aura `orders-graph`, eu-central-1), fraud-api owned by **Jonas**, Jonas and Lena report to Ines (CTO), ADR-007, release freeze 30 October | store it |
| Day 2 | "fraud-api is owned by **Lena** now, not Jonas" | update it |
| Day 3 | "I'm changing how checkout-service calls fraud scoring: who do I talk to, who is their manager, any deadline?" | answer with 2 hops + the correction: **Lena → Ines, freeze 30 October** |

Both backends keep the full Claude Code session history: `nams-hooks` for NAMS, [bin/agent-memory-hook](bin/agent-memory-hook)
for Aura (the SDK's MCP server alone stores only what the agent sends; the three demo sessions were imported from their
transcripts with [harness/import_transcripts.py](harness/import_transcripts.py)).

Each session is a fresh headless `claude -p` with **no** chat history, **no** Claude Code file memory and **no**
file/shell/web tools ([harness/claude_backends.py](harness/claude_backends.py)). Transcripts:
[demo/transcripts/aura](demo/transcripts/aura/), [demo/transcripts/nams](demo/transcripts/nams/).

| Day 3 on Aura (neo4j-agent-memory) | Day 3 on NAMS |
| --- | --- |
| ![Aura](docs/screenshots/setup/aura-2-claude-code.png) | ![NAMS](docs/screenshots/setup/nams-4-claude-code.png) |

## Evaluation (Haystack)

[eval/eval_memory.py](eval/eval_memory.py): 10 questions ([eval/questions.json](eval/questions.json)): 4 single-hop,
3 multi-hop, 1 correction, 2 *not in memory* (the right answer is "I don't know"). An LLM judge (Haystack chat
generator, JSON mode) compares each answer with the reference. The Haystack agents read memory through the **same SDK**
for both backends ([harness/memory_tools.py](harness/memory_tools.py)): `MemorySettings(backend="bolt")` for Aura,
`backend="nams"` for NAMS. All eval runs are read-only (and the NAMS hooks are off, or every question would be stored).

| Variant | What answers | Memory |
| --- | --- | --- |
| `no_memory` | Haystack Agent, no tools | baseline |
| `haystack_aura` | Haystack Agent + neo4j-agent-memory (Bolt) | Aura, **written by Claude Code** |
| `claude_code_aura` | fresh `claude -p` + the SDK's MCP server (read tools) | Aura |
| `haystack_nams` | Haystack Agent + neo4j-agent-memory (NAMS backend) | NAMS, **written by Claude Code** |
| `claude_code_nams` | fresh `claude -p` + hosted NAMS MCP (read tools) | NAMS |

Results of the run in this repo (22 October 2026, one run per variant; Claude Sonnet for Claude Code, Azure OpenAI
gpt-5-mini for extraction, the Haystack agents and the judge):

| Variant | Overall | Single-hop (4) | Multi-hop (3) | Correction (1) | Not in memory (2) |
| --- | --- | --- | --- | --- | --- |
| `no_memory` | 20 % | 0 % | 0 % | 0 % | 100 % |
| `haystack_aura` | **100 %** | 100 % | 100 % | 100 % | 100 % |
| `claude_code_aura` | **100 %** | 100 % | 100 % | 100 % | 100 % |
| `haystack_nams` | 80 % | 100 % | 67 % | 0 % | 100 % |
| `claude_code_nams` | 80 % | 100 % | 67 % | 0 % | 100 % |

Both NAMS misses are the same story: *"who owns fraud-api?"* and *"does Jonas still own it?"* are answered with Jonas.
After the correction, NAMS holds `Lena OWNS fraud-api` **and** the original `Jonas OWNS fraud-api`, and the extracted
entity description still says "owned by Jonas"; the tools used in this run did not reconcile them. On Aura both
`OWNS` edges are live too, but the day-2 session rewrote the entity description and stored a fact with `valid_from`,
which is what the readers found. This compares two configured memory workflows, not identical write capabilities:
the [backend reference](https://neo4j.com/labs/agent-memory/reference/backend-capabilities/) documents structured facts
and direct relationship creation on Bolt, but not through the NAMS Python wrappers.

`haystack_aura` scored 80 % in the first run: the demo's Haystack tool searched entities and messages but not **facts**
(the freeze date and the ADR-007 reason were stored as facts). With `search_facts` added it scored 100 %. With 10
questions and one run, one answer is 10 points.

![Eval](docs/screenshots/setup/aura-6-eval.png)

**Reading the evaluation chart:** the left chart has one light-blue accuracy bar per variant. In the saved chart on
the right, **light blue = multi-hop**, **dark blue = single-hop**, **orange = correction**, and **pink = not in memory**.
These colors identify question types, not Aura versus NAMS. A missing correction bar means **0 %**, not an untested
category; both NAMS variants have 2/3 multi-hop answers correct and 0/1 corrections correct.

After importing the three Claude Code sessions into Aura (prompts, answers, 30 tool calls) the two Aura variants were
rerun: still 100 %, and the eval left the memory untouched (hooks off, read-only tools).

Results go to Aura as `(:DemoEvalVariant)-[:ANSWERED {correct, answer, reason}]->(:DemoEvalQuestion)` and onto the
dashboard. Raw answers and judge reasons: [eval/results/eval_results.json](eval/results/eval_results.json).

## The graph and its vocabulary

### Aura: inspect what is stored

![Aura Query schema overview showing memory, reasoning, GraphRAG and evaluation labels](docs/screenshots/setup/aura-9-data-model.png)

The supplied Aura screenshot runs **`CALL db.schema.visualization()`** on the shared `GraphRAG-agent-memory` instance.
It brings three kinds of records into view: conversations and messages; entities and facts; and recorded reasoning
steps, tool calls and tools. `HAS_MESSAGE` connects conversations to messages, `MENTIONS` connects messages to entities,
and `RELATED_TO` connects entities, with the domain relationship name (such as `OWNS`) stored in its `type` property.
These links make memory inspectable beyond the chat window. Recorded tool activity is an application trace, not the
model's hidden chain of thought ([official memory model](https://neo4j.com/labs/agent-memory/)).

**Read the counts carefully:** the sidebar reports **281 stored nodes and 551 relationships** for this database
snapshot; the **24 nodes** in the result are virtual schema nodes representing labels, not 24 project entities.
`HaystackDocument`, `GraphRagChunk` and evaluation labels appear because this database also holds workshop and test
data. This is not a memory-only count. Neo4j's
[procedure documentation](https://neo4j.com/docs/operations-manual/current/procedures/#procedure_db_schema_visualization)
also warns that the default statistics-based schema view can show relationship combinations absent from the data.
Use a targeted data query to verify a specific ownership edge.

### NAMS: configure what can be extracted

![NAMS ontology library and diagram with nams-default revision r3 active in permissive mode](docs/screenshots/setup/nams-7-ontology-library.png)

The supplied NAMS screenshot shows the ontology library on the left, a vocabulary diagram in the center, and a
property inspector on the right. The visible tabs list **13 entity types and 14 relationships**, including concepts
such as `Person`, `Service`, `Database`, `Organization` and `Decision`. Nodes here represent **types**, and arrows
represent declared relationship patterns, not the people and services remembered from our three sessions.
Node colors distinguish types; they are not the blue-bar provenance or accuracy encodings in the dashboard charts.

**Configuration matters:** the banner in this screenshot says **`nams-default`, revision `r3`, permissive**.
It illustrates the ontology UI, but does not show the demo's custom ontology activated. For the evaluated setup we
used [agent-memory-software-team.json](ontology/agent-memory-software-team.json); the separate
[activated custom-ontology screenshot](docs/screenshots/setup/nams-3-ontology-active.png) shows
`agent-memory-software-team`, revision `r1` (14 entity types, 29 relationships). Verify the active ontology in the
workspace used for a run. The [official ontology guide](https://neo4j.com/labs/agent-memory/explanation/ontologies/)
distinguishes templates, active versions and migration: changing a vocabulary does not by itself reconcile old claims.

## Aura dashboard

[dashboard/dashboard.cypher](dashboard/dashboard.cypher) → [dashboard/build_dashboard.py](dashboard/build_dashboard.py)
→ Aura console → Dashboards → Import. Live (project members):
**[Agent Memory on Neo4j Aura](https://console.neo4j.io/projects/326809f3-c351-4eb7-8770-fcf5d0b6adc1/studio/dashboards/yCfaWsVBltViYPw7jRcS)** and the workshop's
[Haystack GraphRAG on Neo4j](https://console.neo4j.io/projects/326809f3-c351-4eb7-8770-fcf5d0b6adc1/studio/dashboards/oZVFPdtMHufwLxAT7hbo).

| History page (Claude Code sessions) | Ontology page |
| --- | --- |
| ![History](docs/screenshots/setup/aura-8-history.png) | ![Ontology](docs/screenshots/setup/aura-7-ontology.png) |

**Reading the ontology chart:** in "Relationship types: extracted vs agent", **light blue / turquoise = `extracted`**
(relationships with an `extractor` property), and **dark blue / indigo = `agent`** (no `extractor` property, treated as
direct agent writes in this demo). The vertical axis counts stored relationships, not accuracy or confidence.
For example, the saved `OWNS` bar contains one extracted edge and one agent-added edge: the original owner and the
correction coexist. The query classifies provenance from metadata; missing metadata is not a universal proof of an
agent write. See query **O2** in [dashboard/dashboard.cypher](dashboard/dashboard.cypher).

The workshop dashboard this demo builds on (GraphRAG vs. vector RAG on the same Aura instance):

![Haystack GraphRAG workshop dashboard](docs/screenshots/aura-graphrag-workshop.png)

## What we learned building it

Rechecked against the maintainers' documentation on **22 October 2026**, for **Python SDK 0.7.0**. Below, "observed"
means this demo's behavior, not a guarantee about every deployment. Both options are Neo4j Labs projects; the
[SDK documentation](https://neo4j.com/labs/agent-memory/) explicitly notes that Labs offers no support SLA or backwards
compatibility guarantee.

1. **An ontology must match the extracted types.** Observed: `fraud-api` landed as `:Entity:Object`; an `OWNS` pattern
   targeting only `Service` dropped the correction, while an additional `Object` pattern kept it
   ([our ontology notes](ontology/README.md)). The
   [official extraction guide](https://neo4j.com/labs/agent-memory/how-to/ontology-driven-extraction/) confirms that
   forbidden extracted relationships are dropped in **both** permissive and strict mode. It also documents custom
   labels through explicit POLE type/subtype mappings, so "the SDK only supports POLE labels" would be too broad.
   Validate the ontology and inspect the labels actually stored before trusting extraction.

2. **Recording a correction is not the same as superseding the old claim.** Observed: both graphs retained both
   ownership edges; Aura's updated description and dated fact were enough for correct answers in this run. The
   [self-hosted MCP reference](https://neo4j.com/labs/agent-memory/reference/mcp-tools/) exposes fact validity bounds,
   but no relationship-retirement tool. The [Bolt relationship API](https://neo4j.com/labs/agent-memory/reference/api/long-term-entities/)
   accepts `valid_from` / `valid_until`, and direct Bolt writes allow an application to maintain historical edges.
   NAMS also documents **`PUT /v1/entities/{id}`** for entity updates in its
   [REST reference](https://neo4j.com/labs/agent-memory/reference/rest-api/); that is not an edge-retirement API or a
   public Python `update_entity` wrapper. The [hosted MCP inventory](https://neo4j.com/labs/agent-memory/reference/nams-mcp/)
   is deployment- and scope-dependent. Define and test a correction policy; do not conclude that NAMS can never update memory.

3. **Retrieve facts explicitly.** Our first Haystack/Aura run missed the freeze date and ADR reason until we added
   `search_facts`. The [official context API](https://neo4j.com/labs/agent-memory/reference/api/memory-client/) says
   Bolt's assembled long-term context contains entities and preferences, **not facts**. The
   [fact API](https://neo4j.com/labs/agent-memory/reference/api/long-term-preferences/) provides `search_facts` and
   `get_facts_about`. A stored fact cannot help an answer if the retrieval path never reads it; validity timestamps
   alone also do not define which conflicting claim wins.

4. **Check model parameters before blaming extraction.** Observed: the SDK's `temperature=0.0` failed with our
   Azure OpenAI `gpt-5-mini` deployment. Microsoft's
   [reasoning-model guidance](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/reasoning) documents
   unsupported sampling parameters; [LiteLLM documents `drop_params=True`](https://docs.litellm.ai/docs/completion/drop_params)
   to omit unsupported parameters. Our launcher uses `LITELLM_DROP_PARAMS=true`
   ([bin/agent-memory-mcp](bin/agent-memory-mcp)). This is a workaround for this provider/model combination, not a
   universal requirement for every extractor. Verify extraction produced entities and evidence, not just a successful chat reply.

5. **A fresh chat is not an isolated evaluation.** Observed: earlier sessions answered from Claude's local notes or
   repository files. [Claude Code's memory documentation](https://code.claude.com/docs/en/memory#enable-or-disable-auto-memory)
   documents **both** `autoMemoryEnabled: false` and `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` as supported ways to disable
   auto memory. Our earlier environment-variable-only attempt is not proof of a general headless limitation.
   Disable auto memory and exclude file/shell/web tools and other answer-bearing context; inspect the tool transcript.

6. **Capture hooks can contaminate the test set.** Observed: enabled `nams-hooks` stored evaluation questions and
   answers as new memory. [Claude Code's hook reference](https://code.claude.com/docs/en/hooks#disable-or-remove-hooks)
   documents `disableAllHooks: true`; hooks run at configured lifecycle events, not only when the model chooses a
   memory tool. Keep capture on for the story and off for evaluation, alongside a read-only tool allowlist.
   Managed hooks need separate policy review because user-level settings cannot disable them.

7. **Read-only is not the same as isolated.** The
   [MCP reference](https://neo4j.com/labs/agent-memory/reference/mcp-tools/) says `graph_query` blocks writes; it does
   not hide evaluation labels or reference answers stored in the same authorized database. The
   [scope reference](https://neo4j.com/labs/agent-memory/reference/backend-capabilities/) warns that session IDs and
   context retrieval are not authorization boundaries. Exclude raw Cypher from the evaluation tools and separate
   answer keys from agent-readable memory; use database permissions or separate databases/workspaces for isolation.

8. **Backend compatibility does not mean identical retrieval.** The
   [NAMS wrapper reference](https://neo4j.com/labs/agent-memory/reference/api/long-term-geospatial/) confirms that
   `long_term.get_context()` returns `""`; use workspace entity search and explicit conversation context. The
   [capability reference](https://neo4j.com/labs/agent-memory/reference/backend-capabilities/) confirms that NAMS
   message search requires a conversation ID. Separately, our 0.7.0 neighbor readback lost edge direction through
   `get_related_entities`; the [relationship reference](https://neo4j.com/labs/agent-memory/reference/api/long-term-entities/)
   documents source/target fields but does **not** establish this as an intended limitation. Treat it as an observed
   readback issue, verify direction against stored edges, and report a minimal reproduction before generalizing.

## Run it

```bash
git clone https://github.com/ma3u/neo4j-aura-agent-memory-demo && cd neo4j-aura-agent-memory-demo
python3.12 -m venv venv && venv/bin/pip install -r requirements.txt
cp .env.example .env                                   # Aura, NAMS key, Azure OpenAI (or OpenAI)
venv/bin/python demo/run_sessions.py --backend aura    # 3 Claude Code sessions -> neo4j-agent-memory on Aura
venv/bin/python demo/run_sessions.py --backend nams    # the same through NAMS
venv/bin/python eval/eval_memory.py                    # Haystack eval, results -> Aura
venv/bin/python dashboard/build_dashboard.py           # -> dashboard/aura_dashboard.json
```

Check both setups (read-only, nothing is written): `venv/bin/python demo/check_setup.py`.

Interactive: open Claude Code in this folder, approve `agent-memory` and `nams` from `.mcp.json`, authenticate `nams`
via `/mcp`, and tell it something worth remembering.

## GitHub Copilot in VS Code

[.vscode/mcp.json](.vscode/mcp.json) registers both memory servers for VS Code's local agent tools. It uses VS Code's
`servers` format, while [.mcp.json](.mcp.json) retains the `mcpServers` format for Claude Code and compatible clients.
See the [official VS Code MCP setup guide](https://code.visualstudio.com/docs/copilot/customization/mcp-servers).

1. Complete the dependencies and credentials in [the Aura setup](docs/setup-aura.md), or prepare your workspace with
   [the NAMS setup](docs/setup-nams.md). Open this repository's root folder in VS Code.
2. Open [.vscode/mcp.json](.vscode/mcp.json) and use **Start**, or run **MCP: List Servers** from the Command Palette.
   Review the server configuration and accept VS Code's trust prompt to start the backend you want to use.
3. For **`agent-memory`**, VS Code launches `${workspaceFolder}/bin/agent-memory-mcp`. The launcher reads the local
   `.env` and uses the existing `venv`; no credentials are stored in the committed MCP configuration. Its first
   start can initialize the SDK's schema and indexes in your Aura database.
4. For **`nams`**, complete the browser OAuth sign-in and select the intended workspace when prompted. The hosted
   service manages extraction; it does not use the local Aura launcher.
5. In Copilot Chat, choose an agent session that supports tools and enable the selected server in the tools picker.
   Use one backend at a time when comparing results. On versions offering multiple harnesses, use the **Local**
   harness for this VS Code configuration. Other harnesses have their own configuration destinations, as described
   in the official guide.

For a read-only connection check, ask Copilot:

```text
Use only the agent-memory MCP tools to find who owns fraud-api, who their manager is,
and when the release freeze starts. Report conflicting claims or missing information.
Do not read repository files, run shell commands, or write new memory.
```

For NAMS, replace `agent-memory` with `nams`. Expand the tool call to verify the intended MCP server actually
returned the evidence. On this shared demo database, leave `graph_query` disabled so it cannot read evaluation
reference answers.

**MCP access is not automatic session capture.** Copilot can recall existing memory and explicitly store messages
through the server's tools. This configuration does not install Copilot capture hooks or reuse Claude Code's
`nams-hooks` plugin. The evaluation above covers Claude Code and Haystack, **not Copilot**.

## Layout

| Path | What |
| --- | --- |
| [.vscode/mcp.json](.vscode/mcp.json) | GitHub Copilot / VS Code MCP connections for Aura and NAMS |
| [bin/agent-memory-mcp](bin/agent-memory-mcp) | starts the SDK's MCP server on Aura (`neo4j-agent-memory mcp serve --backend bolt`) |
| [bin/agent-memory-hook](bin/agent-memory-hook) | Claude Code hook: captures sessions into Aura through the SDK, injects recall (daemon: `harness/aura_hooks_daemon.py`, importer: `harness/import_transcripts.py`) |
| [ontology/](ontology/) | the shared ontology (NAMS "Agent Memory" template + software team) |
| [harness/](harness/) | Claude Code flags per backend, the SDK as a Haystack tool, the hook daemon, the transcript importer, the LLM factory |
| [demo/](demo/) | story, session runner, smoke test (`check_setup.py`), NAMS MCP config, transcripts |
| [eval/](eval/) | questions, Haystack eval, results |
| [dashboard/](dashboard/) | dashboard queries, generator, import JSON |
| [docs/](docs/) | setup guides, live demo runbook, comparison, screenshots |

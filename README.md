# Neo4j Agent Memory for Claude Code: on your Aura, or as a service

Hacknight demo for [**Graphs Gone Wild**](https://globalai.community/e/ack9t53d) (NODES 2026 pop-up, Global AI Berlin,
23 October 2026).

**The question:** can a coding agent remember a project across sessions, keep a correction, and still say "I don't know"
when it doesn't? With the memory as a graph in Neo4j that other agents and dashboards can read.

**Two ways to give Claude Code Neo4j memory**, same story, same ontology, same evaluation:

| | **1. neo4j-agent-memory on Aura** | **2. NAMS** |
|---|---|---|
| What | Neo4j Labs open-source SDK [`neo4j-agent-memory`](https://neo4j.com/labs/agent-memory/) 0.7.0 with **its own MCP server** (16 tools), Bolt backend | hosted [Neo4j Agent Memory Service](https://memory.neo4jlabs.com): hosted MCP server (47 tools) + `nams-hooks` plugin |
| Where the graph lives | **your Neo4j Aura instance**, next to your data | a NAMS workspace (managed Aura, or bring your own) |
| Extraction | in the SDK (LLM via LiteLLM), driven by the ontology file | in NAMS (background workers), driven by the workspace ontology |
| Claude Code | `.mcp.json` → `bin/agent-memory-mcp` | `.mcp.json` → `https://memory.neo4jlabs.com/mcp` (OAuth) + hooks |
| You see it in | Aura console: Query, Bloom, **Dashboards** | NAMS console: Entity Explorer, Memory Browser, Review |
| Setup guide | **[docs/setup-aura.md](docs/setup-aura.md)** | **[docs/setup-nams.md](docs/setup-nams.md)** |

Both use **one ontology**: the NAMS "Agent Memory" template extended with a software team's vocabulary
([ontology/](ontology/)). Pitch script with all links: **[docs/live-demo.md](docs/live-demo.md)**.

**Result** (10 questions, fresh sessions, LLM judge): without memory 20 % (only the "I don't know" answers);
**neo4j-agent-memory on Aura 100 %** for both Claude Code and a Haystack agent reading the same memory; **NAMS 80 %** for
both: everything except the correction. Same ontology, same story; the difference is how a correction survives.

![Agent Memory on Neo4j Aura](docs/screenshots/setup/aura-5-dashboard.png)

## The story

A fictional team (so no model can answer from pre-training), told to Claude Code over three days
([demo/story.json](demo/story.json); prompts never name a tool):

| Session | Mara says | Memory has to |
|---|---|---|
| Day 1 | Briefing: payments team at Kestrel Labs, checkout-service (FastAPI, Aura `orders-graph`, eu-central-1), fraud-api owned by **Jonas**, Jonas and Lena report to Ines (CTO), ADR-007, release freeze 30 October | store it |
| Day 2 | "fraud-api is owned by **Lena** now, not Jonas" | update it |
| Day 3 | "I'm changing how checkout-service calls fraud scoring: who do I talk to, who is their manager, any deadline?" | answer with 2 hops + the correction: **Lena → Ines, freeze 30 October** |

Each session is a fresh headless `claude -p` with **no** chat history, **no** Claude Code file memory and **no**
file/shell/web tools ([harness/claude_backends.py](harness/claude_backends.py)). Transcripts:
[demo/transcripts/aura](demo/transcripts/aura/), [demo/transcripts/nams](demo/transcripts/nams/).

| Day 3 on Aura (neo4j-agent-memory) | Day 3 on NAMS |
|---|---|
| ![Aura](docs/screenshots/setup/aura-2-claude-code.png) | ![NAMS](docs/screenshots/setup/nams-4-claude-code.png) |

## Evaluation (Haystack)

[eval/eval_memory.py](eval/eval_memory.py): 10 questions ([eval/questions.json](eval/questions.json)): 4 single-hop,
3 multi-hop, 1 correction, 2 *not in memory* (the right answer is "I don't know"). An LLM judge (Haystack chat
generator, JSON mode) compares each answer with the reference. The Haystack agents read memory through the **same SDK**
for both backends ([harness/memory_tools.py](harness/memory_tools.py)): `MemorySettings(backend="bolt")` for Aura,
`backend="nams"` for NAMS. All eval runs are read-only (and the NAMS hooks are off, or every question would be stored).

| Variant | What answers | Memory |
|---|---|---|
| `no_memory` | Haystack Agent, no tools | baseline |
| `haystack_aura` | Haystack Agent + neo4j-agent-memory (Bolt) | Aura, **written by Claude Code** |
| `claude_code_aura` | fresh `claude -p` + the SDK's MCP server (read tools) | Aura |
| `haystack_nams` | Haystack Agent + neo4j-agent-memory (NAMS backend) | NAMS, **written by Claude Code** |
| `claude_code_nams` | fresh `claude -p` + hosted NAMS MCP (read tools) | NAMS |

Results of the run in this repo (22 October 2026, one run per variant; Claude Sonnet for Claude Code, Azure OpenAI
gpt-5-mini for extraction, the Haystack agents and the judge):

| Variant | Overall | Single-hop (4) | Multi-hop (3) | Correction (1) | Not in memory (2) |
|---|---|---|---|---|---|
| `no_memory` | 20 % | 0 % | 0 % | 0 % | 100 % |
| `haystack_aura` | **100 %** | 100 % | 100 % | 100 % | 100 % |
| `claude_code_aura` | **100 %** | 100 % | 100 % | 100 % | 100 % |
| `haystack_nams` | 80 % | 100 % | 67 % | 0 % | 100 % |
| `claude_code_nams` | 80 % | 100 % | 67 % | 0 % | 100 % |

Both NAMS misses are the same story: *"who owns fraud-api?"* and *"does Jonas still own it?"* are answered with Jonas.
After the correction, NAMS holds `Lena OWNS fraud-api` **and** the original `Jonas OWNS fraud-api`, and the extracted
entity description still says "owned by Jonas"; nothing in the MCP tools can retire or overwrite them. On Aura both
`OWNS` edges are live too, but the day-2 session rewrote the entity description and stored a fact with `valid_from`,
which is what the readers found.

`haystack_aura` scored 80 % in the first run: the demo's Haystack tool searched entities and messages but not **facts**
(the freeze date and the ADR-007 reason were stored as facts). With `search_facts` added it scored 100 %. With 10
questions and one run, one answer is 10 points.

![Eval](docs/screenshots/setup/aura-6-eval.png)

Results go to Aura as `(:DemoEvalVariant)-[:ANSWERED {correct, answer, reason}]->(:DemoEvalQuestion)` and onto the
dashboard. Raw answers and judge reasons: [eval/results/eval_results.json](eval/results/eval_results.json).

## Aura dashboard

[dashboard/dashboard.cypher](dashboard/dashboard.cypher) → [dashboard/build_dashboard.py](dashboard/build_dashboard.py)
→ Aura console → Dashboards → Import. Live (project members):
**[Agent Memory on Neo4j Aura](https://console.neo4j.io/projects/326809f3-c351-4eb7-8770-fcf5d0b6adc1/studio/dashboards/5liMFJOPMbPfXN4fxBwy)** and the workshop's
[Haystack GraphRAG on Neo4j](https://console.neo4j.io/projects/326809f3-c351-4eb7-8770-fcf5d0b6adc1/studio/dashboards/oZVFPdtMHufwLxAT7hbo).

| Ontology page | Eval page |
|---|---|
| ![Ontology](docs/screenshots/setup/aura-7-ontology.png) | ![Eval](docs/screenshots/setup/aura-6-eval.png) |

The workshop dashboard this demo builds on (GraphRAG vs. vector RAG on the same Aura instance):

![Haystack GraphRAG workshop dashboard](docs/screenshots/aura-graphrag-workshop.png)

## What we learned building it

1. **Use an ontology, and match it to how the extractor labels things.** The SDK stores entities with their POLE label
   (`fraud-api` becomes `:Entity:Object`). With only `(Person)-[:OWNS]->(Service)` in the ontology, "Lena owns fraud-api"
   was silently dropped; adding the `Object` pattern kept it. ([ontology/README.md](ontology/README.md))
2. **Corrections are the hard part, on both backends.** Neither MCP server can retire a relationship, so the old owner
   stays live next to the new one.
3. **gpt-5-mini + the SDK needs `LITELLM_DROP_PARAMS=true`.** The SDK sends `temperature=0.0`, the model rejects it, and
   extraction fails; Claude then entered everything by hand. ([bin/agent-memory-mcp](bin/agent-memory-mcp))
4. **A "fresh" Claude Code session is not fresh.** Claude Code's own file memory (`~/.claude/projects/<project>/memory/`)
   wrote notes in a first run and the next session answered from them. `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` alone did not
   stop it headless; `autoMemoryEnabled: false` plus no file tools did. With `Read` allowed, a session also found the
   answers in this repo.
5. **Hooks capture everything, including your eval.** With `nams-hooks` on, every eval question and answer became new
   memory. Eval runs need the hooks off and read-only tools; demo runs from before isolation polluted a first workspace
   (entities like "Grep" and "day-1.md"), so the demo uses a fresh one.
6. **Don't give a memory agent `graph_query` on a shared database.** The SDK's raw Cypher tool reads everything in Aura,
   here including the eval's reference answers.
7. **SDK 0.7.0 details:** relations read back through `get_related_entities` lose their direction; on the NAMS backend
   `long_term.get_context` returns `""` by design and message search is per conversation, so cross-session recall goes
   through entity search.

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

Interactive: open Claude Code in this folder, approve `agent-memory` and `nams` from `.mcp.json`, authenticate `nams`
via `/mcp`, and tell it something worth remembering.

## Layout

| Path | What |
|---|---|
| [bin/agent-memory-mcp](bin/agent-memory-mcp) | starts the SDK's MCP server on Aura (`neo4j-agent-memory mcp serve --backend bolt`) |
| [ontology/](ontology/) | the shared ontology (NAMS "Agent Memory" template + software team) |
| [harness/](harness/) | Claude Code flags per backend, the SDK as a Haystack tool, the LLM factory |
| [demo/](demo/) | story, session runner, NAMS MCP config, transcripts |
| [eval/](eval/) | questions, Haystack eval, results |
| [dashboard/](dashboard/) | dashboard queries, generator, import JSON |
| [docs/](docs/) | setup guides, live demo runbook, comparison, screenshots |

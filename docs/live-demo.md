<!-- markdownlint-configure-file { "MD033": { "allowed_elements": ["img"] } } -->

# Live demo runbook (Graphs Gone Wild, 23 Oct 2026, demo pitches 20:00)

Five minutes, two memories, one story. Everything below is clickable; the Aura links work for members of the Aura
project, the NAMS links for the workspace owner.

## Before the pitch (15 min)

| Check | How |
|---|---|
| Everything at once (read-only, ~1 min) | `venv/bin/python demo/check_setup.py` → `17/17 checks passed` |
| Aura instance running | [Aura console → Instances](https://console.neo4j.io/projects/326809f3-c351-4eb7-8770-fcf5d0b6adc1/instances): `GraphRAG-agent-memory` **RUNNING** |
| NAMS workspace alive (free DBs are removed after 2 days idle) | [NAMS dashboard](https://memory.neo4jlabs.com/dashboard), workspace `hacknight-demo` |
| Claude Code sees both servers | `claude` in the repo → `/mcp`: `agent-memory` connected (16 tools), `nams` connected (47 tools; authenticate once) |
| Tabs open | Aura dashboard · Aura Query · NAMS Entity Explorer · NAMS Ontologies · this repo's README |

## The pitch

**1. The problem (30 s).** Coding agents forget everything between sessions. The memory should be a graph: connected,
correctable, explainable, and shared with other agents.

**2. One story, three sessions (60 s).** Show [demo/story.json](../demo/story.json): day 1 briefing, day 2 correction
(fraud-api moves from Jonas to Lena), day 3 a question that needs two hops. Each day is a fresh `claude -p` with no file
access and no chat history. Optional live run (2-3 min per backend):

```bash
venv/bin/python demo/run_sessions.py --backend aura --only day-3
```

**3. Memory 1: neo4j-agent-memory on Aura (60 s).**
- [Aura dashboard](https://console.neo4j.io/projects/326809f3-c351-4eb7-8770-fcf5d0b6adc1/studio/dashboards/yCfaWsVBltViYPw7jRcS) → "Agent Memory on Neo4j Aura": the
  memory graph, the day-3 path checkout-service → fraud-api → Lena → Ines, and the card "who owns fraud-api?"
  (both Jonas and Lena are live: the correction added, it did not retire).
- History page: the three Claude Code sessions as conversations and reasoning traces (every tool call), captured by
  `bin/agent-memory-hook`.
- Ontology page: which relationships the ontology-driven extractor produced (`OWNS`, `REPORTS_TO`, `CALLS`, ...) and
  which the agent added itself, with the evidence sentence.
- Say: *same Aura instance as the GraphRAG data from the workshop: memory sits next to your data, Cypher and
  dashboards work on it.*

**4. Memory 2: NAMS (60 s).**
- [Ontologies](https://memory.neo4jlabs.com/dashboard/ontologies): "Agent Memory + Software Team" active, the same file
  as on Aura.
- [Entity Explorer](https://memory.neo4jlabs.com/dashboard/entities) and
  [Memory Browser](https://memory.neo4jlabs.com/dashboard/memory): what the hooks captured and NAMS extracted.
- Say: *zero setup, everything captured automatically, a console to review; but day 3 answered "Jonas": the stale
  owner won, because nothing can retire the old relation.*

**5. The numbers (30 s).** Eval page of the dashboard: no memory vs. each backend, Haystack agent vs. Claude Code, per
question type. See the [README](../README.md#evaluation-haystack) table.

**6. Takeaways (30 s).**
- Memory as a graph works across sessions **and** across agents (Claude Code writes, a Haystack agent reads).
- Use an ontology: it decides which relations survive extraction.
- Corrections are the hard part: both backends keep the old fact next to the new one today.
- Test memory honestly: switch off the agent's own file memory and file access, or it "remembers" from elsewhere.

## Share the repository

[<img src="repo-qr.png" alt="Repository QR code" width="160" height="160" align="middle">](https://github.com/ma3u/neo4j-aura-agent-memory-demo)
Scan or open the [GitHub repository](https://github.com/ma3u/neo4j-aura-agent-memory-demo) for the code and setup guides.

## If something breaks

| Symptom | Fix |
|---|---|
| `agent-memory` not connected | `bin/agent-memory-mcp` by hand: needs `.env`; first start downloads the embedding model |
| No recall injected / sessions not captured in Aura | `curl -s 127.0.0.1:8787` (daemon up?), log: `$TMPDIR/agent-memory-hook.log` |
| Extraction errors mentioning `temperature` | `LITELLM_DROP_PARAMS=true` (set by the launcher) |
| `nams` asks to authenticate | `/mcp` → `nams` → Authenticate (OAuth) |
| NAMS workspace gone (2 days idle) | create a new one: [setup-nams.md](setup-nams.md) steps 1-3, rerun `demo/run_sessions.py --backend nams` |
| No network | screenshots in [docs/screenshots/](screenshots/) and transcripts in [demo/transcripts/](../demo/transcripts/) |

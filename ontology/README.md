# One ontology for both backends

[agent-memory-software-team.json](agent-memory-software-team.json) is the NAMS **"Agent Memory"** template
(`agent-memory`, revision 1, permissive: `Agent`, `Conversation`, `Memory`, `ToolCall`, `Session` on the POLE types
`Person`, `Organization`, `Location`, `Object`, `Event`) plus the vocabulary of a software team:

| Added entity types | Added relationships |
|---|---|
| `Service` (POLE `OBJECT`), `Team` (`ORGANIZATION`), `Decision` (`EVENT`) | `OWNS`, `REPORTS_TO`, `LEADS`, `PART_OF`, `BUILDS`, `CALLS`, `STORES_DATA_IN`, `DEPLOYS_TO`, `DECIDED_FOR`, `AFFECTS` |

The same file is used by

- **neo4j-agent-memory on Aura**: `NAM_SCHEMA_CONFIG__ONTOLOGY_PATH` in [bin/agent-memory-mcp](../bin/agent-memory-mcp)
  and [harness/memory_tools.py](../harness/memory_tools.py). Check it with
  `venv/bin/neo4j-agent-memory ontology validate ontology/agent-memory-software-team.json`.
- **NAMS**: created and activated in the workspace (`POST /v1/ontologies`, then `POST /v1/ontologies/active`), visible
  under Build → Ontologies.

Why the relationships appear twice (e.g. `(Person)-[:OWNS]->(Service)` and `(Person)-[:OWNS]->(Object)`): the SDK's
extractor stores entities with their POLE label (`fraud-api` becomes `:Entity:Object`), and a relation is only kept when
it matches a pattern. With the `Service` pattern alone, "Lena owns fraud-api" was dropped; the `Object` pattern keeps it.

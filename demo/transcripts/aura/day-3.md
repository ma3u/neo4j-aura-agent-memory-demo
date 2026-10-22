# Day 3: a question that needs the graph (aura)

**Prompt**

> I'm about to change how checkout-service calls fraud scoring. Using only your long-term memory: who do I need to talk to, who is their manager, and is there a deadline I should know about?

**Memory tool calls (neo4j-agent-memory MCP -> Neo4j Aura)**

- `memory_search(query='checkout-service fraud scoring owner contact manager deadline', memory_types=['messages', 'entities', 'preferences'], threshold=0.5)`
  - {"result":"{\"results\": {\"messages\": [{\"id\": \"02b678e9-4d66-4e81-8972-38f29966823d\", \"role\": \"user\", \"content\": \"Briefing from Mara (leads the payments team at Kestrel Labs): checkout-service is built in Python 3.12 with FastAPI. It stores orders in the Neo4j Aura instance orders-graph. It calls fraud-api for fraud scoring; fraud-api is owned by Jonas. Jonas and Lena both report to Ines, the CTO. checkout-service deploys to AWS eu-central-1 via GitHub Actions. Decision ADR-007: chose Neo4j over Postgres for orders because fraud rings (order -> customer -> device -> order) need multi-hop queries. The release freeze starts on 30 October.\", \"timestamp\": \"2026-10-22T12:42:19.592000+00:00\", \"similarity\": 0.8574835062026978}], \"entities\": [{\"id\": \"f95a5507-7f6d-4d1c-95eb-e9b320a022d9\", \"name\": \"checkout-service\", \"type\": \"OBJECT\", \"description\": \"Python 3.12 / FastAPI service; deploys to AWS eu-central-1 via GitHub Actions\"}, {\"id\": \"9e78af58-ae64-4300-a8b6-d50f9fc28fe0\", \"name\": \"fraud-api\", \"type\": \"OBJECT\", \"description\": \"Fraud scoring service, owned by Lena (previously Jonas, changed week of 2026-10-22 per Mara)\"}, {\"id\": \"89c9313e-ea7f-4da7-bf34-a6ec0f20e96d\", \"name\": \"payments team\", \"type\": \"ORGANIZATION\", \"description\": null}, {\"id\": \"88bce2ca-fffb-499f-8b3a-85f3a7bf93b1\", \"name\": \"ADR-007\", \"type\": \"EVENT\", \"description\": null}, {\"id\": \"341abb6a-eca5-4222-88f9-f336dd3f3420\", \"name\": \
- `memory_get_context(query='checkout-service fraud scoring')`
  - {"result":"{\"session_id\": \"4f2bf1e5-9220-4b5c-a696-6a6d4eaf022a\", \"context\": \"## Conversation History\\n\\n### Relevant Past Messages\\n- [user] Briefing from Mara (leads the payments team at Kestrel Labs): checkout-service is built in Python 3.12 with FastAPI. It stores orders in the Neo4j Aura instance orders-graph. It calls fraud-api for fraud scoring; fraud-api is owned by Jonas. Jonas and Lena both report to Ines, the CTO. checkout-service deploys to AWS eu-central-1 via GitHub Actions. Decision ADR-007: chose Neo4j over Postgres for orders because fraud rings (order -> customer -> device -> order) need multi-hop queries. The release freeze starts on 30 October. (relevance: 0.86)\\n\\n## Relevant Knowledge\\n\\n### Relevant Entities\\n- checkout-service (OBJECT:SOFTWARE): Python 3.12 / FastAPI service; deploys to AWS eu-central-1 via GitHub Actions\\n- fraud-api (OBJECT:SOFTWARE): Fraud scoring service, owned by Lena (previously Jonas, changed week of 2026-10-22 per Mara)\\n- orders-graph (OBJECT:DATABASE): Neo4j Aura instance storing orders\\n- payments team (ORGANIZATION)\\n- Postgres (OBJECT)\\n- customer (OBJECT:EXTRACTED_ENTITY)\\n- ADR-007 (EVENT)\\n- order (OBJECT:EXTRACTED_ENTITY)\\n- Neo4j (OBJECT)\\n- Kestrel Labs (ORGANIZATION)\", \"has_context\": true}"}

**Answer**

Here's what my long-term memory has on this:

- **Who to talk to:** Lena, who now owns fraud-api, the fraud scoring service that checkout-service calls. Mara, who leads the payments team at Kestrel Labs, said ownership moved from Jonas to Lena this week (the entity note is dated 2026-10-22). The original briefing from Mara still names Jonas, and that message hasn't been edited. Check with Mara or Lena that the handover is complete, and keep Jonas in the loop while you do.
- **Their manager:** Ines, the CTO. Jonas and Lena both report to her.
- **Deadline:** The release freeze starts on **30 October**, which is 8 days from today (2026-10-22). Your change to the fraud scoring call needs to ship before then, or it waits until the freeze ends.

Memory doesn't say when the freeze ends, or whether the ownership change affects fraud-api's API contract or review process. Ask Lena about both.

Memory also has two facts about checkout-service that may matter for your change. It's Python 3.12 with FastAPI, and it deploys to AWS eu-central-1 via GitHub Actions.

_4 turns, $0.051_

# Day 1: project briefing (aura)

**Prompt**

> Hi, I'm Mara. Here is the briefing for my project. Keep these facts in your long-term memory for future sessions, then confirm in one sentence.
> 
> - I lead the payments team at Kestrel Labs.
> - We build checkout-service in Python 3.12 with FastAPI.
> - checkout-service stores orders in the Neo4j Aura instance orders-graph.
> - checkout-service calls fraud-api for fraud scoring. fraud-api is owned by Jonas.
> - Jonas and Lena both report to Ines, our CTO.
> - checkout-service deploys to AWS eu-central-1 via GitHub Actions.
> - Decision ADR-007: we chose Neo4j over Postgres for orders because fraud rings (order -> customer -> device -> order) need multi-hop queries.
> - The release freeze starts on 30 October.

**Memory tool calls (neo4j-agent-memory MCP -> Neo4j Aura)**

- `memory_store_message(content='Briefing from Mara (leads the payments team at Kestrel Labs): checkout-service is built in Python 3.12 with FastAPI. It stores orders in the Neo4j Aura instance orders-graph. It calls fraud-api for fraud scoring; fraud-api is owned by Jonas. Jonas and Lena both report to Ines, the CTO. checkout-service deploys to AWS eu-central-1 via GitHub Actions. Decision ADR-007: chose Neo4j over Postgres for orders because fraud rings (order -> customer -> device -> order) need multi-hop queries. The release freeze starts on 30 October.', role='user')`
  - {"result":"{\"stored\": true, \"type\": \"message\", \"id\": \"02b678e9-4d66-4e81-8972-38f29966823d\", \"session_id\": \"4ec531b1-f379-4a12-81c6-3559609258bf\"}"}
- `memory_add_entity(name='Mara', entity_type='PERSON', description='Leads the payments team at Kestrel Labs')`
  - {"result":"{\"stored\": true, \"type\": \"entity\", \"id\": \"b34022d3-8cf4-4734-aeca-284ce5b2a2d8\", \"name\": \"Mara\", \"entity_type\": \"PERSON\", \"deduplication\": {\"action\": \"merged\", \"matched_entity_name\": \"Mara\", \"similarity_score\": 1.0}}"}
- `memory_add_entity(name='Kestrel Labs', entity_type='ORGANIZATION')`
  - {"result":"{\"stored\": true, \"type\": \"entity\", \"id\": \"085ba294-5a33-4180-9432-92150c6bf00b\", \"name\": \"Kestrel Labs\", \"entity_type\": \"ORGANIZATION\", \"deduplication\": {\"action\": \"merged\", \"matched_entity_name\": \"Kestrel Labs\", \"similarity_score\": 1.0}}"}
- `memory_add_entity(name='checkout-service', entity_type='OBJECT', subtype='SOFTWARE', description='Python 3.12 / FastAPI service; deploys to AWS eu-central-1 via GitHub Actions')`
  - {"result":"{\"stored\": true, \"type\": \"entity\", \"id\": \"f95a5507-7f6d-4d1c-95eb-e9b320a022d9\", \"name\": \"checkout-service\", \"entity_type\": \"OBJECT\", \"deduplication\": {\"action\": \"merged\", \"matched_entity_name\": \"checkout-service\", \"similarity_score\": 1.0}}"}
- `memory_add_entity(name='orders-graph', entity_type='OBJECT', subtype='DATABASE', description='Neo4j Aura instance storing orders')`
  - {"result":"{\"stored\": true, \"type\": \"entity\", \"id\": \"abb900b4-8247-4698-a6db-d70ccff1dec9\", \"name\": \"orders-graph\", \"entity_type\": \"OBJECT\", \"deduplication\": {\"action\": \"merged\", \"matched_entity_name\": \"orders-graph\", \"similarity_score\": 1.0}}"}
- `memory_add_entity(name='fraud-api', entity_type='OBJECT', subtype='SOFTWARE', description='Fraud scoring service, owned by Jonas')`
  - {"result":"{\"stored\": true, \"type\": \"entity\", \"id\": \"9e78af58-ae64-4300-a8b6-d50f9fc28fe0\", \"name\": \"fraud-api\", \"entity_type\": \"OBJECT\", \"deduplication\": {\"action\": \"merged\", \"matched_entity_name\": \"fraud-api\", \"similarity_score\": 1.0}}"}
- `memory_add_entity(name='Jonas', entity_type='PERSON')`
  - {"result":"{\"stored\": true, \"type\": \"entity\", \"id\": \"d1f30ee7-d0e3-472e-a596-31281f8b6500\", \"name\": \"Jonas\", \"entity_type\": \"PERSON\", \"deduplication\": {\"action\": \"merged\", \"matched_entity_name\": \"Jonas\", \"similarity_score\": 1.0}}"}
- `memory_add_entity(name='Lena', entity_type='PERSON')`
  - {"result":"{\"stored\": true, \"type\": \"entity\", \"id\": \"ecfc56dc-d944-4246-892a-f4ca405045df\", \"name\": \"Lena\", \"entity_type\": \"PERSON\", \"deduplication\": {\"action\": \"merged\", \"matched_entity_name\": \"Lena\", \"similarity_score\": 1.0}}"}
- `memory_add_entity(name='Ines', entity_type='PERSON', description='CTO')`
  - {"result":"{\"stored\": true, \"type\": \"entity\", \"id\": \"ccade7f7-67bb-4459-89e6-63e0838b9c20\", \"name\": \"Ines\", \"entity_type\": \"PERSON\", \"deduplication\": {\"action\": \"merged\", \"matched_entity_name\": \"Ines\", \"similarity_score\": 1.0}}"}
- `memory_add_fact(subject='ADR-007', predicate='decision', object_value='Chose Neo4j over Postgres for orders because fraud rings (order -> customer -> device -> order) need multi-hop queries')`
  - {"result":"{\"stored\": true, \"type\": \"fact\", \"id\": \"2828bc49-82fe-4727-849b-be7da267500c\", \"triple\": \"ADR-007 -> decision -> Chose Neo4j over Postgres for orders because fraud rings (order -> customer -> device -> order) need multi-hop queries\"}"}
- `memory_add_fact(subject='Kestrel Labs release freeze', predicate='starts_on', object_value='30 October', valid_from='2026-10-30')`
  - {"result":"{\"stored\": true, \"type\": \"fact\", \"id\": \"b5976b11-3710-4882-aa16-8619229f5009\", \"triple\": \"Kestrel Labs release freeze -> starts_on -> 30 October\"}"}
- `memory_create_relationship(source_name='Mara', target_name='Kestrel Labs', relationship_type='WORKS_AT', description='Leads the payments team')`
  - {"result":"{\"stored\": true, \"type\": \"relationship\", \"id\": \"31fd3b5b-9f90-42a8-bf1d-4cb38019268a\", \"source\": \"Mara\", \"target\": \"Kestrel Labs\", \"relationship_type\": \"WORKS_AT\"}"}
- `memory_create_relationship(source_name='Mara', target_name='checkout-service', relationship_type='LEADS_TEAM_BUILDING')`
  - {"result":"{\"stored\": true, \"type\": \"relationship\", \"id\": \"ce810608-9a89-4147-a4f6-4d20d45f2cdd\", \"source\": \"Mara\", \"target\": \"checkout-service\", \"relationship_type\": \"LEADS_TEAM_BUILDING\"}"}
- `memory_create_relationship(source_name='checkout-service', target_name='orders-graph', relationship_type='STORES_ORDERS_IN')`
  - {"result":"{\"stored\": true, \"type\": \"relationship\", \"id\": \"8477b77a-f95a-455a-9478-871803194642\", \"source\": \"checkout-service\", \"target\": \"orders-graph\", \"relationship_type\": \"STORES_ORDERS_IN\"}"}
- `memory_create_relationship(source_name='checkout-service', target_name='fraud-api', relationship_type='CALLS', description='Fraud scoring')`
  - {"result":"{\"stored\": true, \"type\": \"relationship\", \"id\": \"9d472079-01f5-473c-9f6e-640067409ab2\", \"source\": \"checkout-service\", \"target\": \"fraud-api\", \"relationship_type\": \"CALLS\"}"}
- `memory_create_relationship(source_name='Jonas', target_name='fraud-api', relationship_type='OWNS')`
  - {"result":"{\"stored\": true, \"type\": \"relationship\", \"id\": \"1298657a-7b1e-49ce-8f87-d889293d98ba\", \"source\": \"Jonas\", \"target\": \"fraud-api\", \"relationship_type\": \"OWNS\"}"}
- `memory_create_relationship(source_name='Jonas', target_name='Ines', relationship_type='REPORTS_TO')`
  - {"result":"{\"stored\": true, \"type\": \"relationship\", \"id\": \"d1effdd9-5fdc-48e1-97c2-c3311dd92dd5\", \"source\": \"Jonas\", \"target\": \"Ines\", \"relationship_type\": \"REPORTS_TO\"}"}
- `memory_create_relationship(source_name='Lena', target_name='Ines', relationship_type='REPORTS_TO')`
  - {"result":"{\"stored\": true, \"type\": \"relationship\", \"id\": \"4037f17c-51bb-477d-be57-856ca1bf4e85\", \"source\": \"Lena\", \"target\": \"Ines\", \"relationship_type\": \"REPORTS_TO\"}"}
- `memory_add_fact(subject='checkout-service', predicate='deploys_to', object_value='AWS eu-central-1 via GitHub Actions')`
  - {"result":"{\"stored\": true, \"type\": \"fact\", \"id\": \"d8e8a194-517e-469f-bb84-cc867ad17587\", \"triple\": \"checkout-service -> deploys_to -> AWS eu-central-1 via GitHub Actions\"}"}
- `memory_add_fact(subject='checkout-service', predicate='tech_stack', object_value='Python 3.12, FastAPI')`
  - {"result":"{\"stored\": true, \"type\": \"fact\", \"id\": \"4a551326-14e8-4cfe-8557-1c37b1effe25\", \"triple\": \"checkout-service -> tech_stack -> Python 3.12, FastAPI\"}"}

**Answer**

Hi Mara, I've saved your whole briefing to long-term memory: you, your team, checkout-service and its stack, orders-graph, fraud-api and Jonas, the Jonas/Lena→Ines reporting line, the eu-central-1 deployment, ADR-007, and the 30 October release freeze.

_22 turns, $0.095_

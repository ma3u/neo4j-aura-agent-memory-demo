// Aura dashboard "Agent Memory on Neo4j Aura": one read-only query per card.
// Data: neo4j-agent-memory (Neo4j Labs SDK, Bolt backend) written by Claude Code via the SDK's MCP server
// (demo/run_sessions.py --backend aura), and eval results from eval/eval_memory.py.

// ===== Page 1: Memory (neo4j-agent-memory) =====

// A1 (single value): entities
MATCH (e:Entity) RETURN count(e) AS Entities;

// A2 (single value): relationships between entities
MATCH (:Entity)-[r:RELATED_TO]->(:Entity) RETURN count(r) AS Relationships;

// A3 (single value): facts
MATCH (f:Fact) RETURN count(f) AS Facts;

// A4 (graph): conversation -> messages -> mentioned entities -> relationships
MATCH p = (:Conversation)-[:HAS_MESSAGE]->(:Message)-[:MENTIONS]->(:Entity) RETURN p
UNION
MATCH p = (:Entity)-[:RELATED_TO]->(:Entity) RETURN p;

// A5 (graph): the day-3 question as a path: checkout-service -> fraud-api -> owner -> manager
MATCH p = (:Entity {name: 'checkout-service'})-[:RELATED_TO*1..3]-(:Entity {name: 'Ines'})
WHERE all(r IN relationships(p) WHERE r.type IN ['CALLS', 'OWNS', 'REPORTS_TO'])
RETURN p;

// A6 (table): who owns fraud-api? The correction added Lena; Jonas is still live (no retire over MCP)
MATCH (p:Entity)-[r:RELATED_TO {type: 'OWNS'}]->(:Entity {name: 'fraud-api'})
RETURN p.name AS owner, coalesce(r.extractor, 'agent via MCP') AS written_by, left(toString(r.created_at), 19) AS created,
       coalesce(toString(r.valid_until), 'live') AS valid_until, r.description AS note
ORDER BY created;

// A7 (table): relationships: extracted with the ontology, or added by the agent
MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity)
RETURN a.name AS subject, r.type AS relation, b.name AS object,
       coalesce(r.extractor, 'agent via MCP') AS written_by, r.confidence AS confidence
ORDER BY written_by, relation;

// A8 (table): facts (subject, predicate, object, valid from)
MATCH (f:Fact)
RETURN f.subject AS subject, f.predicate AS predicate, f.object AS object, toString(f.valid_from) AS valid_from
ORDER BY subject;

// ===== Page 2: Ontology =====

// O1 (bar): entities per type label (POLE label next to :Entity)
MATCH (e:Entity) UNWIND [l IN labels(e) WHERE l <> 'Entity'] AS label
RETURN label, count(*) AS entities ORDER BY entities DESC;

// O2 (bar): relationship types, extracted vs added by the agent (one column each: Aura bar charts ignore a group key)
MATCH (:Entity)-[r:RELATED_TO]->(:Entity)
RETURN r.type AS relation, sum(CASE WHEN r.extractor IS NOT NULL THEN 1 ELSE 0 END) AS extracted,
       sum(CASE WHEN r.extractor IS NULL THEN 1 ELSE 0 END) AS agent
ORDER BY extracted + agent DESC;

// O3 (table): evidence behind each extracted relationship
MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity) WHERE r.extractor IS NOT NULL
RETURN a.name + ' -' + r.type + '-> ' + b.name AS relationship, r.confidence AS confidence,
       left(coalesce(r.evidence[0], ''), 160) AS evidence
ORDER BY confidence DESC;

// ===== Page 3: Eval (Haystack) =====

// E1 (bar): accuracy per variant
MATCH (v:DemoEvalVariant)-[a:ANSWERED]->()
RETURN v.name AS variant, toInteger(round(100.0 * sum(CASE WHEN a.correct THEN 1 ELSE 0 END) / count(a))) AS accuracy
ORDER BY accuracy;

// E2 (bar): accuracy per question type (one column per type)
MATCH (v:DemoEvalVariant)-[a:ANSWERED]->(q:DemoEvalQuestion)
WITH v.name AS variant, q.type AS type, toInteger(round(100.0 * sum(CASE WHEN a.correct THEN 1 ELSE 0 END) / count(a))) AS acc
WITH variant, apoc.map.fromPairs(collect([type, acc])) AS m
RETURN variant, m['single-hop'] AS `single-hop`, m['multi-hop'] AS `multi-hop`, m['correction'] AS correction, m['not-in-memory'] AS `not-in-memory`
ORDER BY variant;

// E3 (table): every answer with the judge's reason
MATCH (v:DemoEvalVariant)-[a:ANSWERED]->(q:DemoEvalQuestion)
RETURN q.id AS id, q.type AS type, q.question AS question, v.name AS variant,
       CASE WHEN a.correct THEN 'correct' ELSE 'wrong' END AS verdict, left(a.answer, 220) AS answer, a.reason AS judge
ORDER BY id, variant;

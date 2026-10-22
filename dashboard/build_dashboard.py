"""
Build a NeoDash 2.4 dashboard JSON from dashboard.cypher, for Aura Console -> Dashboards -> Import
(Aura migrates NeoDash reports to its own cards). Queries live only in dashboard.cypher; this file adds layout.

Run:  venv/bin/python dashboard/build_dashboard.py   # writes dashboard/aura_dashboard.json, paste it into Import

After import, two manual steps (NeoDash bar charts take one value column): open "Accuracy per question type" ->
Settings -> Value and add the other three types next to `multi-hop`, and add `agent` to "Relationship types".
"""
import json
import re
import uuid
from pathlib import Path

HERE = Path(__file__).parent
CYPHER = HERE / "dashboard.cypher"
OUT = HERE / "aura_dashboard.json"

INTRO = """**Claude Code with long-term memory in Neo4j Aura**, through the Neo4j Labs SDK
[neo4j-agent-memory](https://neo4j.com/labs/agent-memory/) and its MCP server (Bolt backend). Three separate Claude Code
sessions (briefing, correction, question) share nothing but this graph, captured by Claude Code hooks; extraction follows the shared ontology
"Agent Memory + Software Team". Haystack evaluates it against NAMS (memory.neo4jlabs.com) on 10 questions.
Code: [github.com/ma3u/neo4j-aura-agent-memory-demo](https://github.com/ma3u/neo4j-aura-agent-memory-demo)"""

# (card id in dashboard.cypher, NeoDash type, title, x, y, w, h, selection). x/w on a 12-column grid;
# Aura keeps the numbers but lays them out on 24 columns, so they are doubled on export (GRID_SCALE).
GRID_SCALE = 2
PAGES = {
    "Memory (neo4j-agent-memory)": [
        ("intro", "text", "Agent memory on Neo4j Aura", 0, 0, 12, 2, {}),
        ("A1", "value", "Entities", 0, 2, 4, 2, {}),
        ("A2", "value", "Relationships", 4, 2, 4, 2, {}),
        ("A3", "value", "Facts", 8, 2, 4, 2, {}),
        ("A4", "graph", "What Claude Code remembers (conversation, messages, entities)", 0, 4, 7, 6, {}),
        ("A5", "graph", "Day 3: checkout-service -> fraud-api -> owner -> manager", 7, 4, 5, 6, {}),
        ("A6", "table", "The correction: who owns fraud-api?", 0, 10, 12, 3, {}),
        ("A7", "table", "Relationships: ontology extraction vs agent", 0, 13, 7, 6, {}),
        ("A8", "table", "Facts", 7, 13, 5, 6, {}),
    ],
    "History (Claude Code)": [
        ("H1", "table", "Claude Code sessions captured in Aura (agent-memory-hook)", 0, 0, 12, 4, {}),
        ("H2", "graph", "Day 2 as a reasoning trace: prompt -> steps -> tool calls", 0, 4, 7, 6, {}),
        ("H3", "bar", "Tool calls per tool", 7, 4, 5, 6, {"index": "tool", "value": "calls", "key": "(none)"}),
    ],
    "Ontology": [
        ("O1", "bar", "Entities per type", 0, 0, 5, 4, {"index": "label", "value": "entities", "key": "(none)"}),
        ("O2", "bar", "Relationship types: extracted vs agent", 5, 0, 7, 4, {"index": "relation", "value": "extracted", "key": "(none)"}),
        ("O3", "table", "Evidence behind extracted relationships", 0, 4, 12, 6, {}),
    ],
    "Eval (Haystack)": [
        ("E1", "bar", "Accuracy per variant (%)", 0, 0, 5, 4, {"index": "variant", "value": "accuracy", "key": "(none)"}),
        ("E2", "bar", "Accuracy per question type (%)", 5, 0, 7, 4, {"index": "variant", "value": "multi-hop", "key": "(none)"}),
        ("E3", "table", "Every answer with the judge's reason", 0, 4, 12, 7, {}),
    ],
}


def load_queries() -> dict[str, str]:
    """Map card id -> query from blocks headed `// <id> (<type>): <title>`."""
    queries, current, lines = {}, None, []
    for line in CYPHER.read_text().splitlines():
        m = re.match(r"//\s*([A-Z]\d+)\s*\(", line)
        if m:
            current, lines = m.group(1), []
        elif current and not line.startswith("//"):
            lines.append(line)
            if line.rstrip().endswith(";"):
                queries[current] = "\n".join(lines).strip().rstrip(";")
                current = None
    return queries


def main() -> None:
    queries = load_queries()
    pages = []
    for title, cards in PAGES.items():
        reports = [{
            "id": f"{re.sub('[^a-z]+', '-', title.lower()).strip('-')}-{cid.lower()}",
            "title": ctitle,
            "query": INTRO if cid == "intro" else queries[cid],
            "x": x * GRID_SCALE, "y": y, "width": w * GRID_SCALE, "height": h,
            "type": rtype,
            "selection": selection,
            "settings": {},
        } for cid, rtype, ctitle, x, y, w, h, selection in cards]
        pages.append({"title": title, "reports": reports})
    dashboard = {
        "uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, "neo4j-aura-agent-memory-demo/dashboard")),  # stable across rebuilds
        "title": "Agent Memory on Neo4j Aura",
        "version": "2.4",
        "settings": {"pagenumber": 0, "editable": True, "fullscreenEnabled": True, "parameters": {}},
        "pages": pages,
    }
    OUT.write_text(json.dumps(dashboard, indent=2) + "\n")
    print(f"Wrote {OUT} ({len(pages)} pages, {sum(len(p['reports']) for p in pages)} cards)")


if __name__ == "__main__":
    main()

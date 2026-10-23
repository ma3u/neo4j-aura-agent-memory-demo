"""
Evaluate Neo4j agent memory with Haystack: does an agent in a NEW session answer correctly from what an earlier
Antigravity or Claude Code session stored? Run demo/run_sessions.py for both backends first (it writes the memory).

Questions (eval/questions.json): 4 single-hop, 3 multi-hop, 1 correction (Jonas -> Lena), 2 not-in-memory
(the right answer is "I don't know": memory must not make an agent invent facts).

Variants (same questions, same wording):
  no_memory          Haystack Agent, no tools                                 -> baseline: what the LLM knows alone
  haystack_aura      Haystack Agent + neo4j-agent-memory SDK, Bolt to Aura    -> another framework reads stored memory
  antigravity_aura   Antigravity MCP (bin/agent-memory-mcp on Aura, read-only) -> the MCP path in Antigravity
  claude_code_aura   claude -p + the SDK's MCP server on Aura (read tools)    -> the MCP path in Claude Code
  haystack_nams      Haystack Agent + neo4j-agent-memory SDK, NAMS backend    -> needs NAMS_API_KEY
  antigravity_nams   Antigravity MCP (bin/nams-mcp on NAMS, read-only)        -> needs NAMS_API_KEY
  claude_code_nams   claude -p + hosted NAMS MCP (read tools, hooks off)      -> needs NAMS_API_KEY

Scoring: LLM judge (Haystack chat generator, JSON mode) against the reference answer, like exercise 10 of
the haystack-workshop. Results: eval/results/eval_results.json and, in Neo4j Aura,
(:DemoEvalVariant)-[:ANSWERED {correct, answer, reason}]->(:DemoEvalQuestion) for the Aura dashboard.

Run:  venv/bin/python eval/eval_memory.py                      # every default variant whose backend is configured
      venv/bin/python eval/eval_memory.py --variants antigravity_aura antigravity_nams
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from haystack.components.agents import Agent
from haystack.dataclasses import ChatMessage
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
load_dotenv(ROOT / ".env")

from llm import chat_generator  # noqa: E402

QUESTIONS = json.loads((ROOT / "eval" / "questions.json").read_text())
RESULTS = ROOT / "eval" / "results" / "eval_results.json"
DEFAULT_VARIANTS = ["no_memory", "haystack_aura", "antigravity_aura", "haystack_nams", "antigravity_nams"]
VARIANTS = ["no_memory", "haystack_aura", "antigravity_aura", "claude_code_aura",
            "haystack_nams", "antigravity_nams", "claude_code_nams"]

ASK = ("Using only your long-term memory about my project, answer briefly: {question}\n"
       "If your memory does not contain the answer, say that you don't know.")
SYSTEM_PROMPT = """You are a coding assistant with long-term memory about the user's project.
- Look things up in memory before answering. Facts can span several hops (service -> owner -> manager).
- If a search finds nothing useful, search again with other words (an entity name, a role, a topic).
- If memory has a newer fact that replaces an older one, answer with the newer one.
- Never invent facts that are not in memory; say you don't know instead. Be concise."""
JUDGE = """You grade an assistant's answer about a fictional software project.

Question: {question}
Reference answer: {reference}
Assistant answer: {candidate}

Correct if the assistant gives the same facts as the reference (extra correct detail is fine; every part of a
two-part question must be answered). If the reference says "Not in memory", the answer is correct only if the
assistant says it does not know / memory has no such fact, and wrong if it names a concrete value.
Return JSON: {{"correct": true or false, "reason": "<one short sentence>"}}"""


def haystack_answer(tools: list | None, question: str) -> str:
    agent = Agent(chat_generator=chat_generator(), tools=tools or [], system_prompt=SYSTEM_PROMPT, max_agent_steps=8)
    reply = agent.run(messages=[ChatMessage.from_user(ASK.format(question=question))])["messages"][-1]
    return reply.text or "(no answer)"


def claude_answer(question: str, backend: str) -> str:
    from claude_backends import BACKENDS  # the same flags as demo/run_sessions.py

    cfg = BACKENDS[backend]
    args = list(cfg["args"])
    args[args.index("--allowedTools") + 1] = cfg["read_only_tools"]  # the eval must not change memory
    args[args.index("--settings") + 1] = json.dumps(cfg["read_only_settings"])  # NAMS hooks off: they would store it
    cmd = ["claude", "-p", ASK.format(question=question), "--output-format", "json", "--model", "sonnet",
           "--strict-mcp-config", "--setting-sources", "project", *args]
    env = {**os.environ, **cfg["env"], **cfg["read_only_env"]}
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600, env=env)
    return json.loads(out.stdout).get("result") or f"(no answer: {out.stderr[-200:]})"


def judge(q: dict, candidate: str) -> dict:
    gen = chat_generator(generation_kwargs={"response_format": {"type": "json_object"}})
    prompt = JUDGE.format(question=q["question"], reference=q["answer"], candidate=candidate)
    reply = gen.run(messages=[ChatMessage.from_user(prompt)])["replies"][0].text
    try:
        verdict = json.loads(reply)
        return {"correct": bool(verdict["correct"]), "reason": verdict.get("reason", "")}
    except (json.JSONDecodeError, KeyError):
        return {"correct": False, "reason": f"unparseable judge reply: {reply[:80]}"}


def answers_for(variant: str) -> list[str]:
    if variant == "no_memory":
        return [haystack_answer(None, q["question"]) for q in QUESTIONS]
    if variant.startswith("haystack_"):  # same SDK, same read-only tool, backend aura (Bolt) or nams
        from memory_tools import AgentMemory

        memory = AgentMemory(variant.removeprefix("haystack_"))
        try:
            return [haystack_answer(memory.tools(), q["question"]) for q in QUESTIONS]
        finally:
            memory.close()
    if variant.startswith("antigravity_"):
        from claude_backends import run_antigravity_batch

        backend = variant.removeprefix("antigravity_")
        prompts = [ASK.format(question=q["question"]) for q in QUESTIONS]
        return run_antigravity_batch(prompts, backend, system_prompt=SYSTEM_PROMPT)
    from claude_backends import write_aura_mcp_config

    write_aura_mcp_config()
    backend = variant.removeprefix("claude_code_")
    with ThreadPoolExecutor(4) as pool:  # independent headless sessions
        return list(pool.map(lambda q: claude_answer(q["question"], backend), QUESTIONS))


def write_to_aura(results: dict) -> None:
    driver = GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]))
    rows = [{"variant": v, **r} for v, rs in results["variants"].items() for r in rs]
    with driver.session() as s:
        s.run("CREATE CONSTRAINT demo_eval_q IF NOT EXISTS FOR (n:DemoEvalQuestion) REQUIRE n.id IS UNIQUE")
        s.run("CREATE CONSTRAINT demo_eval_v IF NOT EXISTS FOR (n:DemoEvalVariant) REQUIRE n.name IS UNIQUE")
        s.run("UNWIND $qs AS q MERGE (n:DemoEvalQuestion {id: q.id}) "
              "SET n.type = q.type, n.question = q.question, n.reference = q.answer", qs=QUESTIONS)
        s.run("UNWIND $rows AS r MERGE (v:DemoEvalVariant {name: r.variant}) SET v.run_at = datetime($ts) "
              "WITH v, r MATCH (q:DemoEvalQuestion {id: r.id}) MERGE (v)-[a:ANSWERED]->(q) "
              "SET a.correct = r.correct, a.answer = r.answer, a.reason = r.reason",
              rows=rows, ts=results["run_at"])
    driver.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", nargs="+", choices=VARIANTS)
    args = parser.parse_args()
    variants = args.variants or [v for v in DEFAULT_VARIANTS if "nams" not in v or os.getenv("NAMS_API_KEY")]

    results = json.loads(RESULTS.read_text()) if RESULTS.exists() else {"variants": {}}
    results["run_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for variant in variants:
        print(f"[{variant}] answering {len(QUESTIONS)} questions ...", flush=True)
        answers = answers_for(variant)
        with ThreadPoolExecutor(8) as pool:
            verdicts = list(pool.map(lambda qa: judge(*qa), zip(QUESTIONS, answers)))
        results["variants"][variant] = [{"id": q["id"], "answer": a, **v} for q, a, v in zip(QUESTIONS, answers, verdicts)]
    RESULTS.write_text(json.dumps(results, indent=2) + "\n")
    write_to_aura(results)

    types = list(dict.fromkeys(q["type"] for q in QUESTIONS))
    print(f"\n{'variant':<26} {'overall':>8} " + " ".join(f"{t:>14}" for t in types))
    for variant, rows in results["variants"].items():
        by_type = {t: [r["correct"] for q, r in zip(QUESTIONS, rows) if q["type"] == t] for t in types}
        overall = 100 * sum(r["correct"] for r in rows) / len(rows)
        print(f"{variant:<26} {overall:>7.0f}% " + " ".join(f"{100 * sum(v) / len(v):>13.0f}%" for v in by_type.values()))
    print(f"\nDetails: {RESULTS.relative_to(ROOT)} | Aura: (:DemoEvalVariant)-[:ANSWERED]->(:DemoEvalQuestion)")


if __name__ == "__main__":
    main()

"""
Local daemon behind bin/agent-memory-hook: captures Antigravity and Claude Code sessions into Neo4j Aura (Bolt) or
NAMS through the neo4j-agent-memory SDK, and injects recalled memory into each new turn. Keeps the SDK client and
the embedding model loaded in memory, so hooks stay fast.

  user prompt   -> short-term Message (role user, entity extraction on) + a ReasoningTrace for the turn
  tool call     -> ReasoningStep (action = tool) + ToolCall (arguments, result)
  final answer  -> short-term Message (role assistant) + trace completed with the answer as outcome
  recall        -> entities, facts and earlier messages relevant to the prompt (injected into the turn)

One conversation per session (on Aura: SDK session_id = session_id; on NAMS: a conversation UUID created via
create_conversation with metadata={harness, projectDirectory, session_id}). Writes run in order on one worker
thread, so a hook only waits for recall, never for extraction. POST {"event": "flush"} blocks until the queue is
empty (demo/run_sessions.py uses it between sessions). Exits after AGENT_MEMORY_HOOKS_IDLE seconds without requests.

Run by bin/agent-memory-hook on demand; by hand: venv/bin/python harness/aura_hooks_daemon.py
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from memory_tools import AgentMemory  # noqa: E402  (same SDK settings, ontology and embeddings as the MCP server)

PORT = int(os.getenv("AGENT_MEMORY_HOOKS_PORT", "8787"))
IDLE_SECONDS = int(os.getenv("AGENT_MEMORY_HOOKS_IDLE", "1800"))
MAX_TEXT = 4000  # per stored tool argument / result


def clip(value, limit: int = MAX_TEXT):
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[:limit] + f"... [{len(text) - limit} chars cut]"


class Capture:
    """Turns hook events into SDK writes on Aura (Bolt) or NAMS. Also used by harness/import_transcripts.py."""

    def __init__(self, memory: AgentMemory):
        self.memory = memory
        self.backend = memory.backend
        self.client = memory._client
        self.traces: dict[str, str] = {}         # session id -> open trace id
        self.conversations: dict[str, str] = {}  # session id -> NAMS conversation UUID
        self.seen_prompts: set[tuple[str, str]] = set()
        self.seen_answers: set[tuple[str, str]] = set()

    def _run(self, coro):
        return self.memory._run(coro)

    def _conv(self, session: str, meta: dict) -> str:
        if self.backend != "nams":
            return session
        if session not in self.conversations:
            conv = self._run(self.client.short_term.create_conversation(session, metadata=meta))
            self.conversations[session] = str(conv.id)
        return self.conversations[session]

    def prompt(self, session: str, text: str, meta: dict) -> None:
        if not text or (session, text) in self.seen_prompts:
            return
        self.seen_prompts.add((session, text))
        conv = self._conv(session, meta)
        msg = self._run(self.client.short_term.add_message(conv, "user", text, metadata=meta))
        trace = self._run(self.client.reasoning.start_trace(
            conv, task=text[:1000], metadata=meta, triggered_by_message_id=msg.id))
        self.traces[session] = str(trace.id)

    def tool(self, session: str, name: str, arguments: dict, result, meta: dict | None = None) -> None:
        conv = self._conv(session, meta or {"harness": "antigravity", "source": "agent-memory-hook"})
        if session not in self.traces:
            trace = self._run(self.client.reasoning.start_trace(conv, task="(tool calls without a prompt)"))
            self.traces[session] = str(trace.id)
        step = self._run(self.client.reasoning.add_step(
            self.traces[session], thought=name, action=name, observation=clip(result, 500), generate_embedding=False))
        args = arguments if isinstance(arguments, dict) else {"input": arguments}
        self._run(self.client.reasoning.record_tool_call(
            step.id, name, {k: clip(v, 1000) for k, v in args.items()}, result=clip(result)))

    def answer(self, session: str, text: str, meta: dict) -> None:
        if not text or (session, text) in self.seen_answers:
            return
        self.seen_answers.add((session, text))
        conv = self._conv(session, meta)
        self._run(self.client.short_term.add_message(conv, "assistant", text, metadata=meta))
        if session in self.traces:
            self._run(self.client.reasoning.complete_trace(
                self.traces.pop(session), outcome=text[:1000], success=True))

    def recall(self, prompt: str, session: str | None = None) -> str:
        if not prompt:
            return ""
        parts = []
        if self.backend == "nams" and session and session in self.conversations:
            ctx = self._run(self.client.short_term.get_context(prompt[:500], session_id=self.conversations[session]))
            if ctx:
                parts.append(ctx)
        res = self.memory.search(prompt[:500])
        if res and not res.startswith("No memories"):
            parts.append(res)
        return "\n\n".join(parts) or f"No memories found for '{prompt[:80]}'."


class Daemon:
    def __init__(self):
        self.captures: dict[str, Capture] = {"aura": Capture(AgentMemory("aura"))}
        self._lock = threading.Lock()
        self.jobs: queue.Queue = queue.Queue()
        self.last_request = time.time()
        threading.Thread(target=self._worker, daemon=True).start()

    def _capture(self, backend: str) -> Capture:
        with self._lock:
            if backend not in self.captures:
                self.captures[backend] = Capture(AgentMemory(backend))
            return self.captures[backend]

    def _worker(self) -> None:
        while True:
            fn, args = self.jobs.get()
            try:
                fn(*args)
            except Exception as e:  # one failed write must not stop the capture
                print(f"agent-memory-hook: {fn.__name__} failed: {e}", file=sys.stderr, flush=True)
            finally:
                self.jobs.task_done()

    def handle(self, event: dict) -> dict:
        self.last_request = time.time()
        kind = event.get("event")
        if kind == "flush":
            self.jobs.join()
            return {}
        backend = event.get("backend") or "aura"
        harness = event.get("harness") or "claude"
        session = event.get("session_id") or "unknown"
        cwd = event.get("cwd", "")
        meta = {"harness": harness, "source": "agent-memory-hook", "project": cwd,
                "projectDirectory": cwd, "session_id": session}
        cap = self._capture(backend)
        if kind in ("UserPromptSubmit", "PreInvocation"):
            prompt = event.get("prompt", "")
            context = cap.recall(prompt, session=session)  # before storing: recall earlier knowledge only
            if prompt and not event.get("read_only"):
                self.jobs.put((cap.prompt, (session, prompt, meta)))
            return {"context": context}
        if event.get("read_only"):
            return {}
        if kind == "PostToolUse":
            self.jobs.put((cap.tool, (session, event.get("tool_name", "?"), event.get("tool_input") or {},
                                      event.get("tool_response"), meta)))
        elif kind == "Stop" and event.get("answer"):
            self.jobs.put((cap.answer, (session, event["answer"], meta)))
        return {}


def main() -> None:
    daemon = Daemon()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # health check
            self._reply({"ok": True, "queued": daemon.jobs.qsize(), "backends": list(daemon.captures)})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            self._reply(daemon.handle(body))

        def _reply(self, payload: dict):
            data = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"agent-memory-hook daemon on 127.0.0.1:{PORT}", file=sys.stderr, flush=True)
    while time.time() - daemon.last_request < IDLE_SECONDS or daemon.jobs.unfinished_tasks:
        time.sleep(5)
    server.shutdown()
    for cap in daemon.captures.values():
        cap.memory.close()


if __name__ == "__main__":
    main()

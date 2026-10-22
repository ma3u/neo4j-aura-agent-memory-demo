"""
Local daemon behind bin/agent-memory-hook: captures Claude Code sessions into Neo4j Aura through the neo4j-agent-memory
SDK, the way nams-hooks does it for NAMS. Keeps one SDK client and the embedding model loaded, so hooks stay fast.

  user prompt   -> short-term Message (role user, entity extraction on) + a ReasoningTrace for the turn
  tool call     -> ReasoningStep (action = tool) + ToolCall (arguments, result)
  final answer  -> short-term Message (role assistant) + trace completed with the answer as outcome
  recall        -> entities, facts and earlier messages relevant to the prompt (injected as additionalContext)

One conversation per Claude Code session (SDK session_id = Claude session_id). Writes run in order on one worker
thread, so a hook only waits for recall, never for extraction. POST /flush blocks until the queue is empty
(demo/run_sessions.py uses it between sessions). Exits after AGENT_MEMORY_HOOKS_IDLE seconds without requests.

Run by bin/agent-memory-hook on demand; by hand: venv/bin/python harness/aura_hooks_daemon.py
"""
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
    """Turns hook events into SDK writes. Also used by harness/import_transcripts.py."""

    def __init__(self, memory: AgentMemory):
        self.memory = memory
        self.client = memory._client
        self.traces: dict[str, str] = {}  # Claude session id -> open trace id

    def _run(self, coro):
        return self.memory._run(coro)

    def prompt(self, session: str, text: str, meta: dict) -> None:
        msg = self._run(self.client.short_term.add_message(session, "user", text, metadata=meta))
        trace = self._run(self.client.reasoning.start_trace(
            session, task=text[:1000], metadata=meta, triggered_by_message_id=msg.id))
        self.traces[session] = str(trace.id)

    def tool(self, session: str, name: str, arguments: dict, result) -> None:
        if session not in self.traces:
            trace = self._run(self.client.reasoning.start_trace(session, task="(tool calls without a prompt)"))
            self.traces[session] = str(trace.id)
        step = self._run(self.client.reasoning.add_step(
            self.traces[session], action=name, observation=clip(result, 500), generate_embedding=False))
        args = arguments if isinstance(arguments, dict) else {"input": arguments}
        self._run(self.client.reasoning.record_tool_call(
            step.id, name, {k: clip(v, 1000) for k, v in args.items()}, result=clip(result)))

    def answer(self, session: str, text: str, meta: dict) -> None:
        self._run(self.client.short_term.add_message(session, "assistant", text, metadata=meta))
        if session in self.traces:
            self._run(self.client.reasoning.complete_trace(
                self.traces.pop(session), outcome=text[:1000], success=True))

    def recall(self, prompt: str) -> str:
        return self.memory.search(prompt[:500])


class Daemon:
    def __init__(self):
        self.capture = Capture(AgentMemory("aura"))
        self.jobs: queue.Queue = queue.Queue()
        self.last_request = time.time()
        threading.Thread(target=self._worker, daemon=True).start()

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
        kind, session = event.get("event"), event.get("session_id") or "unknown"
        meta = {"harness": "claude", "source": "agent-memory-hook", "project": event.get("cwd", "")}
        if kind == "UserPromptSubmit":
            context = self.capture.recall(event.get("prompt", ""))  # before storing: recall earlier knowledge only
            self.jobs.put((self.capture.prompt, (session, event.get("prompt", ""), meta)))
            return {"context": context}
        if kind == "PostToolUse":
            self.jobs.put((self.capture.tool, (session, event.get("tool_name", "?"), event.get("tool_input") or {},
                                               event.get("tool_response"))))
        elif kind == "Stop" and event.get("answer"):
            self.jobs.put((self.capture.answer, (session, event["answer"], meta)))
        elif kind == "flush":
            self.jobs.join()
        return {}


def main() -> None:
    daemon = Daemon()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # health check
            self._reply({"ok": True, "queued": daemon.jobs.qsize()})

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
    daemon.capture.memory.close()


if __name__ == "__main__":
    main()

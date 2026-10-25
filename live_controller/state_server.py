"""
Minimal HTTP endpoint exposing the live controller's latest tick snapshot
as JSON, so the Next.js dashboard (frontend/) can poll cluster state
without talking to Kubernetes directly. Pure stdlib -- no new dependency --
since it only ever needs to serve one small JSON blob on request.

The frontend's own backend (a Next.js API route) is expected to fetch this
server-side and relay it to the browser, so this never needs CORS headers
or to be reachable from anywhere but localhost.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_lock = threading.Lock()
_state: dict = {"tick": -1, "tasks": [], "hosts": [], "metrics": {}, "events": []}


def update_state(new_state: dict) -> None:
    with _lock:
        _state.clear()
        _state.update(new_state)


def _snapshot() -> dict:
    with _lock:
        return dict(_state)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/state":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(_snapshot()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        pass  # keep the controller's own [HH:MM:SS] log lines the only output


def start_background(host: str = "127.0.0.1", port: int = 8787) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

"""The Explorer app — a local, offline dashboard for the whole project.

Run it:
    py explorer/app.py            # serves http://localhost:8000 and opens your browser

Why stdlib, not FastAPI
-----------------------
The spec (notes/07) recommends FastAPI, and that would be fine — but this app is meant to
be *reliable and one-command on a Windows laptop the owner will not maintain*. FastAPI +
uvicorn are not installed here, so choosing them would add a `pip install` step and a
thing to break. Python's own `http.server` needs nothing installed, so `py explorer/app.py`
just works. That is the same "minimal-friction, one command, no build" spirit the spec
asks for, taken one step further. (Recorded in DECISIONS 2026-07-29.)

What it serves
--------------
- the no-build frontend under explorer/static/
- a small read-only JSON API over the files the harness already wrote (runs/, artifacts/)
Nothing here writes to the repo; the offline core needs no key and no network.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

APP_DIR = Path(__file__).resolve().parent
STATIC = APP_DIR / "static"

# Make `explorer.lib` importable whether launched as `py explorer/app.py` or `-m`.
if str(APP_DIR.parent) not in sys.path:
    sys.path.insert(0, str(APP_DIR.parent))

from explorer.lib import artifacts, notes, runs  # noqa: E402

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".woff2": "font/woff2",
    ".map": "application/json",
}


def _q(query: dict, key: str) -> str | None:
    vals = query.get(key)
    return vals[0] if vals else None


# --- the read-only JSON API --------------------------------------------------------------
# Each handler returns (status_code, payload). The offline core lives entirely here.

def _live_status():
    # Imported lazily: live.py imports harness.env_file; keep it out of the offline path.
    from explorer.lib import live
    return 200, live.key_status()


def api_get(path: str, query: dict):
    if path == "/api/overview":
        return 200, artifacts.get_overview()

    if path == "/api/runs":
        return 200, {"palette": runs.PALETTE, "runs": runs.list_runs()}

    if path == "/api/run":
        rid = _q(query, "id")
        if not rid:
            return 400, {"error": "missing ?id="}
        replay = runs.get_replay(rid)
        if replay is None:
            return 404, {"error": f"no recording for id={rid!r}"}
        return 200, {"palette": runs.PALETTE, "run": replay}

    if path == "/api/trace":
        rid = _q(query, "id")
        if not rid:
            return 400, {"error": "missing ?id="}
        trace = runs.get_trace(rid)
        if trace is None:
            return 404, {"error": f"no trace for id={rid!r}"}
        return 200, {"id": rid, "records": trace}

    if path == "/api/evals":
        return 200, artifacts.list_evals()

    if path == "/api/eval":
        arm = _q(query, "arm")
        if not arm:
            return 400, {"error": "missing ?arm="}
        doc = artifacts.get_eval(arm)
        return (200, doc) if doc else (404, {"error": f"no eval {arm!r}"})

    if path == "/api/comparison":
        name = _q(query, "name")
        if not name:
            return 400, {"error": "missing ?name="}
        doc = artifacts.get_comparison(name)
        return (200, doc) if doc else (404, {"error": f"no comparison {name!r}"})

    if path == "/api/taxonomy":
        doc = artifacts.get_taxonomy()
        return (200, doc) if doc else (404, {"error": "no failure-taxonomy.json"})

    if path == "/api/budgets":
        return 200, artifacts.get_budgets()

    if path == "/api/learn":
        return 200, notes.learn_index()

    if path == "/api/note":
        rel = _q(query, "path")
        if not rel:
            return 400, {"error": "missing ?path="}
        md = notes.get_note_markdown(rel)
        return (200, {"path": rel, "markdown": md}) if md is not None \
            else (404, {"error": f"no note {rel!r}"})

    if path == "/api/live/status":
        return _live_status()

    return 404, {"error": f"unknown endpoint {path!r}"}


def api_post(path: str, body: dict):
    """Live-mode POST endpoints (you-play). Mock play needs no key; real play reads the ARC
    key from .env via the harness. ValueError/KeyError map to 400 (a user/session problem),
    everything else to 500."""
    from explorer.lib import live

    if path == "/api/live/play/start":
        return 200, live.start_play(game=body.get("game", "ls20"), mock=bool(body.get("mock")))

    if path == "/api/live/play/action":
        sid = body.get("session_id")
        action = body.get("action")
        if not sid or not action:
            return 400, {"error": "need session_id and action"}
        return 200, live.play_action(sid, action, body.get("x"), body.get("y"))

    if path == "/api/live/play/close":
        return 200, live.close_play(body.get("session_id", ""))

    return 404, {"error": f"unknown endpoint {path!r}"}


class Handler(BaseHTTPRequestHandler):
    server_version = "ExplorerHTTP/1.0"

    # quieter, single-line logging
    def log_message(self, fmt, *args):
        sys.stderr.write("  %s - %s\n" % (self.address_string(), fmt % args))

    def _send_json(self, status: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, url_path: str) -> None:
        rel = url_path.lstrip("/")
        if rel in ("", "/"):
            rel = "index.html"
        # /static/x maps to explorer/static/x; a bare /x also resolves under static
        rel = rel[len("static/"):] if rel.startswith("static/") else rel
        target = (STATIC / rel).resolve()
        try:
            target.relative_to(STATIC.resolve())
        except ValueError:
            self._send_json(403, {"error": "forbidden"})
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            self._send_json(404, {"error": f"not found: {url_path}"})
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",
                         CONTENT_TYPES.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path == "/api/live/watch/stream":
            self._watch_sse(query)
            return
        if path.startswith("/api/"):
            try:
                status, payload = api_get(path, query)
            except Exception as exc:  # never crash the server on one bad read
                status, payload = 500, {"error": f"{type(exc).__name__}: {exc}"}
            self._send_json(status, payload)
            return
        self._send_static(path)

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if not path.startswith("/api/"):
            self._send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            body = json.loads(raw or b"{}")
            status, payload = api_post(path, body)
        except (ValueError, KeyError) as exc:      # bad input / missing session
            status, payload = 400, {"error": str(exc)}
        except Exception as exc:                    # server-side / network failure
            status, payload = 500, {"error": f"{type(exc).__name__}: {exc}"}
        self._send_json(status, payload)

    # --- watch-agent: Server-Sent Events stream of a real agent run ---
    def _watch_sse(self, query):
        game = _q(query, "game") or "ls20"
        try:
            max_actions = int(_q(query, "max") or 8)
        except ValueError:
            max_actions = 8
        max_actions = max(1, min(max_actions, 20))  # protect the 500/day LLM free tier
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        def emit(event):
            data = json.dumps(event, ensure_ascii=False)
            self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
            self.wfile.flush()

        from explorer.lib import live
        try:
            live.watch_stream(game, max_actions, emit)
        except (BrokenPipeError, ConnectionResetError):
            return  # client navigated away; watch_stream's finally already closed the card
        except Exception as exc:
            try:
                emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
            except Exception:
                return
        try:
            emit({"type": "done"})
        except Exception:
            pass


def serve(port: int, open_browser: bool) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://localhost:{port}/"
    print("=" * 68)
    print("  project-agent — Explorer (offline)")
    print(f"  serving {url}")
    print("  offline core: no API key, no network. Ctrl-C to stop.")
    print("=" * 68)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped.")
        httpd.server_close()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="project-agent Explorer (local, offline).")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true", help="don't auto-open the browser")
    args = ap.parse_args(argv)
    serve(args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()

"""A light offline smoke check for the Explorer — its own, separate from the 154-test
harness suite (which does not and should not cover this app; see the separation contract
in notes/07). Verifies the read-only API returns real repo data with no key and no
network, and that path-traversal guards hold.

    py explorer/smoke_test.py        # prints a PASS/FAIL line per check, exits non-zero on any failure
"""

from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR.parent) not in sys.path:
    sys.path.insert(0, str(APP_DIR.parent))

from explorer.lib import artifacts, notes, runs  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    ok = bool(cond)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def check_lib() -> None:
    print("lib (direct):")
    rl = runs.list_runs()
    check("list_runs non-empty", len(rl) > 0, f"{len(rl)} runs")
    first = next((r for r in rl if not r.get("error")), None)
    check("a run parses", first is not None)
    if first:
        rep = runs.get_replay(first["id"])
        check("replay has steps", rep and len(rep["steps"]) > 0, f"{len(rep['steps'])} steps")
        s = rep["steps"][0]
        check("grid is w*h chars", len(s["grid"]) == s["w"] * s["h"], f"{len(s['grid'])} chars")
        if first.get("has_trace"):
            tr = runs.get_trace(first["id"])
            check("trace parses", tr and len(tr) > 0, f"{len(tr)} records")
    ov = artifacts.get_overview()
    check("overview counts", ov["counts"]["recorded_runs"] > 0, str(ov["counts"]))
    check("headline read from taxonomy", ov["headline"]["active_no_progress_share"] is not None,
          f"active-no-progress={ov['headline']['active_no_progress_share']}")
    ev = artifacts.list_evals()
    check("evals present", len(ev["arms"]) > 0, f"{len(ev['arms'])} arms, {len(ev['comparisons'])} comparisons")
    check("taxonomy present", artifacts.get_taxonomy() is not None)
    nf = artifacts.get_noise_floor()
    check("noise floor present", nf is not None and "headline" in nf,
          f"{(nf or {}).get('headline', {}).get('pairs_enumerated')} change-free pairs")
    # The comparison rows must arrive already judged against the band, since the view only
    # displays that verdict and never computes one.
    llm_cmp = next((c["name"] for c in ev["comparisons"]
                    if "random" not in f"{c['before']} {c['after']}"), None)
    if llm_cmp:
        doc = artifacts.get_comparison(llm_cmp)
        judged = [r for r in doc.get("rows", []) if r.get("noise")]
        check("comparison rows carry a noise verdict", len(judged) > 0,
              f"{len(judged)}/{len(doc.get('rows', []))} rows in {llm_cmp}")
        check("noise scope marked in-scope for an LLM-vs-LLM pair",
              (doc.get("noise_scope") or {}).get("in_scope") is True)
    rnd_cmp = next((c["name"] for c in ev["comparisons"]
                    if "random" in f"{c['before']} {c['after']}"), None)
    if rnd_cmp:
        scope = (artifacts.get_comparison(rnd_cmp) or {}).get("noise_scope") or {}
        check("random-arm comparison is marked out of scope", scope.get("in_scope") is False)
    check("budgets present", "model_bakeoff" in artifacts.get_budgets())
    check("learn index has views", set(notes.learn_index()) >= {"home", "replay", "evals", "taxonomy", "traces", "budgets"})
    check("note serves markdown", (notes.get_note_markdown("notes/study/05-the-agent-loop.md") or "").strip() != "")
    check("traversal guard (../CLAUDE.md)", notes.get_note_markdown("../CLAUDE.md") is None)
    check("traversal guard (abs path run)", runs.get_replay("../CLAUDE") is None)


def check_server() -> None:
    print("server (http):")
    from explorer import app
    from http.server import ThreadingHTTPServer

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(0.2)
    base = f"http://127.0.0.1:{port}"

    def get(path):
        with urllib.request.urlopen(base + path, timeout=5) as r:
            return r.status, r.read()

    def post(path, body):
        req = urllib.request.Request(
            base + path, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status, json.loads(r.read())

    try:
        for path in ["/", "/static/js/app.js", "/api/overview", "/api/runs",
                     "/api/evals", "/api/noise", "/api/taxonomy", "/api/budgets", "/api/learn",
                     "/api/live/status"]:
            status, body = get(path)
            check(f"GET {path}", status == 200 and len(body) > 0, f"{status}, {len(body)}B")
        # a bad param should 400/404, not crash
        try:
            get("/api/run?id=does-not-exist")
            check("GET bad run id -> handled", False, "expected HTTPError")
        except urllib.error.HTTPError as e:
            check("GET bad run id -> handled", e.code in (400, 404), f"HTTP {e.code}")

        # live you-play against the offline MockGame — no key, no quota, no network
        print("live (mock, offline):")
        _, start = post("/api/live/play/start", {"mock": True})
        check("play/start (mock)", start.get("mock") and start["frame"]["w"] > 0,
              f"game {start.get('game_id')}, {start['frame']['w']}x{start['frame']['h']}")
        sid = start["session_id"]
        _, act = post("/api/live/play/action", {"session_id": sid, "action": "ACTION2"})
        check("play/action", "score" in act and "legal" in act, f"changed={act.get('changed')}")
        _, closed = post("/api/live/play/close", {"session_id": sid})
        check("play/close", closed.get("ok") is True)
        try:
            post("/api/live/play/action", {"session_id": "nope", "action": "ACTION1"})
            check("action bad session -> 400", False, "expected HTTPError")
        except urllib.error.HTTPError as e:
            check("action bad session -> 400", e.code == 400, f"HTTP {e.code}")
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    print("Explorer smoke test\n" + "-" * 40)
    check_lib()
    check_server()
    print("-" * 40)
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s): {', '.join(FAILS)}")
        sys.exit(1)
    print("All checks passed. The offline core reads real repo data with no key and no network.")

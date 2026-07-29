"""Build `demo.html` — a self-contained, offline replay of real recorded games.

Why this exists
---------------
The rest of the project is a harness you *read about* (the course) or *run in a
terminal* (the scripts). Neither answers the one thing an interviewer asks first:
**"can I see it work?"** A live run is the wrong answer to that — it needs an API key,
a network, and free-tier quota, so it can die on stage. But every game the agent ever
played is already on disk, decision by decision, in `runs/*.recording.jsonl.gz`.

So this script bakes a curated handful of those recordings into a single HTML file with
no external dependencies: open it (double-click, or publish it as an Artifact) and it
replays a real game — the 64x64 screen animating on the left, and on the right the exact
action the agent took, the model's own stated reason, and the score. The score stays at
zero while the reasoning stays confident, which is the whole finding made *visible*.

Faithfulness (CLAUDE.md 3)
--------------------------
Nothing here is invented. Every frame, action, reasoning string, score and state comes
straight from the recording. `cells_changed` and `score_delta` are recomputed here from
consecutive frames rather than trusted from a second file, so a label can never drift
from the picture above it. The only presentational choice is the colour of each cell
value 0-15 — the agent reasons over the *numbers*, not the hues, so the exact palette
changes nothing; it is stated as a choice on the page.

Run it
------
    py build_demo.py            # rebuilds demo.html from the curated runs below
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
OUT = ROOT / "demo.html"

# --- The curated exhibit -------------------------------------------------------
# Each entry is one recorded game we want a viewer to be able to step through.
# `role` drives a small coloured tag; `blurb` is one plain sentence of context.
CURATED = [
    {
        "file": "sb26-7fbdac44.eval-dev-llm-p0.llm-gemini-3.5-flash-lite-objects-h0-r3-y0-p0.30.a1.5c1738fc-9352-441d-98b1-18af0dcff04a.recording.jsonl.gz",
        "label": "LLM agent · game sb26",
        "role": "llm",
        "blurb": "The full agent (with the cross-attempt progress signal) on a visually busy game. "
                 "Watch the screen change every move while the score never leaves zero.",
    },
    {
        "file": "ls20-9607627b.llm-gemini-3.5-flash-lite-objects.80.9669d0d5-f392-44d3-8064-31e06c9c2c7d.recording.jsonl.gz",
        "label": "LLM agent · game ls20",
        "role": "llm",
        "blurb": "An 80-move run. The reasoning stays fluent and purposeful the whole way "
                 "through — toward a goal the game never actually states.",
    },
    {
        "file": "ls20-9607627b.random.80.0036eedd-5088-411f-b77a-cfce5ff99522.recording.jsonl.gz",
        "label": "Random baseline · game ls20",
        "role": "random",
        "blurb": "The same game, played by a seeded coin-flip. It also scores zero — which is "
                 "exactly why beating random is the bar the LLM has to clear, and doesn't.",
    },
]

# A 16-colour palette for cell values 0-15. 0-9 are the familiar ARC colours; 10-15
# extend it for ARC-AGI-3's wider set. This is a *rendering* choice, not data.
PALETTE = [
    "#101014", "#1E88E5", "#E53935", "#43A047", "#FDD835", "#9E9E9E",
    "#E91E8C", "#FB8C00", "#4FC3F7", "#8D2b3a", "#8E24AA", "#00E676",
    "#FF80CC", "#26C6DA", "#AD1457", "#F5F5F5",
]


def clean_reason(text: str, action_label: str) -> tuple[str, bool]:
    """Return (display_reason, is_error).

    The model sometimes echoes the action as its own first line ("ACTION5\n<why>");
    we drop that so the panel shows only the rationale. And on a free-tier outage the
    fallback captured the raw API error as the "reason" — we turn that into one plain
    sentence rather than dumping a 429 JSON blob into an interview demo.
    """
    text = (text or "").strip()
    low = text.lower()
    if "resource_exhausted" in low or "429" in low or "clienterror" in low \
            or low.startswith("client error"):
        return ("Model call failed here — free-tier quota exhausted (HTTP 429). "
                "The loop fell back to a default action instead of crashing.", True)
    lines = text.splitlines()
    if lines and lines[0].strip().upper() == action_label:
        text = "\n".join(lines[1:]).strip()
    return (text, False)


def load_run(path: Path) -> dict:
    """Turn one recording file into the compact structure the page replays."""
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh if line.strip()]

    # Recordings end with a one-line game summary (no frame); keep only real frames.
    frames = [r for r in records if "frame" in r.get("data", {})]

    steps = []
    prev_grid = None
    prev_score = 0
    for i, rec in enumerate(frames):
        d = rec["data"]
        grid = d["frame"][0]  # frame is [grid]; the grid is 64x64 of values 0-15
        score = d.get("score", 0)
        ai = d.get("action_input") or {}
        act_id = ai.get("id", 0)
        reasoning = (ai.get("reasoning") or "").strip()

        if i == 0:
            action_label = "START"          # the initial screen, before any action
            reasoning, is_err = "", False
        else:
            action_label = f"ACTION{act_id}" if act_id else "RESET"
            reasoning, is_err = clean_reason(reasoning, action_label)

        cells_changed = 0
        if prev_grid is not None:
            for ra, rb in zip(prev_grid, grid):
                for a, b in zip(ra, rb):
                    if a != b:
                        cells_changed += 1

        steps.append({
            "action": action_label,
            "reason": reasoning,
            "err": is_err,
            "score": score,
            "dscore": score - prev_score,
            "changed": cells_changed,
            "state": d.get("state", ""),
            # each frame as a flat hex string: one char per cell, value 0-15 -> 0-f
            "grid": "".join(format(min(max(v, 0), 15), "x") for row in grid for v in row),
            "w": len(grid[0]),
            "h": len(grid),
        })
        prev_grid, prev_score = grid, score

    move_steps = [s for s in steps if s["action"] not in ("START", "RESET")]
    changed = sum(1 for s in move_steps if s["changed"] > 0)
    actions_used = sorted({s["action"] for s in move_steps})
    return {
        "steps": steps,
        "final_score": steps[-1]["score"] if steps else 0,
        "n_moves": len(move_steps),
        "pct_changed": round(100 * changed / len(move_steps)) if move_steps else 0,
        "actions_used": actions_used,
    }


def build() -> None:
    runs = []
    for entry in CURATED:
        path = RUNS / entry["file"]
        if not path.exists():
            print(f"  ! skipped (missing): {entry['file']}")
            continue
        data = load_run(path)
        runs.append({**entry, **data})
        print(f"  + {entry['label']:28}  {data['n_moves']:>3} moves  "
              f"final score {data['final_score']}  "
              f"{data['pct_changed']}% of moves changed the screen  "
              f"actions {data['actions_used']}")

    if not runs:
        raise SystemExit("No recordings found in runs/ — nothing to build.")

    payload = json.dumps(
        {"palette": PALETTE, "runs": runs}, ensure_ascii=False, separators=(",", ":")
    ).replace("</", "<\\/")  # so a stray '</script>' in data can't close the tag

    html = PAGE_TEMPLATE.replace("/*__DATA__*/", payload)
    OUT.write_text(html, encoding="utf-8")
    size_kb = OUT.stat().st_size / 1024
    print(f"\nWrote {OUT.name} ({size_kb:.0f} KB) with {len(runs)} runs. "
          f"Open it in a browser — no server, no keys, no network.")


PAGE_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>project-agent — watch the agent play</title>
<style>
  :root{
    --bg:#0d0f14; --panel:#161a22; --panel2:#1d222c; --ink:#e8ecf3; --dim:#9aa4b2;
    --line:#2a3140; --accent:#4FC3F7; --llm:#4FC3F7; --random:#FB8C00; --zero:#E53935;
    --ok:#43A047;
  }
  @media (prefers-color-scheme: light){
    :root{ --bg:#f4f6fa; --panel:#ffffff; --panel2:#eef1f6; --ink:#151a21;
      --dim:#5a6472; --line:#dde2ea; }
  }
  *{ box-sizing:border-box; }
  body{ margin:0; background:var(--bg); color:var(--ink);
    font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
  .wrap{ max-width:1100px; margin:0 auto; padding:22px 20px 60px; }
  header h1{ font-size:20px; margin:0 0 4px; letter-spacing:.2px; }
  header p{ margin:0; color:var(--dim); font-size:14px; }
  .pick{ display:flex; gap:10px; align-items:center; flex-wrap:wrap;
    margin:18px 0 6px; }
  select{ background:var(--panel2); color:var(--ink); border:1px solid var(--line);
    border-radius:8px; padding:8px 10px; font-size:14px; }
  .blurb{ color:var(--dim); font-size:13.5px; margin:2px 2px 16px; min-height:20px; }
  .stage{ display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:18px; }
  @media (max-width:760px){ .stage{ grid-template-columns:1fr; } }
  .card{ background:var(--panel); border:1px solid var(--line); border-radius:14px;
    padding:16px; }
  .screen-card{ display:flex; flex-direction:column; align-items:center; }
  #screen{ width:100%; max-width:420px; aspect-ratio:1/1; image-rendering:pixelated;
    border-radius:10px; background:#000; border:1px solid var(--line); }
  .cap{ color:var(--dim); font-size:12.5px; margin-top:10px; text-align:center; }
  .spark{ width:100%; max-width:420px; height:38px; margin-top:12px;
    background:var(--panel2); border:1px solid var(--line); border-radius:8px; }
  .chip{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px;
    font-weight:600; }
  .chip.llm{ background:rgba(79,195,247,.16); color:var(--llm); }
  .chip.random{ background:rgba(251,140,0,.16); color:var(--random); }
  .stepline{ display:flex; justify-content:space-between; align-items:baseline;
    margin-bottom:12px; }
  .stepline .n{ font-size:13px; color:var(--dim); }
  .action{ font-size:30px; font-weight:700; letter-spacing:.5px; }
  .action.start{ color:var(--dim); font-weight:600; font-size:22px; }
  .metrics{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:6px 0 14px; }
  .metric{ background:var(--panel2); border-radius:10px; padding:10px 12px; }
  .metric .k{ font-size:11px; text-transform:uppercase; letter-spacing:.6px;
    color:var(--dim); }
  .metric .v{ font-size:22px; font-weight:700; margin-top:2px; }
  .metric .v.zero{ color:var(--zero); }
  .metric .v.up{ color:var(--ok); }
  .barwrap{ height:6px; background:var(--line); border-radius:4px; margin-top:8px;
    overflow:hidden; }
  .bar{ height:100%; background:var(--accent); width:0%; transition:width .18s; }
  .why{ background:var(--panel2); border-left:3px solid var(--accent); border-radius:8px;
    padding:11px 13px; }
  .why.err{ border-left-color:var(--random); background:rgba(251,140,0,.10); }
  .why .k{ font-size:11px; text-transform:uppercase; letter-spacing:.6px;
    color:var(--dim); margin-bottom:5px; }
  .why .t{ font-size:14px; white-space:pre-wrap; min-height:42px; }
  .why .t.empty{ color:var(--dim); font-style:italic; }
  .controls{ display:flex; gap:10px; align-items:center; margin-top:16px;
    flex-wrap:wrap; }
  button{ background:var(--panel2); color:var(--ink); border:1px solid var(--line);
    border-radius:9px; padding:9px 14px; font-size:15px; cursor:pointer; }
  button:hover{ border-color:var(--accent); }
  button.primary{ background:var(--accent); color:#04121a; border-color:var(--accent);
    font-weight:700; min-width:96px; }
  input[type=range]{ flex:1; accent-color:var(--accent); min-width:160px; }
  .foot{ margin-top:26px; padding:16px 18px; background:var(--panel);
    border:1px solid var(--line); border-radius:14px; }
  .foot b{ color:var(--zero); }
  details{ margin-top:16px; color:var(--dim); font-size:13.5px; }
  summary{ cursor:pointer; color:var(--accent); }
  .runstat{ font-size:12.5px; color:var(--dim); margin-top:8px; }
  code{ background:var(--panel2); padding:1px 5px; border-radius:4px; font-size:12.5px; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>project-agent — watch the agent play</h1>
    <p>A real recorded game, replayed move by move. No live model, no network — this is
       exactly what happened, read back from the run log on disk.</p>
  </header>

  <div class="pick">
    <label for="run">Run:</label>
    <select id="run"></select>
    <span id="tag"></span>
  </div>
  <div class="blurb" id="blurb"></div>

  <div class="stage">
    <div class="card screen-card">
      <canvas id="screen" width="64" height="64"></canvas>
      <div class="cap">The 64&times;64 screen the agent sees. Colours map cell values
        0&ndash;15 (a display choice; the model reads the numbers).</div>
      <canvas id="spark" class="spark"></canvas>
      <div class="cap">Score over the whole game &mdash; the flat line is the point.</div>
    </div>

    <div class="card">
      <div class="stepline">
        <span class="n">Move <b id="stepno">0</b> of <span id="stepmax">0</span></span>
        <span class="n" id="state"></span>
      </div>
      <div class="action start" id="action">START</div>
      <div class="metrics">
        <div class="metric"><div class="k">Score</div>
          <div class="v" id="score">0</div></div>
        <div class="metric"><div class="k">Score change</div>
          <div class="v" id="dscore">0</div></div>
      </div>
      <div class="metric" style="margin-bottom:14px">
        <div class="k">Cells changed on screen (of 4096)</div>
        <div class="v" id="changed">0</div>
        <div class="barwrap"><div class="bar" id="changedbar"></div></div>
      </div>
      <div class="why">
        <div class="k">Why &mdash; the model's own words</div>
        <div class="t empty" id="why">(the starting screen, before any move)</div>
      </div>
    </div>
  </div>

  <div class="controls">
    <button id="prev">&#9664; Prev</button>
    <button id="play" class="primary">&#9654; Play</button>
    <button id="next">Next &#9654;</button>
    <label style="color:var(--dim);font-size:13px">Speed
      <select id="speed">
        <option value="700">slow</option>
        <option value="380" selected>normal</option>
        <option value="150">fast</option>
      </select>
    </label>
    <input type="range" id="scrub" min="0" value="0">
  </div>
  <div class="runstat" id="runstat"></div>

  <div class="foot">
    What you are watching: the agent <b>observes</b> the screen, <b>decides</b> an action
    with a stated reason, <b>acts</b>, and the game returns a new screen and a score.
    That is the whole agent loop. The screen keeps changing and the reasons stay
    confident, yet <b>the score never moves off zero</b> &mdash; the same result a random
    baseline gets. This project's finding is that <b>~88% of the agent's moves are legal,
    non-repeating, screen-changing work that makes no progress</b>, because the game
    states no goal for the loop to steer toward.
  </div>

  <details>
    <summary>What am I looking at, and is it real?</summary>
    <p>Every frame, action, reason, and score here is read verbatim from a
    <code>runs/*.recording.jsonl.gz</code> file — one of the actual games the agent
    played. "Cells changed" and "score change" are recomputed from consecutive frames at
    build time, so a label can never disagree with the picture. Rebuild this page any
    time with <code>py build_demo.py</code>. The colours are the one presentational
    choice; the agent reasons over the raw numbers, not the hues.</p>
  </details>
</div>

<script id="data" type="application/json">/*__DATA__*/</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const PAL = DATA.palette, RUNS = DATA.runs;
const $ = id => document.getElementById(id);
let run = RUNS[0], i = 0, timer = null;

// --- run selector ---
RUNS.forEach((r, k) => {
  const o = document.createElement('option');
  o.value = k; o.textContent = r.label; $('run').appendChild(o);
});

function decodeGrid(hex, w, h){
  const g = new Uint8Array(w*h);
  for (let k=0;k<hex.length;k++) g[k] = parseInt(hex[k],16);
  return g;
}
function drawScreen(step){
  const cv = $('screen'), ctx = cv.getContext('2d');
  const w = step.w, h = step.h;
  cv.width = w; cv.height = h;
  const g = decodeGrid(step.grid, w, h);
  const img = ctx.createImageData(w, h);
  for (let p=0;p<g.length;p++){
    const c = PAL[g[p]] || '#000';
    const r = parseInt(c.slice(1,3),16), gg = parseInt(c.slice(3,5),16), b = parseInt(c.slice(5,7),16);
    img.data[p*4]=r; img.data[p*4+1]=gg; img.data[p*4+2]=b; img.data[p*4+3]=255;
  }
  ctx.putImageData(img, 0, 0);
}
function drawSpark(){
  const cv = $('spark'), ctx = cv.getContext('2d');
  const W = cv.width = cv.clientWidth || 420, H = cv.height = 38;
  ctx.clearRect(0,0,W,H);
  const steps = run.steps, n = steps.length;
  const maxS = Math.max(1, ...steps.map(s=>s.score));
  // flat baseline reference
  ctx.strokeStyle = 'rgba(255,255,255,.10)'; ctx.beginPath();
  ctx.moveTo(0,H-6); ctx.lineTo(W,H-6); ctx.stroke();
  ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue('--accent');
  ctx.lineWidth = 2; ctx.beginPath();
  steps.forEach((s,k)=>{
    const x = n>1 ? (k/(n-1))*W : 0;
    const y = H-6 - (s.score/maxS)*(H-12);
    k? ctx.lineTo(x,y) : ctx.moveTo(x,y);
  });
  ctx.stroke();
  // playhead
  const px = n>1 ? (i/(n-1))*W : 0;
  ctx.strokeStyle = 'rgba(255,255,255,.5)'; ctx.lineWidth=1; ctx.beginPath();
  ctx.moveTo(px,0); ctx.lineTo(px,H); ctx.stroke();
}
function render(){
  const s = run.steps[i];
  drawScreen(s); drawSpark();
  $('stepno').textContent = i;
  $('stepmax').textContent = run.steps.length - 1;
  $('state').textContent = s.state || '';
  const act = $('action');
  act.textContent = s.action;
  act.className = 'action' + (s.action==='START'||s.action==='RESET' ? ' start':'');
  $('score').textContent = s.score;
  $('score').className = 'v' + (s.score>0 ? ' up':' zero');
  const d = $('dscore');
  d.textContent = (s.dscore>0?'+':'') + s.dscore;
  d.className = 'v' + (s.dscore>0 ? ' up' : (s.dscore<0?' zero':''));
  $('changed').textContent = s.changed;
  $('changedbar').style.width = Math.min(100, s.changed/4096*100) + '%';
  const why = $('why'), whyBox = why.closest('.why');
  if (s.err){ why.textContent = '⚠ ' + s.reason; why.className='t'; whyBox.classList.add('err'); }
  else if (s.reason){ why.textContent = s.reason; why.className='t'; whyBox.classList.remove('err'); }
  else { why.textContent = '(the starting screen, before any move)'; why.className='t empty'; whyBox.classList.remove('err'); }
  $('scrub').value = i;
}
function go(k){ i = Math.max(0, Math.min(run.steps.length-1, k)); render(); }
function stop(){ if(timer){ clearInterval(timer); timer=null; $('play').innerHTML='&#9654; Play'; } }
function play(){
  if (timer){ stop(); return; }
  if (i >= run.steps.length-1) i = 0;
  $('play').innerHTML='&#10073;&#10073; Pause';
  timer = setInterval(()=>{
    if (i >= run.steps.length-1){ stop(); return; }
    go(i+1);
  }, +$('speed').value);
}
function loadRun(k){
  stop(); run = RUNS[k]; i = 0;
  $('tag').innerHTML = '<span class="chip '+run.role+'">'+
    (run.role==='llm'?'LLM agent':'random baseline')+'</span>';
  $('blurb').textContent = run.blurb;
  $('scrub').max = run.steps.length-1;
  $('runstat').textContent =
    `${run.n_moves} moves · final score ${run.final_score} · `+
    `${run.pct_changed}% of moves changed the screen · actions used: ${run.actions_used.join(', ')}`;
  render();
}

$('run').addEventListener('change', e=>loadRun(+e.target.value));
$('prev').addEventListener('click', ()=>{ stop(); go(i-1); });
$('next').addEventListener('click', ()=>{ stop(); go(i+1); });
$('play').addEventListener('click', play);
$('scrub').addEventListener('input', e=>{ stop(); go(+e.target.value); });
window.addEventListener('resize', drawSpark);
loadRun(0);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    build()

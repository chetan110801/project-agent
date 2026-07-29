// Game replay — pick any recorded game and step/play through it: the 64×64 screen, the
// action, the model's own reasoning, score and cells-changed. Two extras the spec asks
// for: side-by-side compare (e.g. LLM vs random on the same game, driven by one scrubber)
// and a "jump to where it got stuck" control (the longest repeated-action streak).
import { api } from '../api.js';
import { el } from '../ui.js';
import { learnStrip } from '../shell.js';
import { drawScreen, drawSpark } from '../grid.js';

let PALETTE = [];
let RUNS = [];              // light summaries from /api/runs
const cache = {};          // id -> full replay
let primary = null, compare = null;
let i = 0, timer = null;

const roleLabel = r => r === 'llm' ? 'LLM agent' : r === 'random' ? 'random baseline' : r.role || 'run';
const shortId = id => id.split('.').slice(0, 2).join(' · ');

export async function render(root) {
  const data = await api('/api/runs');
  PALETTE = data.palette;
  RUNS = data.runs.filter(r => !r.error);

  root.append(
    el('div.view-head', {}, [
      el('h2', { text: 'Game replay' }),
      el('p', { text: 'A real recorded game, read back move by move from the run log — no live model, no network.' }),
    ]),
    learnStrip('replay'),
    pickerRow(),
    el('div#stage'),
    controlsRow(),
    el('div.cap#runstat', { style: 'margin-top:12px' }),
    footNote(),
  );

  // sensible default: an LLM run that visibly gets stuck
  const def = RUNS.find(r => r.role === 'llm' && r.stuck) || RUNS.find(r => r.role === 'llm') || RUNS[0];
  await selectPrimary(def.id);
}

function pickerRow() {
  const opt = (r) => el('option', { value: r.id },
    [`${shortId(r.id)} — ${roleLabel(r.role)} · ${r.n_moves} moves · score ${r.final_score}`]);
  const primarySel = el('select#primarySel', { onchange: e => selectPrimary(e.target.value) },
    RUNS.map(opt));
  const compareSel = el('select#compareSel', { onchange: e => selectCompare(e.target.value) });
  return el('div.card', { style: 'margin-bottom:16px' }, [
    el('div', { style: 'display:flex; gap:16px; flex-wrap:wrap; align-items:end' }, [
      el('label.fld', {}, ['Run', primarySel]),
      el('label.fld', {}, ['Compare with (same game)', compareSel]),
    ]),
  ]);
}

function rebuildCompareOptions() {
  const sel = document.getElementById('compareSel');
  const same = RUNS.filter(r => r.game_id === primary.game_id && r.id !== primary.id);
  sel.replaceChildren(
    el('option', { value: '' }, ['— none (single view) —']),
    ...same.map(r => el('option', { value: r.id },
      [`${roleLabel(r.role)} · ${r.n_moves} moves · score ${r.final_score}`])));
  sel.value = compare ? compare.id : '';
}

async function load(id) {
  if (!cache[id]) cache[id] = (await api('/api/run', { id })).run;
  return cache[id];
}

async function selectPrimary(id) {
  stop();
  primary = await load(id);
  document.getElementById('primarySel').value = id;
  // keep compare only if still same game
  if (compare && compare.game_id !== primary.game_id) compare = null;
  rebuildCompareOptions();
  i = 0;
  buildStage();
  render_i();
}

async function selectCompare(id) {
  stop();
  compare = id ? await load(id) : null;
  i = 0;
  buildStage();
  render_i();
}

function maxLen() {
  return Math.max(primary.steps.length, compare ? compare.steps.length : 0);
}

function buildStage() {
  const stage = document.getElementById('stage');
  stage.className = compare ? 'grid2' : '';
  stage.replaceChildren(panel('A', primary), compare ? panel('B', compare) : null);
  const scrub = document.getElementById('scrub');
  scrub.max = maxLen() - 1; scrub.value = 0;
  updateStuckButton();
}

// one player column
function panel(tag, run) {
  const stuck = run.stuck
    ? `longest repeat: ${run.stuck.action} ×${run.stuck.length} from move ${run.stuck.start_index}`
    : 'no long repeat (guards on)';
  return el('div.card', {}, [
    el('div', { style: 'display:flex; justify-content:space-between; align-items:center; margin-bottom:10px' }, [
      el('span.chip', { class: `chip ${run.role}`, text: roleLabel(run.role) }),
      el('span.dim', { style: 'font-size:12px', text: shortId(run.id) }),
    ]),
    el('canvas', { class: 'screen', id: `screen${tag}`, width: 64, height: 64 }),
    el('canvas', { class: 'spark', id: `spark${tag}` }),
    el('div.action-big', { id: `action${tag}`, text: 'START' }),
    el('div.grid3', { style: 'margin:10px 0 12px' }, [
      miniStat(`score${tag}`, 'Score'),
      miniStat(`dscore${tag}`, 'Δ score'),
      miniStat(`changed${tag}`, 'Cells changed'),
    ]),
    el('div.why', { id: `whybox${tag}` }, [
      el('div.k', { text: "Why — the model's own words" }),
      el('div', { class: 't empty', id: `why${tag}`, text: '(the starting screen, before any move)' }),
    ]),
    el('div.cap', { text: stuck }),
  ]);
}

function miniStat(id, k) {
  return el('div.stat', {}, [el('div.k', { text: k }), el('div', { class: 'v', id, text: '0', style: 'font-size:20px' })]);
}

function controlsRow() {
  return el('div.controls', {}, [
    el('button', { id: 'prev', onclick: () => { stop(); go(i - 1); } }, ['◀ Prev']),
    el('button.primary', { id: 'play', onclick: play }, ['▶ Play']),
    el('button', { id: 'next', onclick: () => { stop(); go(i + 1); } }, ['Next ▶']),
    el('button', { id: 'stuckBtn', title: 'jump to the longest repeated-action streak',
      onclick: jumpStuck }, ['⤷ Jump to where it got stuck']),
    el('label', { style: 'color:var(--dim); font-size:13px' }, ['Speed ',
      el('select', { id: 'speed' }, [
        el('option', { value: '700' }, ['slow']),
        el('option', { value: '380', selected: 'selected' }, ['normal']),
        el('option', { value: '150' }, ['fast']),
      ])]),
    el('input', { type: 'range', id: 'scrub', min: 0, value: 0,
      oninput: e => { stop(); go(+e.target.value); } }),
  ]);
}

function updateStuckButton() {
  const btn = document.getElementById('stuckBtn');
  const s = (primary && primary.stuck) || (compare && compare.stuck);
  btn.disabled = !s;
}

function jumpStuck() {
  stop();
  const s = (primary && primary.stuck) || (compare && compare.stuck);
  if (s) go(s.start_index);
}

function paintOne(tag, run, idx) {
  const step = run.steps[Math.min(idx, run.steps.length - 1)];
  drawScreen(document.getElementById(`screen${tag}`), step, PALETTE);
  drawSpark(document.getElementById(`spark${tag}`), run.steps, Math.min(idx, run.steps.length - 1));
  const act = document.getElementById(`action${tag}`);
  act.textContent = step.action;
  act.className = 'action-big' + (['START', 'RESET'].includes(step.action) ? ' start' : '');
  const score = document.getElementById(`score${tag}`);
  score.textContent = step.score; score.className = 'v' + (step.score > 0 ? ' ok' : ' zero');
  const d = document.getElementById(`dscore${tag}`);
  d.textContent = (step.dscore > 0 ? '+' : '') + step.dscore;
  d.className = 'v' + (step.dscore > 0 ? ' ok' : step.dscore < 0 ? ' zero' : '');
  document.getElementById(`changed${tag}`).textContent = step.changed;
  const why = document.getElementById(`why${tag}`), box = document.getElementById(`whybox${tag}`);
  if (step.err) { why.textContent = '⚠ ' + step.reason; why.className = 't'; box.classList.add('err'); }
  else if (step.reason) { why.textContent = step.reason; why.className = 't'; box.classList.remove('err'); }
  else { why.textContent = '(the starting screen, before any move)'; why.className = 't empty'; box.classList.remove('err'); }
}

function render_i() {
  paintOne('A', primary, i);
  if (compare) paintOne('B', compare, i);
  document.getElementById('scrub').value = i;
  const rs = document.getElementById('runstat');
  rs.textContent = `${primary.n_moves} moves · final score ${primary.final_score} · `
    + `${primary.pct_changed}% of moves changed the screen · actions used: ${primary.actions_used.join(', ')}`
    + (compare ? `   ·vs·   ${roleLabel(compare.role)}: ${compare.n_moves} moves, score ${compare.final_score}` : '');
}

function go(k) { i = Math.max(0, Math.min(maxLen() - 1, k)); render_i(); }

function stop() {
  if (timer) { clearInterval(timer); timer = null; }
  const b = document.getElementById('play'); if (b) b.textContent = '▶ Play';
}

function play() {
  if (timer) { stop(); return; }
  if (i >= maxLen() - 1) i = 0;
  const btn = document.getElementById('play'); btn.textContent = '❚❚ Pause';
  const canvas = document.getElementById('screenA');
  timer = setInterval(() => {
    if (!document.body.contains(canvas)) { stop(); return; }  // navigated away
    if (i >= maxLen() - 1) { stop(); return; }
    go(i + 1);
  }, +document.getElementById('speed').value);
}

function footNote() {
  return el('div.card', { style: 'margin-top:20px' }, [
    el('div', { html:
      "You are watching the agent <b>observe</b> the screen, <b>decide</b> an action with a "
      + "stated reason, <b>act</b>, and get a new screen and score — the whole agent loop. The "
      + "screen keeps changing and the reasons stay confident, yet the score never leaves zero. "
      + "Every frame, action, reason and score is read verbatim from the recording; "
      + "cells-changed is recomputed from consecutive frames so a label can never drift from the picture." }),
  ]);
}

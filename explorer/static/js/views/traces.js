// Traces — browse one run's raw decision records (the receipts). This is the exact JSONL
// the evals and the failure taxonomy are computed from, so "why did it do that?" has an
// answer you can read line by line.
import { api } from '../api.js';
import { el, fmt } from '../ui.js';
import { learnStrip } from '../shell.js';

const shortId = id => id.split('.').slice(0, 2).join(' · ');

export async function render(root) {
  const { runs } = await api('/api/runs');
  const withTrace = runs.filter(r => r.has_trace && !r.error);

  root.append(
    el('div.view-head', {}, [
      el('h2', { text: 'Traces' }),
      el('p', { text: 'One append-only JSONL record per decision — the same files the evals and taxonomy read.' }),
    ]),
    learnStrip('traces'),
    el('div.card', {}, [
      el('label.fld', {}, ['Run',
        el('select', { id: 'trSel', onchange: e => show(e.target.value) },
          withTrace.map(r => el('option', { value: r.id },
            [`${shortId(r.id)} — ${r.role} · ${r.n_moves} moves`])))]),
    ]),
    el('div#trBody'),
  );
  if (withTrace.length) show(withTrace[0].id);
}

async function show(id) {
  const body = document.getElementById('trBody');
  body.replaceChildren(el('div.loading', { text: `Loading trace for ${shortId(id)}…` }));
  const { records } = await api('/api/trace', { id });
  const start = records.find(r => r.kind === 'episode_start') || {};
  const steps = records.filter(r => r.kind === 'step');
  const end = records.find(r => r.kind === 'episode_end');

  body.replaceChildren(
    el('div.card', { style: 'margin-top:14px' }, [
      el('div', { style: 'display:flex; gap:8px; flex-wrap:wrap; margin-bottom:6px' }, [
        el('span.pill', { text: `policy: ${start.policy || '?'}` }),
        el('span.pill', { text: `max_actions: ${start.max_actions ?? '?'}` }),
        el('span.pill', { text: `${steps.length} steps` }),
        el('span.pill', { text: `final score: ${(end || steps[steps.length - 1] || {}).score ?? 0}` }),
      ]),
      el('p.dim', { style: 'font-size:12px; margin:2px 0 0', text: `run_id ${start.run_id || id}` }),
    ]),
    el('div.card.scroll-x', { style: 'margin-top:12px' }, [
      el('div.scroll-y', {}, el('table.data', {}, [
        el('thead', {}, el('tr', {}, ['#', 'Action', 'OK', 'Δscore', 'Δcells', 'legal', 'latency', "Model's reason / note"]
          .map(h => el('th', { text: h })))),
        el('tbody', {}, steps.map(s => el('tr', {}, [
          el('td.dim', { text: s.index }),
          el('td', {}, [el('b', { text: s.action })]),
          el('td', {}, [el('span', { class: 'chip ' + (s.accepted ? 'ok' : 'zero'), text: s.accepted ? 'yes' : 'no' })]),
          el('td', { text: fmt.num(s.score_delta) }),
          el('td', { text: fmt.num(s.cells_changed) }),
          el('td.dim', { text: s.legal_options }),
          el('td.dim', { text: s.latency_ms != null ? Math.round(s.latency_ms) + 'ms' : '—' }),
          el('td', { style: 'max-width:440px' }, [reasonCell(s)]),
        ]))),
      ])),
    ]),
  );
}

function reasonCell(s) {
  const wrap = el('div');
  if (s.note) wrap.append(el('div', { class: 'chip warn', style: 'margin-bottom:4px', text: s.note }));
  const r = (s.reasoning || '').trim();
  wrap.append(el('div', { class: r ? '' : 'dim', style: 'white-space:pre-wrap; font-size:12.5px',
    text: r || '(no reason recorded)' }));
  return wrap;
}

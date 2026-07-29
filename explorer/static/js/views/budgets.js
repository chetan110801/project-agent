// Budgets — the three you actually spend on a free tier: tokens per call, requests per day
// (the 500/day cap), and latency (the model bakeoff, where the fastest model on paper was
// the wrong one). All from artifacts/*budget*.json, model-bakeoff.json and the usage log.
import { api } from '../api.js';
import { el, fmt } from '../ui.js';
import { learnStrip } from '../shell.js';

export async function render(root) {
  const b = await api('/api/budgets');

  root.append(
    el('div.view-head', {}, [
      el('h2', { text: 'Budgets' }),
      el('p', { text: 'Tokens · requests per day · latency — the real limits of a free tier, measured.' }),
    ]),
    learnStrip('budgets'),
    usageCard(b.usage),
    tokenCard(b.llm_budget),
    bakeoffCard(b.model_bakeoff),
  );
}

// --- requests per day ---
function usageCard(u) {
  if (!u) return el('div.notice.info', { style: 'margin-bottom:16px',
    text: 'No local usage log (artifacts/llm-usage.jsonl is per-machine and gitignored).' });
  const used = u.by_day.length ? Math.max(...u.by_day.map(d => d.calls)) : 0;
  return el('div.card', { style: 'margin-bottom:16px' }, [
    el('div.section-title', { style: 'margin-top:0', text: 'Requests per day — the 500/day wall' }),
    el('div.grid4', {}, [
      el('div.stat', {}, [el('div.k', { text: 'Calls logged (all time)' }), el('div.v', { text: fmt.num(u.total) })]),
      el('div.stat', {}, [el('div.k', { text: 'Succeeded' }), el('div', { class: 'v ok', text: fmt.num(u.ok) })]),
      el('div.stat', {}, [el('div.k', { text: 'Failed (429 etc.)' }), el('div', { class: 'v zero', text: fmt.num(u.fail) })]),
      el('div.stat', {}, [el('div.k', { text: 'Free daily limit' }), el('div.v', { text: fmt.num(u.daily_limit) }),
        el('div.sub', { text: `busiest day: ${used} calls` })]),
    ]),
    u.by_day.length ? el('div', { style: 'margin-top:14px' }, [
      el('div.hbars', {}, u.by_day.slice(-8).map(d =>
        el('div.hbar', {}, [
          el('div.mono', { text: d.day }),
          el('div.track', {}, [el('div.fill', {
            style: `width:${Math.min(100, d.calls / u.daily_limit * 100).toFixed(1)}%; background:var(--accent)` })]),
          el('div.num', { text: `${d.calls}/${u.daily_limit}` }),
        ]))),
    ]) : null,
    el('p.dim', { style: 'font-size:12px; margin-top:10px',
      text: 'The daily counter is per-machine derived state, reconstructable from the traces — so it is not committed.' }),
  ]);
}

// --- tokens per call ---
function tokenCard(bud) {
  if (!bud) return el('div');
  const rows = bud.rows || [];
  return el('div.card', { style: 'margin-bottom:16px' }, [
    el('div.section-title', { style: 'margin-top:0', text: 'Tokens per call → games per day' }),
    el('div.scroll-x', {}, el('table.data', {}, [
      el('thead', {}, el('tr', {}, ['Model', 'Encoding', 'Tokens/call', 'RPM', 'TPM', 'Binding limit', 'Games/day']
        .map(h => el('th', { text: h })))),
      el('tbody', {}, rows.map(r => el('tr', {}, [
        el('td', {}, [el('b', { text: r.model })]),
        el('td.dim', { text: r.encoding }),
        el('td', { text: fmt.num(r.prompt_tokens_per_call) }),
        el('td', { text: fmt.num(r.rpm) }),
        el('td', { text: fmt.num(r.tpm) }),
        el('td', {}, [el('span.pill', { text: r.binding_limit })]),
        el('td', {}, [el('b', { text: fmt.num(r.games_per_day) })]),
      ]))),
    ])),
    el('p.dim', { style: 'font-size:12px; margin-top:10px',
      text: `Source: ${bud.limits_source}. ${(bud.assumptions || {}).prompt || ''}` }),
  ]);
}

// --- latency: the model bakeoff ---
function bakeoffCard(bo) {
  if (!bo) return el('div');
  const rows = bo.results || [];
  return el('div.card', {}, [
    el('div.section-title', { style: 'margin-top:0', text: 'Latency — the bakeoff (fastest on paper ≠ usable)' }),
    el('p.dim', { style: 'font-size:12.5px; margin:0 0 12px',
      text: `${bo.calls_per_model} calls/model on a real ${bo.prompt_chars}-char prompt, ${bo.timeout_seconds}s timeout.` }),
    el('div.scroll-x', {}, el('table.data', {}, [
      el('thead', {}, el('tr', {}, ['Model', 'Answered', 'Usable actions', 'Median ms', 'RPM', 'RPD', 'Games/day']
        .map(h => el('th', { text: h })))),
      el('tbody', {}, rows.map(r => el('tr', {}, [
        el('td', {}, [el('b', { text: r.model })]),
        el('td', {}, [el('span', { class: 'chip ' + (r.answered ? 'ok' : 'zero'),
          text: `${r.answered}/${r.calls}` })]),
        el('td', { text: fmt.num(r.usable_actions) }),
        el('td', { text: r.median_ms != null ? fmt.num(Math.round(r.median_ms)) : '— timed out' }),
        el('td', { text: fmt.num(r.rpm) }),
        el('td', { text: fmt.num(r.rpd) }),
        el('td', { text: fmt.num(r.games_per_day_at_80_actions) }),
      ]))),
    ])),
    el('p.dim', { style: 'font-size:12px; margin-top:10px', html:
      'The models with the biggest paper quota answered <b>0/3</b> real prompts — they timed out. '
      + 'The chosen model (gemini-3.5-flash-lite) is slower on the spec sheet but actually replies.' }),
  ]);
}

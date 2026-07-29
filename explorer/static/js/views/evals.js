// Evals — the arms that were run, each arm's metrics tagged steering / outcome / cost, and
// the before/after comparisons that decide whether a change is kept. Every field is read
// from artifacts/evals/*.json; the app computes nothing new.
import { api } from '../api.js';
import { el, fmt } from '../ui.js';
import { learnStrip } from '../shell.js';

const KIND = {
  steering: ['illegal_action_rate', 'no_change_rate', 'revisit_rate', 'top_action_share',
    'top_action_share_excess', 'longest_repeat_streak', 'distinct_actions', 'distinct_targets',
    'usable_reply_rate'],
  outcome: ['final_score', 'levels_completed', 'wins', 'level1_ratio', 'game_overs', 'failed_episodes'],
  cost: ['wall_seconds', 'llm_calls', 'llm_input_tokens', 'seconds_waited', 'llm_retries', 'actions', 'episodes'],
};
const kindOf = (m) => Object.entries(KIND).find(([, ms]) => ms.includes(m))?.[0] || 'other';
const KIND_CHIP = { steering: 'other', outcome: 'ok', cost: 'warn', other: 'other' };

export async function render(root) {
  const { arms, comparisons } = await api('/api/evals');

  root.append(
    el('div.view-head', {}, [
      el('h2', { text: 'Evals' }),
      el('p', { text: 'A fixed game suite, run on every change. Metrics tagged steering / outcome / cost; a change is only kept if the before/after numbers justify it.' }),
    ]),
    learnStrip('evals'),
    el('div.section-title', { text: `Arms run (${arms.length})` }),
    armsTable(arms),
    el('div#armDetail'),
    el('div.section-title', { text: 'How big a difference counts (the measured noise band)' }),
    el('div#noiseBand'),
    el('div.section-title', { text: `Before / after comparisons (${comparisons.length})` }),
    comparePicker(comparisons),
    el('div#cmpDetail'),
  );
  if (arms.length) showArm(arms[0].arm);
  showNoiseBand();
  if (comparisons.length) showComparison(comparisons[0].name);
}

// The noise band: how far each metric drifts between two runs of the SAME configuration.
// Without it no row in any comparison below can be read, so it sits above them on the page.
async function showNoiseBand() {
  const box = document.getElementById('noiseBand');
  let doc;
  try {
    doc = await api('/api/noise');
  } catch {
    box.replaceChildren(el('div.notice.info', {
      text: 'No noise-floor.json yet — run: py scripts/noise_floor.py',
    }));
    return;
  }
  const h = doc.headline || {};
  const group = (doc.groups || [])[0] || {};
  const nulls = group.null || {};
  const rows = Object.entries(nulls)
    .map(([m, n]) => ({ m, ...n }))
    .sort((a, b) => (a.kind + a.m).localeCompare(b.kind + b.m));

  box.replaceChildren(el('div.card', {}, [
    el('p', { style: 'margin:0 0 8px', html:
      `Each arm is <b>one</b> run and the model samples, so the same setup twice gives two `
      + `different numbers. These are ${fmt.num(h.pairs_enumerated)} A/B experiments in which `
      + `the change was <b>nothing at all</b> — every way of splitting `
      + `${(group.runs || []).length} identical runs of ${(group.games || []).length} games into `
      + `two arms sharing no episode. A real difference below its metric's band tells you nothing.` }),
    el('p.dim', { style: 'font-size:12.5px; margin:0 0 10px',
      text: `configuration measured: ${group.config || '—'} · runs: ${(group.runs || []).join(', ')}` }),
    el('div.scroll-x', {}, el('table.data', {}, [
      el('thead', {}, el('tr', {}, ['Metric', 'Kind', 'Typical (p50)', 'Band (p95)', 'Widest seen'].map(h2 => el('th', { text: h2 })))),
      el('tbody', {}, rows.map(r => el('tr', {}, [
        el('td.mono', { text: r.m }),
        el('td', {}, [el('span', { class: `chip ${KIND_CHIP[r.kind] || 'other'}`, text: r.kind })]),
        el('td', { text: fmt.num(r.null_p50) }),
        el('td', {}, [el('b', { text: fmt.num(r.null_p95) })]),
        el('td', {}, [r.never_moved
          ? el('span.dim', { text: 'never moved' })
          : el('span', { text: fmt.num(r.null_max) })]),
      ]))),
    ])),
    el('p.dim', { style: 'font-size:12px; margin-top:10px', html:
      '<b>Never moved</b> means these 16 episodes never disagreed — not that the metric cannot '
      + 'move. More runs could only widen a band, never narrow it, so <i>inside</i> the band is '
      + 'decisively not evidence while just outside it is suggestive, not proven.' }),
  ]));
}

function armsTable(arms) {
  const head = ['Arm', 'Policy', 'Model', 'Episodes', 'Actions', 'Final score', 'Wins', 'level1_ratio'];
  return el('div.card.scroll-x', {}, [
    el('table.data', {}, [
      el('thead', {}, el('tr', {}, head.map(h => el('th', { text: h })))),
      el('tbody', {}, arms.map(a =>
        el('tr', { style: 'cursor:pointer', onclick: () => showArm(a.arm) }, [
          el('td', {}, [el('b', { text: a.arm })]),
          el('td', { text: a.policy || '—' }),
          el('td.dim', { text: a.model || '—' }),
          el('td', { text: fmt.num(a.episodes) }),
          el('td', { text: fmt.num(a.actions) }),
          el('td', {}, [el('span', { class: a.final_score ? '' : 'dir-worse', text: fmt.num(a.final_score) })]),
          el('td', { text: fmt.num(a.wins) }),
          el('td', { text: fmt.fixed(a.level1_ratio, 3) }),
        ]))),
    ]),
  ]);
}

async function showArm(arm) {
  const box = document.getElementById('armDetail');
  box.replaceChildren(el('div.loading', { text: `Loading ${arm}…` }));
  const doc = await api('/api/eval', { arm });
  const agg = doc.aggregate || {};
  const cfg = doc.config || {};
  const rows = Object.entries(agg).map(([m, v]) => ({ m, v, kind: kindOf(m) }))
    .sort((a, b) => (a.kind + a.m).localeCompare(b.kind + b.m));

  box.replaceChildren(el('div.card', { style: 'margin-top:14px' }, [
    el('div', { style: 'display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:6px' }, [
      el('b', { text: doc.arm }),
      el('span.pill', { text: `${doc.suite} suite` }),
      el('span.pill', { text: `${(doc.games || []).length} games` }),
      cfg.model ? el('span.pill', { text: cfg.model }) : null,
      cfg.encoder ? el('span.pill', { text: `encoder: ${cfg.encoder}` }) : null,
      el('span.pill', { text: `history: ${cfg.history}` }),
    ]),
    el('p.dim', { style: 'font-size:12.5px; margin:2px 0 12px',
      text: `games: ${(doc.games || []).join(', ')}` }),
    el('div.scroll-x', {}, el('table.data', {}, [
      el('thead', {}, el('tr', {}, ['Metric', 'Kind', 'Value'].map(h => el('th', { text: h })))),
      el('tbody', {}, rows.map(r => el('tr', {}, [
        el('td.mono', { text: r.m }),
        el('td', {}, [el('span', { class: `chip ${KIND_CHIP[r.kind]}`, text: r.kind })]),
        el('td', { text: fmt.num(r.v) }),
      ]))),
    ])),
  ]));
}

function comparePicker(comparisons) {
  if (!comparisons.length) return el('div.notice.info', { text: 'No comparisons on disk.' });
  return el('div.card', {}, [
    el('label.fld', {}, ['Comparison',
      el('select', { id: 'cmpSel', onchange: e => showComparison(e.target.value) },
        comparisons.map(c => el('option', { value: c.name },
          [`${c.before} → ${c.after}   (${(c.config_changed || []).join(', ') || 'multi'})`]))),
    ]),
  ]);
}

async function showComparison(name) {
  const box = document.getElementById('cmpDetail');
  box.replaceChildren(el('div.loading', { text: `Loading ${name}…` }));
  const doc = await api('/api/comparison', { name });
  const dir = (d) => el('td', { class: d === 'better' ? 'dir-better' : d === 'worse' ? 'dir-worse' : 'dir-same',
    text: d === 'better' ? '▲ better' : d === 'worse' ? '▼ worse' : '— same' });

  // Each row is also judged against the band above: did this change move the metric further
  // than a change of nothing routinely does? A row the audit did not cover shows a dash
  // rather than a verdict.
  const verdict = (n) => {
    if (!n) return el('td.dim', { text: '—' });
    if (n.inside_noise) {
      return el('td.dim', { text: `inside noise (band ${fmt.num(n.null_p95)})` });
    }
    return el('td', {}, [el('b', {
      text: n.exceeds_null_max ? 'beyond every change-free pair' : `survives (band ${fmt.num(n.null_p95)})`,
    })]);
  };
  const scope = doc.noise_scope;

  box.replaceChildren(el('div.card', { style: 'margin-top:14px' }, [
    el('div', { style: 'margin-bottom:8px' }, [
      el('b', { text: `${doc.before} → ${doc.after}` }),
      el('span.dim', { style: 'margin-left:10px; font-size:12.5px',
        text: `changed: ${(doc.config_changed || []).join(', ')} · `
          + `${doc.single_variable ? 'single variable' : 'multi-variable'} · ${doc.same_games ? 'same games' : 'different games'}` }),
    ]),
    scope && !scope.in_scope
      ? el('div.notice.warn', { style: 'margin-bottom:10px', text: scope.note })
      : scope
        ? el('p.dim', { style: 'font-size:12.5px; margin:0 0 10px',
          text: `${scope.rows_inside_noise} of ${scope.rows_judged} rows are inside the noise band.` })
        : null,
    el('div.scroll-x', {}, el('table.data', {}, [
      el('thead', {}, el('tr', {}, ['Metric', 'Kind', 'Before', 'After', 'Direction', 'vs noise band'].map(h => el('th', { text: h })))),
      el('tbody', {}, (doc.rows || []).map(r => el('tr', {}, [
        el('td.mono', { text: r.metric }),
        el('td', {}, [el('span', { class: `chip ${KIND_CHIP[r.kind] || 'other'}`, text: r.kind })]),
        el('td', { text: fmt.num(r.before) }),
        el('td', { text: fmt.num(r.after) }),
        dir(r.direction),
        verdict(r.noise),
      ]))),
    ])),
    el('p.dim', { style: 'font-size:12px; margin-top:10px', html:
      'Direction is about the <i>metric</i>, not the outcome — a steering metric can improve while '
      + 'the score stays zero. That gap is the whole finding. The last column is the second filter: '
      + 'a direction inside the noise band is not a result at all.' }),
  ]));
}

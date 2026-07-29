// Home / overview — the project at a glance: the honest headline (the wall), the four
// experiments, the counts, and jump-links into every other view. All numbers come from
// /api/overview, which reads them live from the taxonomy + the runs on disk.
import { api } from '../api.js';
import { el, stat, fmt } from '../ui.js';
import { learnStrip } from '../shell.js';

export async function render(root) {
  const ov = await api('/api/overview');
  const h = ov.headline, c = ov.counts;

  root.append(
    el('div.view-head', {}, [
      el('h2', { text: 'The project at a glance' }),
      el('p', { text: ov.title }),
    ]),
    learnStrip('home'),

    // the honest headline
    el('div.card', { style: 'border-left:4px solid var(--zero)' }, [
      el('div.section-title', { text: 'The headline — reported honestly' }),
      el('p', { text: h.one_liner, style: 'margin:0 0 14px; font-size:15px' }),
      el('div.grid3', {}, [
        stat('Active, no progress', fmt.pct(h.active_no_progress_share, 0), {
          zero: true, sub: 'legal, non-repeating, screen-changing work that gets nowhere' }),
        stat('Moves that made progress', fmt.pct(h.progress_share, 0), {
          zero: true, sub: 'the score never moves off zero' }),
        stat('Final score vs random', '0 = 0', {
          sub: 'the agent ties a seeded coin-flip on the outcome that counts' }),
      ]),
      el('p.dim', { style: 'margin:12px 2px 0; font-size:12.5px',
        text: `Measured over ${fmt.num(h.taxonomy_actions)} actions in ${fmt.num(h.taxonomy_episodes)} `
          + `episodes of the current default arm (${h.taxonomy_arm}).` }),
    ]),

    // the four experiments
    el('div.section-title', { text: 'Four controlled experiments — each changed behaviour, moved the score not at all' }),
    el('div.grid4', {}, ov.experiments.map(x =>
      el('div.card', {}, [
        el('div', { style: 'font-size:12px; color:var(--dim)', text: `Experiment ${x.n}` }),
        el('div', { style: 'font-weight:700; margin:5px 0 8px; font-size:14px', text: x.name }),
        el('div.dim', { style: 'font-size:12.5px', text: x.result }),
      ]))),

    // counts + jump links
    el('div.section-title', { text: 'What is in here' }),
    el('div.grid4', {}, [
      jump('#/replay', 'Recorded games', c.recorded_runs, `${c.games} distinct games · ${c.runs_with_trace} with traces`),
      jump('#/evals', 'Eval arms', c.eval_arms, `${c.comparisons} before/after comparisons`),
      jump('#/taxonomy', 'Failure taxonomy', '6 buckets', 'every action counted into one'),
      jump('#/budgets', 'Budgets', '3 spent', 'tokens · requests/day · latency'),
    ]),

    el('p.dim', { style: 'margin-top:22px; font-size:12.5px', html:
      'Everything here is read from files already in the repo — <code>runs/</code> and '
      + '<code>artifacts/</code>. No API key, no network. Turn on <b>Learn</b> (top-right) '
      + 'to get a plain-language explainer and the matching study note on every view.' }),
  );
}

function jump(href, k, v, sub) {
  return el('a', { href, style: 'text-decoration:none' }, [
    el('div.stat', { style: 'height:100%' }, [
      el('div.k', { text: k }),
      el('div.v', { text: String(v) }),
      el('div.sub', { text: sub }),
    ]),
  ]);
}

// Failure taxonomy — every recorded action sorted into one of six priority buckets, shown
// as a bar chart. The headline: ~88% active-but-no-progress, 0% progress. Straight from
// artifacts/failure-taxonomy.json.
import { api } from '../api.js';
import { el, fmt } from '../ui.js';
import { learnStrip } from '../shell.js';

const COLOR = {
  illegal_action: '#E53935', dead_action: '#FB8C00', revisit: '#B388FF',
  perseveration: '#FDD835', active_no_progress: '#4FC3F7', progress: '#43A047',
};

export async function render(root) {
  const tax = await api('/api/taxonomy');
  const order = tax.bucket_order || Object.keys(COLOR);
  const meaning = tax.bucket_meaning || {};

  // build the set of views: the headline arm + every family
  const views = {};
  if (tax.headline_llm_default_now) views['headline (current default arm)'] = tax.headline_llm_default_now;
  for (const [k, v] of Object.entries(tax.by_family || {})) views[k] = v;
  const keys = Object.keys(views);

  root.append(
    el('div.view-head', {}, [
      el('h2', { text: 'Failure taxonomy' }),
      el('p', { text: 'Every action counted into one of six priority buckets. The wall, as a table.' }),
    ]),
    learnStrip('taxonomy'),
    el('div.grid3', {}, [
      el('div.stat', {}, [el('div.k', { text: 'Episodes read' }), el('div.v', { text: fmt.num(tax.episodes_read) })]),
      el('div.stat', {}, [el('div.k', { text: 'Actions classified' }), el('div.v', { text: fmt.num(tax.actions_classified) })]),
      el('div.stat', {}, [el('div.k', { text: 'Perseveration threshold' }),
        el('div.v', { text: `≥${tax.perseveration_streak_threshold}` }), el('div.sub', { text: 'repeats in a row' })]),
    ]),
    el('div.card', { style: 'margin-top:16px' }, [
      el('label.fld', { style: 'margin-bottom:14px' }, ['Show buckets for',
        el('select', { id: 'famSel', onchange: e => paint(views[e.target.value], order) },
          keys.map(k => el('option', { value: k }, [k])))]),
      el('div#chart'),
    ]),
    legend(order, meaning),
    el('p.dim', { style: 'font-size:12.5px; margin-top:14px',
      text: `Generated from: ${tax.generated_from}` }),
  );

  paint(views[keys[0]], order);
}

function paint(fam, order) {
  const chart = document.getElementById('chart');
  const buckets = fam.buckets || {};
  const total = fam.actions || Object.values(buckets).reduce((s, b) => s + (b.count || 0), 0);
  chart.replaceChildren(
    el('div', { style: 'margin-bottom:10px' }, [
      el('b', { text: fam.arm || '' }),
      el('span.dim', { style: 'margin-left:8px; font-size:12.5px',
        text: `${fmt.num(fam.episodes)} episodes · ${fmt.num(total)} actions` }),
    ]),
    el('div.hbars', {}, order.map(name => {
      const b = buckets[name] || { count: 0, share: 0 };
      const pct = (b.share != null ? b.share : (total ? b.count / total : 0)) * 100;
      return el('div.hbar', {}, [
        el('div', {}, [el('span.mono', { text: name })]),
        el('div.track', {}, [el('div.fill', { style: `width:${pct.toFixed(1)}%; background:${COLOR[name] || '#888'}` })]),
        el('div.num', { text: `${pct.toFixed(1)}%` }),
      ]);
    })),
  );
}

function legend(order, meaning) {
  return el('div.card', { style: 'margin-top:16px' }, [
    el('div.section-title', { style: 'margin-top:0', text: 'What each bucket means' }),
    el('div', {}, order.map(name =>
      el('div', { style: 'display:flex; gap:10px; align-items:baseline; margin-bottom:7px' }, [
        el('span', { style: `flex:0 0 14px; height:14px; border-radius:3px; background:${COLOR[name] || '#888'}; display:inline-block` }),
        el('span.mono', { style: 'flex:0 0 160px', text: name }),
        el('span.dim', { style: 'font-size:13px', text: meaning[name] || '' }),
      ]))),
  ]);
}

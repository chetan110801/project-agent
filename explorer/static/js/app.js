// The Explorer shell: Learn/Demo toggle, hash router, and the view registry. Each view is
// a module exporting `render(root)`; the router swaps them into <main> on hash change.
import { loadLearn } from './shell.js';
import { el, loading, errorCard } from './ui.js';

import * as home from './views/home.js';
import * as replay from './views/replay.js';
import * as evals from './views/evals.js';
import * as taxonomy from './views/taxonomy.js';
import * as traces from './views/traces.js';
import * as budgets from './views/budgets.js';
import * as live from './views/live.js';

const VIEWS = { home, replay, evals, taxonomy, traces, budgets, live };
const ORDER = ['home', 'replay', 'evals', 'taxonomy', 'traces', 'budgets', 'live'];
const app = document.getElementById('app');
const tabs = document.getElementById('tabs');

function currentRoute() {
  const id = (location.hash.replace(/^#\//, '') || 'home').split('?')[0];
  return VIEWS[id] ? id : 'home';
}

async function route() {
  const id = currentRoute();
  [...tabs.querySelectorAll('a')].forEach(a =>
    a.classList.toggle('active', a.getAttribute('href') === `#/${id}`));
  app.replaceChildren(loading());
  try {
    const root = el('div');
    await VIEWS[id].render(root);
    app.replaceChildren(root);
    window.scrollTo(0, 0);
  } catch (err) {
    console.error(err);
    app.replaceChildren(errorCard(err));
  }
}

// --- Learn/Demo toggle (persisted) ---
const learnToggle = document.getElementById('learnToggle');
function applyLearn(on) {
  document.body.classList.toggle('learn', on);
  learnToggle.checked = on;
  localStorage.setItem('explorer.learn', on ? '1' : '0');
}
learnToggle.addEventListener('change', () => applyLearn(learnToggle.checked));

async function boot() {
  applyLearn(localStorage.getItem('explorer.learn') === '1');
  await loadLearn();
  window.addEventListener('hashchange', route);
  if (!location.hash) location.hash = '#/home';
  route();
}

boot();

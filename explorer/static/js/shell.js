// Shared shell services the views use: the Learn-mode explainer strip and the note modal.
// Kept out of app.js so every view can import them without a circular dependency.
import { api } from './api.js';
import { el } from './ui.js';
import { renderMarkdown } from './md.js';

let LEARN = {};

export async function loadLearn() {
  try { LEARN = await api('/api/learn'); } catch { LEARN = {}; }
}

// The purple "what is this?" strip shown at the top of a view when Learn mode is on.
// Hidden by CSS (body:not(.learn)) in Demo mode, so it costs nothing there.
export function learnStrip(viewId) {
  const info = LEARN[viewId];
  if (!info) return el('div');
  return el('div.learn-strip', {}, [
    el('div.lead', { text: 'Learn mode · what is this?' }),
    el('div.blurb', { text: info.blurb }),
    el('div.links', {}, (info.notes || []).map(n =>
      el('button', { onclick: () => openNote(n.file, n.title) }, [`📘 ${n.title}`]))),
  ]);
}

const back = document.getElementById('modalBack');
const body = document.getElementById('modalBody');
document.getElementById('modalClose').addEventListener('click', closeNote);
back.addEventListener('click', e => { if (e.target === back) closeNote(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeNote(); });

export async function openNote(path, title) {
  body.innerHTML = `<p class="dim">Loading ${title || path}…</p>`;
  back.classList.add('open');
  try {
    const { markdown } = await api('/api/note', { path });
    body.innerHTML = renderMarkdown(markdown);
    body.scrollTop = 0; back.scrollTop = 0;
  } catch (err) {
    body.innerHTML = `<p class="notice warn">Could not load ${path}: ${err.message}</p>`;
  }
}

export function closeNote() { back.classList.remove('open'); }

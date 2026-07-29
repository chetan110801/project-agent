// Live modes — play and watch a real game through the same harness the offline runs used.
// This view renders the KEY GATE (from /api/live/status) and the controls for each mode.
// The offline core never depends on any of this: with no key the real buttons are cleanly
// disabled. A no-key MOCK play is always available so the mechanics can be tried anywhere.
import { api } from '../api.js';
import { el } from '../ui.js';
import { learnStrip, openNote } from '../shell.js';
import { startYouPlay, startWatch } from './live_run.js';

export async function render(root) {
  let status;
  try { status = await api('/api/live/status'); }
  catch (err) { status = { arc: false, llm: false, you_play_enabled: false, watch_agent_enabled: false, error: err.message }; }

  root.append(
    el('div.view-head', {}, [
      el('h2', { text: 'Live — play and watch, for real' }),
      el('p', { text: 'Optional. Talks to the real ARC-AGI-3 server through the same harness the offline runs used. Gated so the always-works offline core never depends on it.' }),
    ]),
    learnStrip('live'),
    keyBanner(status),
    el('div.grid2', {}, [youPlayCard(status), watchCard(status)]),
  );
}

function keyBanner(s) {
  const badge = (ok, label) => el('span', { class: 'chip ' + (ok ? 'ok' : 'zero'),
    text: `${label}: ${ok ? 'present' : 'missing'}` });
  return el('div.card', { style: 'margin-bottom:16px' }, [
    el('div', { style: 'display:flex; gap:10px; align-items:center; flex-wrap:wrap' }, [
      el('b', { text: 'Keys detected in .env:' }),
      badge(s.arc, 'ARC_API_KEY'),
      badge(s.llm, 'GEMINI/GOOGLE key'),
    ]),
    el('p.dim', { style: 'font-size:12px; margin:8px 0 0',
      text: 'Only whether a key exists is ever sent to this page — never the key value. Keys stay in the untracked .env.' }),
  ]);
}

function youPlayCard(status) {
  const host = el('div', { style: 'margin-top:14px' });
  const gameInput = el('input', { type: 'text', value: 'ls20', size: 8, id: 'ypGame' });
  const realBtn = el('button.primary', {
    disabled: status.you_play_enabled ? null : 'disabled',
    onclick: () => startYouPlay(host, { mock: false, game: gameInput.value.trim() || 'ls20' }),
  }, ['▶ Real game']);
  const mockBtn = el('button', {
    onclick: () => startYouPlay(host, { mock: true }),
  }, ['▶ No-key demo (mock)']);

  return el('div.card', {}, [
    header('You play', 'ARC key only · no LLM quota'),
    el('p', { style: 'font-size:13.5px; color:var(--dim); margin:8px 0 12px',
      text: 'Drive a real game live: click an action, the real server returns the next frame and score — the exact task the agent faces. No LLM calls, so the 500/day LLM quota is untouched.' }),
    el('div', { style: 'display:flex; gap:10px; align-items:end; flex-wrap:wrap' }, [
      el('label.fld', {}, ['Game', gameInput]),
      realBtn, mockBtn,
    ]),
    status.you_play_enabled ? null : el('p.dim', { style: 'font-size:12px; margin:9px 0 0', html:
      'Real play is disabled until an <code>ARC_API_KEY</code> is in your <code>.env</code> — '
      + 'but the no-key mock works right now.' }),
    status.you_play_enabled ? null : el('div', { style: 'margin-top:8px' },
      [el('button', { onclick: () => openNote(status.howto.arc, 'Get your ARC API key') }, ['📘 How to get an ARC key'])]),
    host,
  ]);
}

function watchCard(status) {
  const host = el('div', { style: 'margin-top:14px' });
  const gameInput = el('input', { type: 'text', value: 'ls20', size: 8, id: 'waGame' });
  const maxSel = el('select', { id: 'waMax' }, [
    el('option', { value: '5' }, ['5 actions']),
    el('option', { value: '8', selected: 'selected' }, ['8 actions']),
    el('option', { value: '12' }, ['12 actions']),
    el('option', { value: '20' }, ['20 actions (max)']),
  ]);
  const startBtn = el('button.primary', {
    disabled: status.watch_agent_enabled ? null : 'disabled',
    onclick: () => startWatch(host, { game: gameInput.value.trim() || 'ls20', max: maxSel.value }),
  }, ['▶ Start watching']);

  return el('div.card', {}, [
    header('Watch the agent play', 'ARC + LLM keys · real 429 risk'),
    el('p', { style: 'font-size:13.5px; color:var(--dim); margin:8px 0 12px',
      text: 'Trigger a real agent run and stream observe → decide → act → score as it happens. Each action is one LLM call against the 500/day free tier — kept short on purpose. A 429 mid-run degrades to an amber "fell back" step; it does not crash.' }),
    el('div', { style: 'display:flex; gap:10px; align-items:end; flex-wrap:wrap' }, [
      el('label.fld', {}, ['Game', gameInput]),
      el('label.fld', {}, ['Action budget', maxSel]),
      startBtn,
    ]),
    status.watch_agent_enabled ? null : el('div.notice.warn', { style: 'margin-top:10px' }, [
      el('div', { html: 'Disabled — needs both an <code>ARC_API_KEY</code> and an LLM key in <code>.env</code>.' }),
      el('div', { style: 'margin-top:9px; display:flex; gap:8px; flex-wrap:wrap' }, [
        el('button', { onclick: () => openNote(status.howto.arc, 'Get your ARC API key') }, ['📘 ARC key']),
        el('button', { onclick: () => openNote(status.howto.llm, 'Get a free LLM API key') }, ['📘 LLM key']),
      ]),
    ]),
    host,
  ]);
}

function header(title, badge) {
  return el('div', { style: 'display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap' }, [
    el('b', { style: 'font-size:16px', text: title }),
    el('span.pill', { text: badge }),
  ]);
}

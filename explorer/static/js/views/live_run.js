// Interactive live drivers. you-play does request/response against the real server (or the
// no-key mock); watch-agent consumes a Server-Sent-Events stream of a real agent run and
// degrades gracefully on a 429 (amber "fell back" step) exactly as the harness does.
import { el } from '../ui.js';
import { drawScreen } from '../grid.js';

// ============================ you play ============================
export async function startYouPlay(host, { mock = false, game = 'ls20' } = {}) {
  host.replaceChildren(el('div.loading', { text: mock ? 'Starting the no-key mock game…' : `Connecting to the real server (${game})…` }));
  let s;
  try {
    s = await post('/api/live/play/start', { mock, game });
  } catch (err) {
    host.replaceChildren(errorBox(mock ? 'Could not start the mock game.' : 'Could not reach the game server.', err));
    return;
  }

  const palette = s.palette;
  const state = { sid: s.session_id, done: s.done, armed: null };

  const canvas = el('canvas', { class: 'screen', width: 64, height: 64 });
  const scoreEl = miniStat('Score'), dEl = miniStat('Δ score'), cEl = miniStat('Cells changed'), stEl = miniStat('State');
  const actionsBox = el('div', { style: 'display:flex; gap:8px; flex-wrap:wrap; margin:12px 0' });
  const hint = el('div.cap', { text: 'Pick a button. A click action (ACTION6) arms the screen — then click a cell.' });
  const logBox = el('div.scroll-y', { style: 'max-height:200px; margin-top:8px' });
  const banner = el('div');

  function draw(frame) { drawScreen(canvas, frame, palette); }
  function setStat(node, v, cls) { node.querySelector('.v').textContent = v; node.querySelector('.v').className = 'v' + (cls ? ' ' + cls : ''); }

  function renderLegal(legal) {
    actionsBox.replaceChildren(...legal.map(a =>
      el('button', {
        disabled: state.done ? 'disabled' : null,
        onclick: () => a.complex ? armClick(a) : sendAction(a.name),
      }, [a.complex ? `${a.name} (click)` : a.name])));
    if (!legal.length) actionsBox.append(el('span.dim', { text: 'no actions available — end the game' }));
  }

  function armClick(a) {
    state.armed = a.name;
    hint.textContent = `${a.name} armed — click a cell on the screen to place it.`;
    canvas.style.cursor = 'crosshair';
  }

  canvas.addEventListener('click', (e) => {
    if (!state.armed || state.done) return;
    const rect = canvas.getBoundingClientRect();
    const w = canvas.width, h = canvas.height;
    const x = Math.max(0, Math.min(w - 1, Math.floor((e.clientX - rect.left) / rect.width * w)));
    const y = Math.max(0, Math.min(h - 1, Math.floor((e.clientY - rect.top) / rect.height * h)));
    const name = state.armed; state.armed = null; canvas.style.cursor = '';
    hint.textContent = `sent ${name} at (x=${x}, y=${y})`;
    sendAction(name, x, y);
  });

  async function sendAction(name, x, y) {
    setBusy(true);
    try {
      const r = await post('/api/live/play/action', { session_id: state.sid, action: name, x, y });
      draw(r.frame);
      setStat(scoreEl, r.score, r.score > 0 ? 'ok' : 'zero');
      setStat(dEl, (r.dscore > 0 ? '+' : '') + r.dscore, r.dscore > 0 ? 'ok' : r.dscore < 0 ? 'zero' : '');
      setStat(cEl, r.changed);
      setStat(stEl, r.state, r.done ? 'ok' : '');
      logRow(logBox, `${r.action} → score ${r.score} (${r.dscore >= 0 ? '+' : ''}${r.dscore}), ${r.changed} cells changed`);
      state.done = r.done;
      renderLegal(r.legal);
      if (r.done) banner.replaceChildren(el('div.notice.warn', { html: '🎉 <b>WIN</b> — you solved it. End the game to record the scorecard.' }));
    } catch (err) {
      logRow(logBox, `⚠ ${err.message}`, true);
    } finally { setBusy(false); }
  }

  function setBusy(b) { [...actionsBox.querySelectorAll('button')].forEach(x => x.disabled = b || state.done); }

  const endBtn = el('button', { onclick: endGame }, ['■ End game']);
  async function endGame() {
    endBtn.disabled = true; endBtn.textContent = 'ending…';
    try {
      const r = await post('/api/live/play/close', { session_id: state.sid });
      banner.replaceChildren(finalCard(r, mock));
    } catch (err) { banner.replaceChildren(errorBox('Could not close the game cleanly.', err)); }
    actionsBox.replaceChildren(el('span.dim', { text: 'game ended' }));
  }

  host.replaceChildren(
    el('div', { style: 'display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:10px' }, [
      el('span.chip', { class: 'chip ' + (mock ? 'warn' : 'ok'), text: mock ? 'MOCK — offline, not the real server' : 'LIVE — real ARC-AGI-3 server' }),
      el('span.dim', { style: 'font-size:12.5px', text: `game ${s.game_id}` }),
      s.scorecard_url ? el('a', { href: s.scorecard_url, target: '_blank', rel: 'noopener', text: 'scorecard ↗' }) : null,
      el('span.spacer', { style: 'flex:1' }), endBtn,
    ]),
    el('div.grid2', {}, [
      el('div', {}, [canvas, hint]),
      el('div', {}, [
        el('div.grid4', { style: 'margin-bottom:10px' }, [scoreEl, dEl, cEl, stEl]),
        actionsBox,
        el('div.section-title', { style: 'margin-top:6px', text: 'Move log' }),
        logBox,
        banner,
      ]),
    ]),
  );
  draw(s.frame);
  setStat(scoreEl, s.score, s.score > 0 ? 'ok' : 'zero'); setStat(dEl, '0'); setStat(cEl, '—'); setStat(stEl, s.state);
  renderLegal(s.legal);
}

// ============================ watch the agent ============================
export function startWatch(host, { game = 'ls20', max = '8' } = {}) {
  host.replaceChildren(el('div.loading', { text: `Starting a real agent run on ${game} (up to ${max} actions)…` }));

  let palette = null, es = null, closed = false;
  const canvas = el('canvas', { class: 'screen', width: 64, height: 64 });
  const actionEl = el('div.action-big', { text: '…' });
  const scoreEl = miniStat('Score'), cEl = miniStat('Cells changed'), iEl = miniStat('Move');
  const whyBox = el('div.why', {}, [el('div.k', { text: "Why — the model's own words" }), el('div.t empty', { id: 'wWhy', text: 'waiting for the first decision…' })]);
  const logBox = el('div.scroll-y', { style: 'max-height:200px; margin-top:8px' });
  const status = el('div.cap', { text: 'connecting…' });
  const banner = el('div');

  const stopBtn = el('button', { onclick: stop }, ['■ Stop']);
  function stop() { closed = true; if (es) es.close(); stopBtn.disabled = true; stopBtn.textContent = 'stopped'; status.textContent = 'stopped by you.'; }

  function setWhy(text, err) {
    const w = whyBox.querySelector('.t') || whyBox.children[1];
    w.textContent = err ? '⚠ ' + text : text;
    w.className = 't' + (text ? '' : ' empty');
    whyBox.classList.toggle('err', !!err);
  }
  function setStat(node, v, cls) { const el2 = node.querySelector('.v'); el2.textContent = v; el2.className = 'v' + (cls ? ' ' + cls : ''); }

  host.replaceChildren(
    el('div', { style: 'display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:10px' }, [
      el('span.chip.ok', { text: 'LIVE — real agent, real server' }),
      el('span', { class: 'chip', id: 'wLink' }),
      el('span.spacer', { style: 'flex:1' }), stopBtn,
    ]),
    el('div.grid2', {}, [
      el('div', {}, [canvas, status]),
      el('div', {}, [
        actionEl,
        el('div.grid3', { style: 'margin:10px 0' }, [scoreEl, cEl, iEl]),
        whyBox, banner,
      ]),
    ]),
    el('div.section-title', { text: 'Decision log' }), logBox,
  );

  try {
    es = new EventSource(`/api/live/watch/stream?game=${encodeURIComponent(game)}&max=${encodeURIComponent(max)}`);
  } catch (err) {
    banner.replaceChildren(errorBox('Could not open the live stream.', err));
    return;
  }

  es.onmessage = (ev) => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.type === 'info') {
      palette = m.palette; status.textContent = `game ${m.game_id} · budget ${m.max_actions} actions`;
      const link = host.querySelector('#wLink');
      if (m.scorecard_url && link) { link.replaceChildren(el('a', { href: m.scorecard_url, target: '_blank', rel: 'noopener', text: 'scorecard ↗' })); }
    } else if (m.type === 'start') {
      palette = m.palette || palette; if (m.frame && palette) drawScreen(canvas, m.frame, palette);
      status.textContent = 'agent is thinking…';
    } else if (m.type === 'step') {
      if (m.frame && palette) drawScreen(canvas, m.frame, palette);
      actionEl.textContent = m.action; actionEl.className = 'action-big';
      setStat(scoreEl, m.score, m.score > 0 ? 'ok' : 'zero');
      setStat(cEl, m.changed); setStat(iEl, m.index);
      setWhy(m.reason || '(no reason)', m.err);
      logRow(logBox, `#${m.index} ${m.action} → score ${m.score}, ${m.changed} cells${m.err ? '  ⚠ fell back (quota)' : ''}`, m.err);
      status.textContent = 'agent is thinking…';
    } else if (m.type === 'end') {
      status.textContent = `finished: ${m.stopped_because} · ${m.actions} actions · ${m.llm_calls} LLM calls, ${m.client_errors} errors`;
      banner.replaceChildren(finalCard({ ok: true, scorecard: m.scorecard, final: m }, false));
      stop();
    } else if (m.type === 'error') {
      banner.replaceChildren(el('div.notice.warn', { html: `<b>Live run error:</b> ${escapeHtml(m.message)}<br>The offline core is unaffected.` }));
      status.textContent = 'stopped on error.';
      stop();
    } else if (m.type === 'done') {
      stop();
    }
  };
  es.onerror = () => {
    if (closed) return;
    status.textContent = 'stream closed.';
    if (!banner.children.length) banner.replaceChildren(el('div.notice.info', { text: 'The stream closed. If nothing streamed, the ARC/LLM key may be invalid or the server is unreachable — the offline core is unaffected.' }));
    stop();
  };
}

// ============================ shared bits ============================
async function post(path, body) {
  const res = await fetch(new URL(path, location.origin), {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `${res.status} ${res.statusText}`);
  return data;
}

function miniStat(k) {
  return el('div.stat', {}, [el('div.k', { text: k }), el('div.v', { text: '—', style: 'font-size:20px' })]);
}
function logRow(box, text, err) {
  box.insertBefore(el('div', { class: err ? '' : 'dim', style: 'font-size:12.5px; padding:3px 0; border-bottom:1px solid var(--line)' + (err ? '; color:var(--warn)' : ''), text }), box.firstChild);
}
function errorBox(title, err) {
  return el('div.notice.warn', { html: `<b>${escapeHtml(title)}</b><br>${escapeHtml((err && err.message) || String(err))}<br><span class="dim">The offline core is unaffected.</span>` });
}
function finalCard(r, mock) {
  const sc = r.scorecard || {};
  const rows = [];
  if (r.final) rows.push(['final score', r.final.final_score], ['stopped', r.final.stopped_because], ['LLM calls', r.final.llm_calls], ['errors (429 etc.)', r.final.client_errors]);
  if (sc && typeof sc === 'object') {
    if (sc.score != null) rows.push(['scorecard score', sc.score]);
    if (sc.total_actions != null) rows.push(['total actions', sc.total_actions]);
    if (sc.total_levels_completed != null) rows.push(['levels completed', sc.total_levels_completed]);
    if (sc.won != null) rows.push(['won', String(sc.won)]);
  }
  return el('div.card', { style: 'margin-top:12px' }, [
    el('b', { text: mock ? 'Mock game ended' : 'Game ended — final scorecard' }),
    el('div', { style: 'margin-top:8px' }, rows.length ? rows.map(([k, v]) =>
      el('div', { style: 'display:flex; justify-content:space-between; border-bottom:1px solid var(--line); padding:4px 0; font-size:13px' },
        [el('span.dim', { text: k }), el('b', { text: String(v) })])) : [el('span.dim', { text: mock ? '(no scorecard for the mock game)' : '(no scorecard returned)' })]),
  ]);
}
function escapeHtml(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

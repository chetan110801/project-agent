// Small DOM helpers shared by every view. No framework — just enough sugar to keep the
// views readable.

// el('div.card#id', {onclick}, [children|strings]) -> HTMLElement
export function el(sel, attrs, kids) {
  const m = sel.match(/^([a-z0-9]+)?(.*)$/i);
  const tag = m[1] || 'div';
  const node = document.createElement(tag);
  const rest = m[2];
  const idMatch = rest.match(/#([\w-]+)/);
  if (idMatch) node.id = idMatch[1];
  const classes = [...rest.matchAll(/\.([\w-]+)/g)].map(x => x[1]);
  if (classes.length) node.className = classes.join(' ');
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (k === 'html') node.innerHTML = v;
    else if (k === 'text') node.textContent = v;
    else if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  if (kids != null) for (const kid of [].concat(kids)) {
    if (kid == null || kid === false) continue;
    node.appendChild(typeof kid === 'string' ? document.createTextNode(kid) : kid);
  }
  return node;
}

export const fmt = {
  pct: (x, d = 1) => (x == null ? '—' : (x * 100).toFixed(d) + '%'),
  num: (x) => (x == null ? '—' : (typeof x === 'number' ? x.toLocaleString() : x)),
  fixed: (x, d = 1) => (x == null ? '—' : (+x).toFixed(d)),
};

export function stat(k, v, opts = {}) {
  const cls = 'v' + (opts.zero ? ' zero' : opts.ok ? ' ok' : '');
  return el('div.stat', {}, [
    el('div.k', { text: k }),
    el('div', { class: cls, text: String(v) }),
    opts.sub ? el('div.sub', { text: opts.sub }) : null,
  ]);
}

export function loading(msg = 'Loading…') { return el('div.loading', { text: msg }); }

export function errorCard(err) {
  return el('div.notice.warn', { html: `<b>Could not load this view.</b><br>${err.message || err}` });
}

// A compact markdown -> HTML renderer, just enough for the study notes (headings, lists,
// tables, code fences, blockquotes, rules, inline bold/italic/code/links). The notes are
// trusted repo files, but we still escape HTML before formatting, on principle.

function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function inline(s) {
  s = esc(s);
  s = s.replace(/`([^`]+)`/g, (_, c) => `<code>${c}</code>`);
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g,
    (_, t, h) => `<a href="${h}" target="_blank" rel="noopener">${t}</a>`);
  return s;
}

function renderTable(rows) {
  const cells = r => r.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
  const head = cells(rows[0]);
  const body = rows.slice(2).map(cells);
  let h = '<table><thead><tr>' + head.map(c => `<th>${inline(c)}</th>`).join('') + '</tr></thead><tbody>';
  for (const r of body) h += '<tr>' + r.map(c => `<td>${inline(c)}</td>`).join('') + '</tr>';
  return h + '</tbody></table>';
}

export function renderMarkdown(md) {
  const lines = md.replace(/\r\n/g, '\n').split('\n');
  const out = [];
  let i = 0;
  while (i < lines.length) {
    let line = lines[i];

    // code fence
    if (/^```/.test(line)) {
      const buf = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
      i++; // closing fence
      out.push(`<pre><code>${esc(buf.join('\n'))}</code></pre>`);
      continue;
    }
    // table (line of pipes followed by a |---| separator)
    if (/^\s*\|.*\|/.test(line) && i + 1 < lines.length && /^\s*\|[-:| ]+\|/.test(lines[i + 1])) {
      const buf = [];
      while (i < lines.length && /^\s*\|.*\|/.test(lines[i])) buf.push(lines[i++].trim());
      out.push(renderTable(buf));
      continue;
    }
    // heading
    let m = line.match(/^(#{1,6})\s+(.*)$/);
    if (m) { out.push(`<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`); i++; continue; }
    // hr
    if (/^\s*([-*_])\1{2,}\s*$/.test(line)) { out.push('<hr>'); i++; continue; }
    // blockquote (group)
    if (/^\s*>\s?/.test(line)) {
      const buf = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ''));
      out.push(`<blockquote>${inline(buf.join(' '))}</blockquote>`);
      continue;
    }
    // list (group; ordered or unordered)
    if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\.\s+/.test(line);
      const buf = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
        buf.push(lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, ''));
      }
      const tag = ordered ? 'ol' : 'ul';
      out.push(`<${tag}>` + buf.map(x => `<li>${inline(x)}</li>`).join('') + `</${tag}>`);
      continue;
    }
    // blank
    if (!line.trim()) { i++; continue; }
    // paragraph (group consecutive plain lines)
    const buf = [line];
    i++;
    while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|```|\s*>|\s*([-*]|\d+\.)\s|\s*\|)/.test(lines[i])
           && !/^\s*([-*_])\1{2,}\s*$/.test(lines[i])) {
      buf.push(lines[i++]);
    }
    out.push(`<p>${inline(buf.join(' '))}</p>`);
  }
  return out.join('\n');
}

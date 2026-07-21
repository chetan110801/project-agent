"""Compile every markdown file in this repo into one browsable index.html.

Same idea as project-asi's index.html: a single offline file — sidebar library,
reader pane, dark/light/sepia themes. Rerun after editing any note:

    py build_site.py
"""

from __future__ import annotations

import datetime
import html
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).parent
OUT = ROOT / "index.html"

# (section label, file path) — sidebar order. New notes are picked up automatically.
def collect_docs() -> list[tuple[str, Path]]:
    docs: list[tuple[str, Path]] = []
    for p in sorted((ROOT / "notes").glob("[0-9]*.md")):
        docs.append(("Study notes", p))
    docs.append(("Study notes", ROOT / "notes" / "DECISIONS.md"))
    docs.append(("Project", ROOT / "CLAUDE.md"))
    for name in ("README.md", "ablation-plan.md"):
        p = ROOT / "trm-reproduction" / name
        if p.exists():
            docs.append(("Deferred: TRM", p))
    return [(s, p) for s, p in docs if p.exists()]


def doc_id(path: Path) -> str:
    return re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")


def doc_title(text: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else fallback


def render(path: Path, ids_by_basename: dict[str, str]) -> str:
    body = markdown.markdown(
        path.read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    # Internal links between md files become in-page hash links.
    def fix_link(m: re.Match) -> str:
        target = m.group(2).split("#")[0]
        base = target.rsplit("/", 1)[-1]
        if base in ids_by_basename:
            return f'{m.group(1)}"#{ids_by_basename[base]}"'
        return m.group(0)

    return re.sub(r'(href=)"([^"#]+\.md[^"]*)"', fix_link, body)


def main() -> None:
    docs = collect_docs()
    ids_by_basename = {p.name: doc_id(p) for _, p in docs}

    nav, sections, last_section = [], [], None
    for section, path in docs:
        text = path.read_text(encoding="utf-8")
        did = doc_id(path)
        title = doc_title(text, path.stem)
        short = re.sub(r"^Study note \d+ — ", "", title)
        if section != last_section:
            nav.append(f'<div class="nav-section">{html.escape(section)}</div>')
            last_section = section
        nav.append(
            f'<a class="nav-link" href="#{did}" data-doc="{did}">{html.escape(short)}</a>'
        )
        sections.append(
            f'<article id="{did}" data-title="{html.escape(short)}">'
            f"{render(path, ids_by_basename)}</article>"
        )

    built = datetime.date.today().isoformat()
    page = TEMPLATE.replace("{{NAV}}", "\n".join(nav))
    page = page.replace("{{SECTIONS}}", "\n".join(sections))
    page = page.replace("{{BUILT}}", built)
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes, {len(docs)} documents)")


TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark light">
<title>project-agent — notes</title>
<style>
:root{--content-width:760px;
  --ui-font:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --read-font:Georgia,"Iowan Old Style","Palatino Linotype",Palatino,"Times New Roman",serif}
html[data-theme="light"]{--bg:#fbfbf9;--bg-2:#f2f1ec;--panel:#ffffff;--text:#1d1d1f;
  --muted:#6b6b6f;--border:#e4e2db;--accent:#8a5a2b;--accent-soft:#f0e6da;--quote:#f6f3ec}
html[data-theme="dark"]{--bg:#1b1c1e;--bg-2:#232427;--panel:#202123;--text:#e3e2df;
  --muted:#9a9a9e;--border:#34353a;--accent:#d8a566;--accent-soft:#2c2a26;--quote:#26272a}
html[data-theme="sepia"]{--bg:#f3e7cf;--bg-2:#ece0c4;--panel:#f7eed9;--text:#46392a;
  --muted:#8c7a59;--border:#dccaa3;--accent:#9c5a25;--accent-soft:#ecdcbd;--quote:#efe4ca}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--ui-font);
  display:flex;min-height:100vh}
.sidebar{width:290px;flex-shrink:0;background:var(--bg-2);border-right:1px solid var(--border);
  padding:1rem .9rem 2rem;position:sticky;top:0;height:100vh;overflow-y:auto}
.brand{font-weight:700;font-size:1.02rem;margin:0 .2rem .2rem}
.tagline{font-size:.78rem;color:var(--muted);margin:0 .2rem 1rem;line-height:1.45}
.nav-section{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);
  margin:1.1rem .2rem .35rem}
.nav-link{display:block;padding:.42rem .55rem;border-radius:8px;color:var(--text);
  text-decoration:none;font-size:.88rem;line-height:1.35}
.nav-link:hover{background:var(--accent-soft)}
.nav-link.active{background:var(--accent);color:#fff}
.themes{display:flex;gap:.35rem;margin:1.4rem .2rem 0}
.themes button{border:1px solid var(--border);background:var(--panel);color:var(--text);
  border-radius:8px;padding:.35rem .6rem;font-size:.78rem;cursor:pointer}
.themes button.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.built{font-size:.72rem;color:var(--muted);margin:1rem .2rem 0}
main{flex:1;min-width:0;padding:2.2rem 1.4rem 5rem}
article{display:none;max-width:var(--content-width);margin:0 auto;
  font-family:var(--read-font);font-size:1.06rem;line-height:1.66}
article.active{display:block}
article h1,article h2,article h3{font-family:var(--ui-font);line-height:1.25}
article h1{font-size:1.65rem;margin:.2rem 0 1rem}
article h2{font-size:1.25rem;margin-top:2.2rem;border-bottom:1px solid var(--border);
  padding-bottom:.3rem}
article h3{font-size:1.05rem;margin-top:1.6rem}
article a{color:var(--accent)}
article hr{border:0;border-top:1px solid var(--border);margin:2rem 0}
article blockquote{margin:1rem 0;padding:.6rem 1rem;background:var(--quote);
  border-left:3px solid var(--accent);border-radius:0 8px 8px 0}
article code{font-family:ui-monospace,Consolas,monospace;font-size:.85em;
  background:var(--accent-soft);padding:.1em .35em;border-radius:5px}
article pre{background:var(--panel);border:1px solid var(--border);border-radius:10px;
  padding:.9rem 1rem;overflow-x:auto}
article pre code{background:none;padding:0;font-size:.82rem;line-height:1.55}
.tablewrap,article table{max-width:100%}
article table{border-collapse:collapse;font-family:var(--ui-font);font-size:.88rem;
  display:block;overflow-x:auto}
article th,article td{border:1px solid var(--border);padding:.45rem .6rem;text-align:left;
  vertical-align:top}
article th{background:var(--bg-2)}
.menu-btn{display:none}
@media (max-width:820px){
  body{flex-direction:column}
  .sidebar{position:static;width:100%;height:auto;border-right:0;
    border-bottom:1px solid var(--border)}
  main{padding:1.4rem 1rem 4rem}
}
</style>
</head>
<body>
<nav class="sidebar">
  <p class="brand">project-agent</p>
  <p class="tagline">An LLM agent for ARC-AGI-3, judged by its engineering harness.
     Plain-language notes, decisions, and rules — all in one page.</p>
  {{NAV}}
  <div class="themes" id="themes">
    <button data-theme="dark">Dark</button>
    <button data-theme="light">Light</button>
    <button data-theme="sepia">Sepia</button>
  </div>
  <p class="built">Built {{BUILT}} · rebuild: <code>py build_site.py</code></p>
</nav>
<main>
{{SECTIONS}}
</main>
<script>
(function(){
  var links=[].slice.call(document.querySelectorAll('.nav-link'));
  var docs=[].slice.call(document.querySelectorAll('article'));
  function show(id){
    var target=document.getElementById(id)||docs[0];
    docs.forEach(function(d){d.classList.toggle('active',d===target)});
    links.forEach(function(l){l.classList.toggle('active',l.dataset.doc===target.id)});
    document.title='project-agent — '+target.dataset.title;
    window.scrollTo(0,0);
  }
  window.addEventListener('hashchange',function(){show(location.hash.slice(1))});
  show(location.hash.slice(1));

  var themeBtns=[].slice.call(document.querySelectorAll('#themes button'));
  function setTheme(t){
    document.documentElement.dataset.theme=t;
    themeBtns.forEach(function(b){b.classList.toggle('active',b.dataset.theme===t)});
    try{localStorage.setItem('pa-theme',t)}catch(e){}
  }
  themeBtns.forEach(function(b){b.onclick=function(){setTheme(b.dataset.theme)}});
  var saved='dark';
  try{saved=localStorage.getItem('pa-theme')||'dark'}catch(e){}
  setTheme(saved);
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()

"""Compile every markdown note in this repo into one browsable index.html.

The reader shell is ported from the `hy` project's build_site.py — a mobile-first
reading app in a single offline file: home cards -> section lists -> articles,
an overlay drawer with every setting (theme / font / size / spacing / width),
position memory with "Continue reading", edge-tap + arrow-key paging, breadcrumbs
and prev/next pagers. Document collection stays ours (notes, decisions, CLAUDE.md,
deferred TRM docs). Rerun after editing any note:

    py build_site.py
"""

from __future__ import annotations

import datetime
import html
import re
import sys
from pathlib import Path

try:
    import markdown as md_lib
except ImportError:
    sys.exit("Missing dependency. Install it with:  py -m pip install markdown")

ROOT = Path(__file__).parent
OUT = ROOT / "index.html"
BRAND = "project-agent"
TAGLINE = ("An LLM agent for ARC-AGI-3, judged by its engineering harness. "
           "Plain-language notes, decisions, and rules — all in one page.")

NUM_RE = re.compile(r"^(\d+)")


# --------------------------------------------------------------------------- #
# Document collection (ours)
# --------------------------------------------------------------------------- #
def collect_docs() -> list[tuple[str, Path]]:
    """(section label, file path) in sidebar order. New notes are picked up automatically.

    Order is the reading order: the zero-knowledge course first, then the things Chetan
    has to do himself, then the project record, then rules, then the deferred TRM work.
    """
    docs: list[tuple[str, Path]] = []
    for p in sorted((ROOT / "notes" / "study").glob("[0-9]*.md")):
        docs.append(("Learn from zero", p))
    for p in sorted((ROOT / "notes" / "howto").glob("[0-9]*.md")):
        docs.append(("Do this — step by step", p))
    for p in sorted((ROOT / "notes").glob("[0-9]*.md")):
        docs.append(("Project record", p))
    docs.append(("Project record", ROOT / "notes" / "DECISIONS.md"))
    docs.append(("Project", ROOT / "CLAUDE.md"))
    for name in ("README.md", "ablation-plan.md"):
        p = ROOT / "trm-reproduction" / name
        if p.exists():
            docs.append(("Deferred: TRM", p))
    return [(s, p) for s, p in docs if p.exists()]


def doc_id(path: Path) -> str:
    return re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")


def read_text(path: Path) -> str:
    """Read as text, tolerating a UTF-8 BOM or Windows-1252 source encoding."""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def doc_title(text: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else fallback


def short_title(full: str) -> str:
    """'Study 03 — Tokens and context windows' -> 'Tokens and context windows'."""
    t = re.sub(r"^(Study note|Study|How-to)\s*\d+\s*—\s*", "", full)
    if t == full and "—" in full:
        t = full.split("—", 1)[1].strip()
    return t.strip() or full


CALLOUT_OPEN_RE = re.compile(r"^:::\s*([a-zA-Z][\w-]*)\s*(.*?)\s*$")


def expand_callouts(text: str) -> str:
    """Turn `::: key` … `:::` fences into the styled boxes the reader shell renders.

    `key` / `example` / `warn` / `note` become coloured <div class="callout …"> blocks —
    they break up a long note visually so a beginner can see what to slow down on.
    Inner markdown still renders, via the md_in_html extension.
    """
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        m = CALLOUT_OPEN_RE.match(lines[i])
        if m:
            cls = m.group(1).lower()
            j = i + 1
            body: list[str] = []
            while j < len(lines) and lines[j].strip() != ":::":
                body.append(lines[j])
                j += 1
            out.append(f'<div class="callout {cls}" markdown="1">')
            out.append("")
            out.extend(body)
            out.append("")
            out.append("</div>")
            i = j + 1
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


def build_metas() -> list[dict]:
    metas = []
    for section, path in collect_docs():
        text = read_text(path)
        full = doc_title(text, path.stem)
        m = NUM_RE.match(path.stem)
        metas.append({
            "section": section,
            "path": path,
            "text": text,
            "tabid": doc_id(path),
            "badge": m.group(1) if m else "",
            "full_title": full,
            "title": short_title(full),
        })
    return metas


# --------------------------------------------------------------------------- #
# Markdown rendering (plain; internal .md links become in-page links)
# --------------------------------------------------------------------------- #
def render_markdown(md, text: str, ids_by_basename: dict[str, str]) -> str:
    body = md.reset().convert(expand_callouts(text))

    def fix_link(m: re.Match) -> str:
        target = m.group(2).split("#")[0]
        base = target.rsplit("/", 1)[-1]
        if base in ids_by_basename:
            did = ids_by_basename[base]
            return f'{m.group(1)}"#{did}" class="wikilink" data-target="{did}"'
        return m.group(0)

    return re.sub(r'(href=)"([^"#]+\.md[^"]*)"', fix_link, body)


# --------------------------------------------------------------------------- #
# Page assembly (ported from hy/build_site.py)
# --------------------------------------------------------------------------- #
def sidebar_group(label, items):
    """A collapsible <details> group with its tab links. items: list of (tabid, badge, title, full)."""
    links = []
    for tabid, badge, title, full in items:
        badge_html = f'<span class="num">{html.escape(badge)}</span>' if badge else ""
        links.append(
            f'<a class="tab" data-target="{html.escape(tabid)}" href="#{html.escape(tabid)}" '
            f'title="{html.escape(full)}">{badge_html}<span class="tab-title">{html.escape(title)}</span></a>'
        )
    return (f'<details class="group" open><summary>{html.escape(label)}'
            f'<span class="group-count">{len(items)}</span></summary>\n'
            f'<div class="group-body">{"".join(links)}</div></details>')


def _pager_link(meta, cls, before, after):
    if not meta:
        return '<span class="pager-spacer"></span>'
    return (f'<a class="{cls}" data-target="{html.escape(meta["tabid"])}" '
            f'href="#{html.escape(meta["tabid"])}" title="{html.escape(meta["full_title"])}">'
            f'{before}<span>{html.escape(meta["title"])}</span>{after}</a>')


def crumb_nav(crumb):
    """Home › Section breadcrumb at the top of every article. crumb = (secid, label)."""
    if not crumb:
        return ""
    secid, label = crumb
    return ('<nav class="crumb">'
            '<a data-target="home" href="#home">⌂ Home</a><span class="crumb-sep">›</span>'
            f'<a data-target="{html.escape(secid)}" href="#{html.escape(secid)}">{html.escape(label)}</a>'
            '</nav>')


def article(meta, body_html, prev=None, nxt=None, crumb=None):
    pager = ('<nav class="pager">'
             + _pager_link(prev, "pager-prev", "← ", "")
             + _pager_link(nxt, "pager-next", "", " →")
             + '</nav>')
    return (f'<article class="doc" id="doc-{html.escape(meta["tabid"])}" '
            f'data-tabid="{html.escape(meta["tabid"])}">{crumb_nav(crumb)}{body_html}{pager}</article>')


def preview_title(title: str) -> str:
    """Short form for menu previews: drop '[bracket glosses]', a leading file number, and
    keep the headline half (before the colon)."""
    t = re.sub(r"\s*\[[^\]]*\]", "", title)
    t = t.split(":", 1)[0]
    t = re.sub(r"^\d+\s+", "", t.strip())
    return re.sub(r"\s{2,}", " ", t).strip()


def _range_label(items):
    """'01–08' from a group's first and last file numbers ('' when unnumbered)."""
    badges = [b for _, b, _, _ in items if b]
    if not badges:
        return ""
    return badges[0] if badges[0] == badges[-1] else f"{badges[0]}–{badges[-1]}"


def home_doc(brand, groups, range_kickers=True):
    """The landing view: one card per section (tab), each opening that section's file list."""
    cards = []
    for i, (label, items) in enumerate(groups):
        count = f'{len(items)} file{"s" if len(items) != 1 else ""}'
        rng = _range_label(items) if range_kickers else ""
        kicker = f"{rng} · {count}" if rng else count
        preview = " · ".join(preview_title(t) for _, _, t, _ in items[:4])
        cards.append(
            f'<a class="card" data-target="sec-{i}" href="#sec-{i}">'
            f'<span class="card-k">{html.escape(kicker)}</span>'
            f'<span class="card-t">{html.escape(label)}</span>'
            f'<span class="card-p">{html.escape(preview)}</span></a>')
    return ('<article class="doc nav-view" id="doc-home" data-tabid="home">'
            '<header class="nav-head">'
            f'<h1 class="home-h">{html.escape(brand)}</h1>'
            f'<p class="home-sub">{html.escape(TAGLINE)}</p>'
            '</header>'
            '<a class="resume" id="homeResume" href="#" hidden>'
            '<span class="resume-k">Continue reading</span>'
            '<span class="resume-t" id="homeResumeTitle"></span>'
            '<span class="resume-go">→</span></a>'
            f'<div class="cards">{"".join(cards)}</div></article>')


def section_doc(i, label, items):
    """One section's file list, reached from the home cards."""
    links = []
    for tabid, badge, title, full in items:
        badge_html = f'<span class="num">{html.escape(badge)}</span>' if badge else '<span class="num"></span>'
        links.append(
            f'<a data-target="{html.escape(tabid)}" href="#{html.escape(tabid)}" '
            f'title="{html.escape(full)}">{badge_html}'
            f'<span class="st">{html.escape(title)}</span></a>')
    count = f'{len(items)} file{"s" if len(items) != 1 else ""}'
    rng = _range_label(items)
    return (f'<article class="doc nav-view" id="doc-sec-{i}" data-tabid="sec-{i}">'
            '<nav class="crumb"><a data-target="home" href="#home">⌂ Home</a>'
            f'<span class="crumb-sep">›</span><span class="crumb-here">{html.escape(label)}</span></nav>'
            '<header class="nav-head">'
            f'<h1 class="home-h">{html.escape(label)}</h1>'
            f'<p class="home-sub">{html.escape(f"{rng} · {count}" if rng else count)}</p>'
            '</header>'
            f'<div class="seclist">{"".join(links)}</div></article>')


def render_page(page_title, sidebar_brand, groups, sections_html, initial_tabid, range_kickers=True):
    sidebar = "\n".join(sidebar_group(lbl, items) for lbl, items in groups)
    nav_docs = "\n".join([home_doc(sidebar_brand, groups, range_kickers)]
                         + [section_doc(i, lbl, items) for i, (lbl, items) in enumerate(groups)])
    return (PAGE_TEMPLATE
            .replace("__PAGE_TITLE__", html.escape(page_title))
            .replace("__PAGEKEY__", html.escape(page_title))
            .replace("__BRAND__", html.escape(sidebar_brand))
            .replace("__BUILT__", datetime.date.today().isoformat())
            .replace("__SIDEBAR__", sidebar)
            .replace("__SECTIONS__", nav_docs + "\n" + sections_html)
            .replace("__INITIAL__", html.escape(initial_tabid)))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    metas = build_metas()
    if not metas:
        sys.exit(f"No documents found under {ROOT}")
    ids_by_basename = {m["path"].name: m["tabid"] for m in metas}
    md = md_lib.Markdown(extensions=["extra", "sane_lists", "md_in_html"])

    # groups in first-seen section order
    groups, order = [], []
    by_section: dict[str, list] = {}
    for m in metas:
        if m["section"] not in by_section:
            by_section[m["section"]] = []
            order.append(m["section"])
        by_section[m["section"]].append((m["tabid"], m["badge"], m["title"], m["full_title"]))
    groups = [(s, by_section[s]) for s in order]
    crumb_of = {tabid: (f"sec-{i}", label)
                for i, (label, items) in enumerate(groups) for tabid, _, _, _ in items}

    sections = []
    for idx, meta in enumerate(metas):
        body = render_markdown(md, meta["text"], ids_by_basename)
        prev = metas[idx - 1] if idx > 0 else None
        nxt = metas[idx + 1] if idx < len(metas) - 1 else None
        sections.append(article(meta, body, prev, nxt, crumb_of.get(meta["tabid"])))

    page = render_page(f"{BRAND} — notes", BRAND, groups, "\n".join(sections),
                       metas[0]["tabid"])
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes, {len(metas)} documents)")


PAGE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark light">
<meta name="theme-color" id="tcMeta" content="#1b1c1e">
<title>__PAGE_TITLE__</title>
<style>
:root{
  --content-font: 18px;
  --content-width: 760px;
  --content-leading: 1.66;
  --ui-font: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --read-font: Georgia,"Iowan Old Style","Palatino Linotype",Palatino,"Times New Roman",serif;
}
html[data-theme="light"]{
  --bg:#fbfbf9; --bg-2:#f2f1ec; --panel:#ffffff; --text:#1d1d1f; --muted:#6b6b6f;
  --border:#e4e2db; --accent:#8a5a2b; --accent-soft:#f0e6da; --quote:#f6f3ec; --shadow:rgba(0,0,0,.08);
}
html[data-theme="dark"]{
  --bg:#1b1c1e; --bg-2:#232427; --panel:#202123; --text:#e3e2df; --muted:#9a9a9e;
  --border:#34353a; --accent:#d8a566; --accent-soft:#2c2a26; --quote:#26272a; --shadow:rgba(0,0,0,.4);
}
html[data-theme="sepia"]{   /* warm "paper" theme for easy night / long reading */
  --bg:#f3e7cf; --bg-2:#ece0c4; --panel:#f7eed9; --text:#46392a; --muted:#8c7a59;
  --border:#dccaa3; --accent:#9c5a25; --accent-soft:#ecdcbd; --quote:#efe4ca; --shadow:rgba(90,70,30,.14);
}
*{box-sizing:border-box}
[hidden]{display:none!important}   /* author display:flex must never beat the hidden attribute */
html{-webkit-text-size-adjust:100%;text-size-adjust:100%;-webkit-tap-highlight-color:transparent}
html,body{margin:0;height:100%}
/* App height: iOS Safari's 100vh INCLUDES the space its address bar / toolbar sit over, so a
   100vh shell is taller than what you can see and the text is clipped top and bottom. Ladder:
   100vh -> 100dvh where supported -> an exact pixel height measured by JS (works everywhere). */
:root{--app-h:100vh}
@supports (height:100dvh){:root{--app-h:100dvh}}
body{background:var(--bg);color:var(--text);font-family:var(--ui-font);
  display:flex;flex-direction:column;height:var(--app-h);overflow:hidden}

/* menu + home live in ONE fixed flex row, so the browser lays them out side by side and
   they can never overlap — whatever the safe-area inset, font size or device is. (They
   used to be two independently positioned buttons whose gap was a hardcoded 46px.) */
.navbtns{position:fixed;top:env(safe-area-inset-top);left:env(safe-area-inset-left);
  z-index:50;display:flex;align-items:center;gap:.25rem}
.hamburger,.homebtn{flex:0 0 auto;width:46px;height:46px;
  border:0;background:transparent;color:var(--muted);font-size:1.2rem;line-height:1;cursor:pointer;
  display:flex;align-items:center;justify-content:center;opacity:0;
  transition:opacity .25s;-webkit-tap-highlight-color:transparent;touch-action:manipulation;
  text-shadow:0 0 5px var(--bg),0 0 5px var(--bg),0 0 5px var(--bg)}
.homebtn{font-size:1.15rem}
.hamburger:hover,.hamburger:focus-visible,
.homebtn:hover,.homebtn:focus-visible{opacity:.85;outline:none}
.hamburger.hint,.homebtn.hint{opacity:.55}                   /* brief "I'm here" hint on load */
.homebtn[hidden]{display:none}
body:not(.sidebar-collapsed) .hamburger,
body:not(.sidebar-collapsed) .homebtn{opacity:0;pointer-events:none} /* hidden while drawer open */

.btn{-webkit-appearance:none;appearance:none;border:1px solid var(--border);background:var(--bg-2);color:var(--text);
  border-radius:8px;padding:.4rem .6rem;font-size:.85rem;cursor:pointer;line-height:1;touch-action:manipulation;
  display:inline-flex;align-items:center;justify-content:center;gap:.3rem;transition:background .15s,border-color .15s}
.btn:hover{border-color:var(--accent);background:var(--accent-soft)}
.btn.active{background:var(--accent);color:#fff;border-color:var(--accent)}

/* layout — the reading column is always full width; the menu is an overlay drawer (same on
   every device), so opening / closing it never reflows the text you are reading */
.shell{display:flex;flex:1;min-height:0;position:relative}
.scrim{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:60;opacity:0;visibility:hidden;
  transition:opacity .25s,visibility .25s}
body:not(.sidebar-collapsed) .scrim{opacity:1;visibility:visible}
.sidebar{position:fixed;top:0;left:0;bottom:0;z-index:70;width:min(340px,86vw);
  background:var(--bg-2);border-right:1px solid var(--border);box-shadow:4px 0 28px var(--shadow);
  overflow-y:auto;-webkit-overflow-scrolling:touch;padding:.4rem .65rem 2rem;
  transform:translateX(-100%);transition:transform .25s ease}
body:not(.sidebar-collapsed) .sidebar{transform:none}
.sidebar-head{display:flex;align-items:center;gap:.5rem;padding:.35rem .15rem .5rem;
  position:sticky;top:0;background:var(--bg-2);z-index:1}
.sidebar-head .brand{font-weight:700;font-size:1rem;flex:1;min-width:0;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.closeSidebar{-webkit-appearance:none;appearance:none;border:0;background:transparent;color:var(--muted);
  font-size:1.5rem;line-height:1;cursor:pointer;padding:.05rem .4rem;border-radius:8px;touch-action:manipulation}
.closeSidebar:hover{color:var(--text);background:var(--accent-soft)}

/* reading-controls panel — every setting lives here, in the drawer */
.panel{display:flex;flex-direction:column;gap:.45rem;padding:.55rem;margin:.1rem 0 .7rem;
  border:1px solid var(--border);border-radius:11px;background:var(--panel)}
.panel-row{display:flex;align-items:center;gap:.5rem}
.panel-lbl{font-size:.82rem;color:var(--muted);flex:1;min-width:0}
.panel-row .btn{flex:0 0 auto}
.panel-row .wide{flex:1}
/* segmented controls (theme, body font) */
.seg{display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden;background:var(--bg-2)}
.seg button{-webkit-appearance:none;appearance:none;border:0;background:transparent;color:var(--text);
  font-size:.8rem;padding:.4rem .55rem;cursor:pointer;line-height:1;min-height:34px;touch-action:manipulation}
.seg button + button{border-left:1px solid var(--border)}
.seg button.active{background:var(--accent);color:#fff}

/* sliders (text size, line spacing, width) */
.slider-row{display:flex;flex-direction:column;gap:.2rem;padding:.05rem 0}
.slider-row label{display:flex;justify-content:space-between;align-items:baseline;
  font-size:.82rem;color:var(--muted)}
.slider-row .val{color:var(--text);font-variant-numeric:tabular-nums;font-size:.8rem}
input[type=range]{-webkit-appearance:none;appearance:none;width:100%;height:28px;background:transparent;
  cursor:pointer;touch-action:manipulation}
input[type=range]:focus{outline:none}
input[type=range]::-webkit-slider-runnable-track{height:6px;border-radius:6px;background:var(--border)}
input[type=range]::-moz-range-track{height:6px;border-radius:6px;background:var(--border)}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:20px;height:20px;
  border-radius:50%;background:var(--accent);border:2px solid var(--panel);margin-top:-7px;
  box-shadow:0 1px 3px var(--shadow)}
input[type=range]::-moz-range-thumb{width:20px;height:20px;border-radius:50%;background:var(--accent);
  border:2px solid var(--panel);box-shadow:0 1px 3px var(--shadow)}

/* brief visual feedback when an edge-tap turns the page */
.edge-flash{position:fixed;top:0;bottom:0;width:36px;z-index:55;pointer-events:none;opacity:0;
  transition:opacity .12s ease}
.edge-flash.show{opacity:.85}
.edge-flash.left{left:0;background:linear-gradient(to right,var(--accent-soft),transparent)}
.edge-flash.right{right:0;background:linear-gradient(to left,var(--accent-soft),transparent)}
.filter{width:100%;padding:.5rem .6rem;margin:.1rem 0 .6rem;border:1px solid var(--border);
  border-radius:8px;background:var(--panel);color:var(--text);font-size:16px;-webkit-appearance:none}
.built{font-size:.72rem;color:var(--muted);margin:1.2rem .2rem 0;font-variant-numeric:tabular-nums}
.group{margin-bottom:.25rem;border-radius:8px}
.group>summary{cursor:pointer;list-style:none;padding:.4rem .55rem;font-weight:600;font-size:.82rem;
  color:var(--muted);text-transform:uppercase;letter-spacing:.4px;border-radius:6px;
  display:flex;align-items:center;gap:.4rem}
.group>summary::-webkit-details-marker{display:none}
.group>summary:before{content:"▸";font-size:.7rem;transition:transform .15s}
.group[open]>summary:before{transform:rotate(90deg)}
.group>summary:hover{background:var(--accent-soft)}
.group-count{margin-left:auto;font-size:.7rem;background:var(--border);color:var(--muted);
  border-radius:10px;padding:.05rem .4rem}
.group-body{display:flex;flex-direction:column;gap:1px;padding:.1rem 0 .35rem}
.tab{display:flex;align-items:baseline;gap:.5rem;padding:.4rem .55rem;border-radius:7px;
  text-decoration:none;color:var(--text);font-size:.9rem;line-height:1.3}
.tab:hover{background:var(--accent-soft)}
.tab.active{background:var(--accent);color:#fff}
.tab.active .num{color:#fff;opacity:.85}
.tab .num{font-size:.72rem;color:var(--muted);min-width:1.6em;font-variant-numeric:tabular-nums;font-weight:600}
.tab-title{flex:1}

/* main / reading column */
.main{flex:1;min-width:0;overflow-y:auto;-webkit-overflow-scrolling:touch;scroll-behavior:smooth;
  overscroll-behavior:contain}
/* top padding clears the fixed hamburger / home / back row (46px) at every width */
.content{max-width:var(--content-width);margin:0 auto;
  padding:calc(3.4rem + env(safe-area-inset-top)) 1.6rem calc(6rem + env(safe-area-inset-bottom));
  font-family:var(--read-font);font-size:var(--content-font);line-height:var(--content-leading);color:var(--text);
  overflow-wrap:break-word}
body.full-width .content{max-width:none}     /* "Full width": fill the screen horizontally */
.doc{display:none}
.doc.active{display:block;animation:fade .2s ease}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}

/* typography inside the body */
.content h1{font-size:2em;line-height:1.15;margin:.1em 0 .2em;font-family:var(--ui-font);letter-spacing:-.015em}
.content h1 + p{font-size:1.16em;line-height:1.5;color:var(--muted);margin:.15em 0 1.5em}  /* the deck line */
.content h1 + p em{color:var(--muted);font-style:italic}
.content h2{font-size:1.42em;line-height:1.22;margin:2.5em 0 .6em;font-family:var(--ui-font);
  font-weight:700;letter-spacing:-.01em}
.content h2::before{content:"";display:block;width:46px;height:3px;border-radius:2px;
  background:var(--accent);margin:0 0 .75em}
.content h3{font-size:1.16em;margin:1.7em 0 .45em;font-family:var(--ui-font);font-weight:700;
  color:var(--accent);letter-spacing:-.005em}
.content p{margin:.75em 0}
.content a{color:var(--accent);text-decoration:none;border-bottom:1px solid var(--accent-soft)}
.content a:hover{border-bottom-color:var(--accent)}
.content blockquote{margin:1.5em 0;padding:.1em 0 .1em 1.25em;background:transparent;
  border-left:3px solid var(--accent);border-radius:0;font-size:1.14em;line-height:1.5;
  font-style:italic;color:var(--text)}
.content blockquote p{margin:.4em 0}
.content ul,.content ol{padding-left:1.4em;margin:.7em 0}
.content li{margin:.4em 0}
.content li>ul,.content li>ol{margin:.35em 0}
.content hr{border:0;border-top:1px solid var(--border);margin:1.6em 0}

/* inline parenthetical glosses — muted so the main sentence leads */
.content .gloss{color:var(--muted)}
.content blockquote .gloss,.content h1 + p .gloss{color:inherit;opacity:.7}

/* dynamic components: lead paragraph, key-line, callout boxes */
.content .lead{font-size:1.14em;line-height:1.55;color:var(--text);margin:.2em 0 1em}
.content .keyline{font-size:1.16em;font-weight:600;line-height:1.5;color:var(--text);
  border-left:3px solid var(--accent);padding:.05em 0 .05em .9em;margin:1.2em 0}
.content .callout{margin:1.3em 0;padding:.85em 1.05em .95em;border-radius:11px;
  border:1px solid var(--border);border-left-width:4px;background:var(--bg-2)}
.content .callout>:first-child{margin-top:0}
.content .callout>:last-child{margin-bottom:0}
.content .callout::before{display:block;font-family:var(--ui-font);font-size:.68rem;
  letter-spacing:.7px;text-transform:uppercase;font-weight:700;margin-bottom:.45em;opacity:.95}
.content .callout.key{border-left-color:var(--accent);background:var(--accent-soft)}
.content .callout.key::before{content:"Key idea";color:var(--accent)}
.content .callout.example{border-left-color:#5a86c4}
.content .callout.example::before{content:"Example";color:#5a86c4}
.content .callout.warn{border-left-color:#c4715a}
.content .callout.warn::before{content:"Careful";color:#c4715a}
.content .callout.note{border-left-color:var(--muted)}
.content .callout.note::before{content:"Aside";color:var(--muted)}

/* collapsible "words to use" drawer at the end of a file */
.content details.vocab{margin:1.8em 0 .5em;border:1px solid var(--border);border-radius:11px;
  background:var(--bg-2);overflow:hidden}
.content details.vocab>summary{cursor:pointer;list-style:none;font-family:var(--ui-font);
  font-weight:700;font-size:.95rem;color:var(--accent);padding:.8em 1em}
.content details.vocab>summary::-webkit-details-marker{display:none}
.content details.vocab>summary::before{content:"▸  ";font-size:.85em;color:var(--muted)}
.content details.vocab[open]>summary::before{content:"▾  "}
.content details.vocab[open]>summary{border-bottom:1px solid var(--border)}
.content details.vocab ul{padding:.6em 1.2em .8em 1.7em;margin:0}
.content details.vocab li{margin:.45em 0}
.content code{background:var(--bg-2);padding:.1em .35em;border-radius:5px;font-size:.9em}
.content strong{font-weight:700}
.content img{max-width:100%;height:auto}
.content table{display:block;max-width:100%;overflow-x:auto;border-collapse:collapse;font-size:.92em}
.content th,.content td{border:1px solid var(--border);padding:.35em .6em;text-align:left;vertical-align:top}
.content th{background:var(--bg-2)}
.wikilink{color:var(--accent);text-decoration:none;border-bottom:1px solid var(--accent-soft);cursor:pointer}
.wikilink:hover{border-bottom-color:var(--accent)}
.wikilink.missing{color:var(--muted);border-bottom:1px dotted var(--muted);cursor:help}

/* ---- home / section views + the way back out of a file ---- */
/* the way back — present but invisible while reading, exactly like the hamburger */
.backbtn{position:fixed;top:env(safe-area-inset-top);right:env(safe-area-inset-right);
  z-index:50;width:46px;height:46px;border:0;background:transparent;color:var(--muted);
  font-size:1.2rem;line-height:1;cursor:pointer;display:flex;align-items:center;
  justify-content:center;opacity:0;transition:opacity .25s;
  -webkit-tap-highlight-color:transparent;touch-action:manipulation;
  text-shadow:0 0 5px var(--bg),0 0 5px var(--bg),0 0 5px var(--bg)}
.backbtn:hover,.backbtn:focus-visible{opacity:.85;outline:none}
.backbtn.hint{opacity:.55}                                   /* brief "I'm here" hint on load */
.backbtn[hidden]{display:none}
body:not(.sidebar-collapsed) .backbtn{opacity:0;pointer-events:none}

/* the menu views are UI, not prose: own font, own (wider) measure */
.doc.nav-view{font-family:var(--ui-font)}
body.on-nav:not(.full-width) .content{max-width:min(1120px,100%)}
.nav-head{margin:0 0 1.6rem}
.content .home-h{font-size:2.1rem;line-height:1.12;margin:0 0 .3rem;font-family:var(--ui-font);
  font-weight:800;letter-spacing:-.02em}
.content .home-sub{color:var(--muted);font-size:.92rem;line-height:1.5;margin:0;
  font-variant-numeric:tabular-nums}

.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(258px,1fr));gap:.85rem}
.content a.card{display:flex;flex-direction:column;gap:.3rem;min-width:0;
  border:1px solid var(--border);border-radius:14px;background:var(--bg-2);
  padding:1rem 1.05rem 1.05rem;text-decoration:none;color:var(--text);
  transition:border-color .15s,background .15s,transform .12s,box-shadow .15s}
.content a.card:hover{border-color:var(--accent);background:var(--accent-soft);
  transform:translateY(-2px);box-shadow:0 8px 20px var(--shadow)}
.card-k{font-size:.67rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;
  color:var(--accent);font-variant-numeric:tabular-nums}
.card-t{font-weight:700;font-size:1.02rem;line-height:1.3;min-height:2.6em;  /* 2 lines = even cards */
  overflow-wrap:anywhere;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card-p{color:var(--muted);font-size:.82rem;line-height:1.5;margin-top:auto;padding-top:.45rem;
  overflow-wrap:anywhere;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}

.content a.resume{display:flex;align-items:center;gap:.7rem;min-width:0;margin:0 0 1.5rem;
  padding:.8rem 1rem;border:1px solid var(--accent);border-radius:14px;background:var(--accent-soft);
  color:var(--text);text-decoration:none;font-size:.9rem;transition:background .15s,color .15s}
.content a.resume:hover{background:var(--accent);color:#fff}
.content a.resume:hover .resume-k,.content a.resume:hover .resume-t,
.content a.resume:hover .resume-go{color:#fff}
.resume-k{font-weight:700;color:var(--accent);flex:0 0 auto}
.resume-t{color:var(--muted);flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.resume-go{color:var(--muted);flex:0 0 auto}

.seclist{display:flex;flex-direction:column;max-width:880px;border:1px solid var(--border);
  border-radius:14px;background:var(--bg-2);overflow:hidden}
.content .seclist a{display:flex;align-items:center;gap:.9rem;min-width:0;padding:.8rem 1rem;
  text-decoration:none;color:var(--text);border:0;border-bottom:1px solid var(--border);
  font-size:.95rem;line-height:1.4;transition:background .12s}
.content .seclist a:last-child{border-bottom:0}
.content .seclist a:hover{background:var(--accent-soft)}
.seclist .num{font-size:.75rem;color:var(--accent);min-width:2em;flex:0 0 auto;
  font-variant-numeric:tabular-nums;font-weight:700}
.seclist .st{flex:1;min-width:0}
.content .seclist a::after{content:"›";flex:0 0 auto;color:var(--muted);font-size:1.05rem;opacity:.5}
.content .seclist a:hover::after{color:var(--accent);opacity:1}

.crumb{display:flex;align-items:center;gap:.45rem;flex-wrap:wrap;font-family:var(--ui-font);
  font-size:.8rem;color:var(--muted);margin:0 0 1.4rem;padding-right:3.25rem} /* clear of the back button */
.content .crumb a{color:var(--muted);text-decoration:none;border-bottom:0}
.content .crumb a:hover{color:var(--accent)}
.crumb-sep{opacity:.5}
.crumb-here{color:var(--text);font-weight:600}

.pager{display:flex;gap:1rem;margin-top:3.2rem;padding-top:1.3rem;border-top:1px solid var(--border);
  font-family:var(--ui-font);font-size:.9rem}
.pager a{display:inline-flex;align-items:center;gap:.4rem;max-width:48%;color:var(--accent);
  text-decoration:none;border:1px solid var(--border);border-radius:9px;padding:.55rem .75rem;
  background:var(--bg-2);line-height:1.25}
.pager a:hover{border-color:var(--accent);background:var(--accent-soft)}
.pager a span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pager .pager-next{margin-left:auto;text-align:right}
.pager-spacer{flex:1}
.empty{color:var(--muted);text-align:center;margin-top:4rem;font-family:var(--ui-font)}

/* ---- phones & small screens (the drawer is already an overlay on every device) ---- */
@media (max-width:680px){
  .btn{padding:.55rem .7rem;font-size:.95rem;min-height:42px}   /* bigger touch targets */
  .seg button{min-height:42px;padding:.5rem .6rem}
  input[type=range]{height:40px}
  input[type=range]::-webkit-slider-thumb{width:24px;height:24px;margin-top:-9px}
  input[type=range]::-moz-range-thumb{width:24px;height:24px}
  .closeSidebar{font-size:1.7rem;padding:.1rem .5rem}
  .tab{padding:.6rem .6rem}                          /* easier to tap */
  .group>summary{padding:.55rem .55rem}
  /* Give the text as much of the screen as the fixed corner buttons allow. Top clears the
     46px button row and nothing more; bottom is just breathing room + the home-bar inset.
     (Was 3.4rem / 4.5rem — ~70px of dead space on a phone screen.) */
  .content{padding:calc(3.05rem + env(safe-area-inset-top)) max(.9rem,env(safe-area-inset-right))
                   calc(1.6rem + env(safe-area-inset-bottom)) max(.9rem,env(safe-area-inset-left))}
  .cards{grid-template-columns:1fr;gap:.7rem}             /* one clean column on a phone */
  .content .home-h{font-size:1.7rem}
  .content a.card{padding:.9rem 1rem 1rem}
  .card-t{font-size:1.05rem;min-height:0}                 /* no filler line in a 1-col list */
  .card-p{font-size:.87rem;-webkit-line-clamp:3}
  .card-k{font-size:.7rem}
  .content .seclist a{padding:.95rem .9rem;font-size:1rem;gap:.75rem}
  .content a.resume{padding:.9rem 1rem;font-size:.95rem}
  .pager{flex-wrap:wrap;gap:.6rem}
  .pager a{max-width:100%;flex:1 1 100%}
  .pager .pager-next{margin-left:0;justify-content:flex-end}
  .content h2{margin-top:2em}                        /* less air between sections on a phone */
}

/* Touch devices have no hover, so buttons that only appear on hover are invisible forever
   after the load hint fades. Keep them faintly but permanently visible there instead —
   still out of the way while reading, but always findable. The drawer-open rule above
   still wins (higher specificity), so they stay hidden behind the scrim. */
@media (hover:none){
  .hamburger,.homebtn,.backbtn{opacity:.5}
}
</style>
</head>
<body class="sidebar-collapsed">
<div class="navbtns">
  <button class="hamburger" id="toggleSidebar" aria-label="Open menu" title="Menu">☰</button>
  <button class="homebtn" id="homeBtn" aria-label="Home" title="Home" hidden>⌂</button>
</div>
<button class="backbtn" id="backBtn" aria-label="Back" title="Back" hidden>←</button>

<div class="shell">
  <div class="scrim" id="scrim"></div>
  <nav class="sidebar" id="sidebar" aria-label="Menu and reading settings">
    <div class="sidebar-head">
      <span class="brand">__BRAND__</span>
      <button class="closeSidebar" id="closeSidebar" aria-label="Close menu" title="Close">×</button>
    </div>
    <div class="panel">
      <div class="panel-row">
        <span class="panel-lbl">Theme</span>
        <span class="seg" id="themeSeg">
          <button type="button" data-theme="dark" title="Dark">Dark</button>
          <button type="button" data-theme="light" title="Light">Light</button>
          <button type="button" data-theme="sepia" title="Warm / sepia">Sepia</button>
        </span>
      </div>
      <div class="panel-row">
        <span class="panel-lbl">Body font</span>
        <span class="seg" id="fontSeg">
          <button type="button" data-font="serif" title="Serif (Georgia)">Serif</button>
          <button type="button" data-font="sans" title="Sans-serif">Sans</button>
        </span>
      </div>
      <div class="slider-row">
        <label for="fontRange">Text size <span class="val" id="fontVal">19</span></label>
        <input type="range" id="fontRange" min="11" max="80" step="1" aria-label="Text size">
      </div>
      <div class="slider-row">
        <label for="leadRange">Line spacing <span class="val" id="leadVal">1.66</span></label>
        <input type="range" id="leadRange" min="1" max="4" step="0.05" aria-label="Line spacing">
      </div>
      <div class="slider-row">
        <label for="widthRange">Width <span class="val" id="widthVal">860</span></label>
        <input type="range" id="widthRange" min="340" max="3000" step="20" aria-label="Reading width">
      </div>
      <div class="panel-row">
        <button class="btn wide" id="widthFull" title="Fill the screen width">⇔ Full width</button>
        <button class="btn" id="resetReading" title="Reset font, size, spacing &amp; width">Reset</button>
      </div>
      <div class="panel-row">
        <span class="panel-lbl">Edge-tap pages</span>
        <button class="btn" id="edgeToggle" title="Tap the far left / right screen edge to turn pages">On</button>
      </div>
      <div class="panel-row">
        <span class="panel-lbl">On open</span>
        <span class="seg" id="startSeg">
          <button type="button" data-start="resume" title="Reopen where you left off">Resume</button>
          <button type="button" data-start="home" title="Always start on the home page">Home</button>
        </span>
      </div>
    </div>
    <input class="filter" id="filter" type="search" placeholder="Filter…" autocomplete="off">
    <a class="tab homelink" data-target="home" href="#home"><span class="num">⌂</span><span class="tab-title">Home</span></a>
    __SIDEBAR__
    <p class="built">Built __BUILT__ · rebuild: <code>py build_site.py</code></p>
  </nav>
  <main class="main" id="main">
    <div class="content" id="content">
      __SECTIONS__
    </div>
  </main>
</div>

<script>
(function(){
  var INITIAL = "__INITIAL__";
  var root = document.documentElement, body = document.body;
  var content = document.getElementById('content');
  var LS = window.localStorage;

  function $(id){return document.getElementById(id);}

  // ---- persisted reading preferences (shared across all generated pages) ----
  function getNum(k,d){var v=parseFloat(LS.getItem(k));return isNaN(v)?d:v;}
  var FONT_MIN=11,  FONT_MAX=80;
  var WIDTH_MIN=340, WIDTH_MAX=3000;
  var LEAD_MIN=1.0, LEAD_MAX=4.0;
  var DEF_FONT=19, DEF_WIDTH=860, DEF_LEAD=1.66, DEF_FAM='serif';
  var SERIF='Georgia,"Iowan Old Style","Palatino Linotype",Palatino,"Times New Roman",serif';
  var SANS='-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif';
  var font  = Math.min(FONT_MAX,  Math.max(FONT_MIN,  getNum('pa-font', DEF_FONT)));
  var width = Math.min(WIDTH_MAX, Math.max(WIDTH_MIN, getNum('pa-width', DEF_WIDTH)));
  var lead  = Math.min(LEAD_MAX,  Math.max(LEAD_MIN,  getNum('pa-leading', DEF_LEAD)));
  var theme = LS.getItem('pa-theme') || 'dark';            // 'dark' | 'light' | 'sepia'
  var fam   = LS.getItem('pa-fontfam')==='sans' ? 'sans' : 'serif';
  var fullw = LS.getItem('pa-fullwidth')==='1';
  var edges = LS.getItem('pa-edgetap')!=='0';              // edge-tap paging, on by default

  // ---- exact app height (iOS Safari: 100vh is TALLER than what you can actually see) ----
  // `dvh` is the CSS unit built for exactly this: it tracks the visible area as the browser's
  // toolbars slide in and out, with no JS at all. Where it exists, trust it and stay out of the
  // way — a JS measurement that disagrees (innerHeight is stale in some in-app browsers, e.g.
  // opening the file from the OneDrive app) is what leaves a band of dead space at the bottom.
  // Only older engines without dvh fall back to measuring.
  var hasDvh = !!(window.CSS && CSS.supports && CSS.supports('height', '100dvh'));
  if(!hasDvh){
    var lastH = 0;
    var setAppHeight = function(){
      var vv = window.visualViewport;
      var h = Math.round((vv && vv.height) || window.innerHeight);
      if(!h || Math.abs(h - lastH) < 2) return;      // ignore no-ops / 1px jitter
      lastH = h; root.style.setProperty('--app-h', h + 'px');
    };
    setAppHeight();
    window.addEventListener('resize', setAppHeight);
    window.addEventListener('orientationchange', function(){ setTimeout(setAppHeight, 250); });
    window.addEventListener('pageshow', setAppHeight);
    if(window.visualViewport) window.visualViewport.addEventListener('resize', setAppHeight);
  }

  // Reading-first: the menu is an overlay drawer, so it always starts CLOSED, on every device.
  body.classList.add('sidebar-collapsed');

  // Keep the reader anchored: note the block at the top of the viewport, apply the change, then
  // re-scroll so that same block sits under the same spot. So changing text size / line spacing /
  // width / font never jumps you away from where you were reading.
  function preserveScroll(fn){
    var main=$('main'), doc=document.querySelector('.doc.active'), anchor=null, off=0;
    if(doc){
      var top=main.getBoundingClientRect().top;
      var els=doc.querySelectorAll('h1,h2,h3,h4,h5,p,li,blockquote,div.callout,ul,ol,pre,table,hr,details,img');
      for(var i=0;i<els.length;i++){var r=els[i].getBoundingClientRect();
        if(r.bottom>top+2){anchor=els[i];off=r.top-top;break;}}
    }
    fn();
    if(anchor){
      var prev=main.style.scrollBehavior; main.style.scrollBehavior='auto';
      var nt=anchor.getBoundingClientRect().top-main.getBoundingClientRect().top;
      main.scrollTop += (nt-off); main.style.scrollBehavior=prev;
    }
  }

  function segActive(id,attr,val){var s=$(id); if(!s) return;
    Array.prototype.forEach.call(s.querySelectorAll('button'),function(b){
      b.classList.toggle('active', b.getAttribute(attr)===val);});}
  function setRange(id,v){var r=$(id); if(r && parseFloat(r.value)!==v) r.value=v;}

  // ---- setters (each clamps, persists, updates its read-out AND its slider/segment) ----
  function widthOut(){var v=$('widthVal'); if(v) v.textContent = fullw ? 'Max' : width;}
  function setFont(px){font=Math.min(FONT_MAX,Math.max(FONT_MIN,Math.round(px)));
    root.style.setProperty('--content-font',font+'px'); LS.setItem('pa-font',font);
    var v=$('fontVal'); if(v) v.textContent=font; setRange('fontRange',font);}
  function setLead(x){lead=Math.min(LEAD_MAX,Math.max(LEAD_MIN,Math.round(x*100)/100));
    root.style.setProperty('--content-leading',lead); LS.setItem('pa-leading',lead);
    var v=$('leadVal'); if(v) v.textContent=lead.toFixed(2); setRange('leadRange',lead);}
  function setWidth(px){width=Math.min(WIDTH_MAX,Math.max(WIDTH_MIN,Math.round(px)));
    root.style.setProperty('--content-width',width+'px'); LS.setItem('pa-width',width); widthOut(); setRange('widthRange',width);}
  function setFull(on){fullw=on; body.classList.toggle('full-width',on);
    LS.setItem('pa-fullwidth',on?'1':'0'); var b=$('widthFull'); if(b) b.classList.toggle('active',on); widthOut();}
  function applyFam(){root.style.setProperty('--read-font', fam==='sans'?SANS:SERIF);
    LS.setItem('pa-fontfam',fam); segActive('fontSeg','data-font',fam);}
  function applyTheme(){root.setAttribute('data-theme',theme); LS.setItem('pa-theme',theme);
    segActive('themeSeg','data-theme',theme);
    var bg={dark:'#1b1c1e',light:'#fbfbf9',sepia:'#f3e7cf'}[theme]||'#1b1c1e';
    var m=$('tcMeta'); if(m) m.setAttribute('content',bg);}
  setWidth(width); setFont(font); setLead(lead); applyFam(); applyTheme(); setFull(fullw);

  // ---- control handlers (all settings live inside the drawer) ----
  function wireRange(id,setter){var r=$(id); if(!r) return;
    r.addEventListener('input',function(){preserveScroll(function(){setter(parseFloat(r.value));});});}
  wireRange('fontRange', setFont);
  wireRange('leadRange', setLead);
  wireRange('widthRange', function(v){ if(fullw) setFull(false); setWidth(v); });

  $('themeSeg').addEventListener('click',function(e){var b=e.target.closest('[data-theme]');
    if(!b) return; theme=b.getAttribute('data-theme'); applyTheme();});      // colour only — no reflow
  $('fontSeg').addEventListener('click',function(e){var b=e.target.closest('[data-font]');
    if(!b) return; preserveScroll(function(){fam=b.getAttribute('data-font'); applyFam();});});
  $('widthFull').onclick =function(){preserveScroll(function(){setFull(!fullw);});};
  $('resetReading').onclick=function(){preserveScroll(function(){
    setFull(false); fam=DEF_FAM; applyFam(); setFont(DEF_FONT); setLead(DEF_LEAD); setWidth(DEF_WIDTH);});};

  // edge-tap paging toggle
  function applyEdge(){var b=$('edgeToggle'); if(b){b.textContent=edges?'On':'Off'; b.classList.toggle('active',edges);}
    LS.setItem('pa-edgetap',edges?'1':'0');}
  applyEdge();
  $('edgeToggle').onclick=function(){edges=!edges; applyEdge();};

  // ---- the invisible hamburger + overlay drawer (open/close never reflows the text) ----
  function openDrawer(){body.classList.remove('sidebar-collapsed');}
  function closeDrawer(){body.classList.add('sidebar-collapsed');}
  $('toggleSidebar').onclick=function(){body.classList.contains('sidebar-collapsed')?openDrawer():closeDrawer();};
  $('closeSidebar').onclick=closeDrawer;
  $('scrim').onclick=closeDrawer;
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'||e.keyCode===27){closeDrawer();return;}
    if(e.altKey||e.ctrlKey||e.metaKey||e.shiftKey) return;        // leave browser / OS shortcuts alone
    var ae=document.activeElement, tag=ae&&ae.tagName;
    if(tag==='INPUT'||tag==='TEXTAREA'||tag==='SELECT'||(ae&&ae.isContentEditable)) return;
    if(ae&&ae.closest&&ae.closest('.sidebar')) return;            // don't hijack arrows inside the drawer
    if(e.key==='ArrowLeft'||e.keyCode===37){ if(goPager('prev')) e.preventDefault(); }       // ← previous
    else if(e.key==='ArrowRight'||e.keyCode===39){ if(goPager('next')) e.preventDefault(); } // → next
  });

  // a brief hint on load so the (otherwise invisible) corner buttons are easy to find
  var hintable=[$('toggleSidebar'),$('homeBtn'),$('backBtn')];
  hintable.forEach(function(el){ if(el) el.classList.add('hint'); });
  setTimeout(function(){hintable.forEach(function(el){ if(el) el.classList.remove('hint'); });},2600);

  // ---- where you were: remembered per page, across closes/reopens ----
  var POSKEY = 'pa-pos:' + "__PAGEKEY__";
  var startMode = LS.getItem('pa-startmode')==='home' ? 'home' : 'resume';
  var POS;
  try{ POS = JSON.parse(LS.getItem(POSKEY)||'{}') || {}; }catch(e){ POS = {}; }
  if(!POS.s || typeof POS.s!=='object') POS.s = {};
  function isNavView(id){ return id==='home' || id.indexOf('sec-')===0; }
  function savePos(){ try{ LS.setItem(POSKEY, JSON.stringify(POS)); }catch(e){} }
  function rememberScroll(){
    var doc=document.querySelector('.doc.active'); if(!doc) return;
    var id=doc.getAttribute('data-tabid'); if(!id) return;
    POS.t=id;
    if(!isNavView(id)){ POS.f=id; POS.s[id]=Math.round($('main').scrollTop); }
  }
  function setScroll(y){
    var m=$('main'), prev=m.style.scrollBehavior;
    m.style.scrollBehavior='auto'; m.scrollTop=y||0; m.style.scrollBehavior=prev;
  }
  function applyStart(){ segActive('startSeg','data-start',startMode); LS.setItem('pa-startmode',startMode); }
  applyStart();
  $('startSeg').addEventListener('click',function(e){var b=e.target.closest('[data-start]');
    if(!b) return; startMode=b.getAttribute('data-start'); applyStart();});

  // ---- tab switching ----
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.tab'));
  function activate(tabid, push, restoreY){
    var doc = document.getElementById('doc-'+tabid);
    if(!doc) return false;
    rememberScroll();                                   // keep the spot on the page we're leaving
    document.querySelectorAll('.doc.active').forEach(function(d){d.classList.remove('active');});
    doc.classList.add('active');
    tabs.forEach(function(t){t.classList.toggle('active', t.getAttribute('data-target')===tabid);});
    var active = document.querySelector('.tab.active');
    if(active){
      var grp = active.closest('details'); if(grp) grp.open = true;
      active.scrollIntoView({block:'nearest'});
    }
    // picking a file from a menu starts at the top; only a reopen restores where you were
    var y = restoreY || 0;
    setScroll(y);
    if(y) requestAnimationFrame(function(){ setScroll(y); });   // again once fonts/layout settle
    if(push!==false) history.replaceState(null,'','#'+tabid);
    POS.t = tabid; if(!isNavView(tabid)){ POS.f = tabid; POS.s[tabid] = y; }
    savePos();
    updateBack();
    return true;
  }

  // ---- the way back out: file → its section → home ----
  function backTarget(){
    var doc=document.querySelector('.doc.active'); if(!doc) return null;
    var id=doc.getAttribute('data-tabid');
    if(!id || id==='home') return null;
    if(id.indexOf('sec-')===0) return 'home';
    var a=doc.querySelector('.crumb a[data-target^="sec-"]');
    return a ? a.getAttribute('data-target') : 'home';
  }
  function updateBack(){
    var t=backTarget(), b=$('backBtn');
    var doc=document.querySelector('.doc.active');
    var onHome = !!(doc && doc.getAttribute('data-tabid')==='home');
    if(b){
      b.hidden = !t;
      b.title = (t==='home') ? 'Back to home' : 'Back to this section';
    }
    var hb=$('homeBtn'); if(hb) hb.hidden = onHome;   // nothing to go to when already home
    // the menu views are UI, not prose — they get a wider measure
    body.classList.toggle('on-nav', !!(doc && doc.classList.contains('nav-view')));
  }
  $('backBtn').onclick=function(){ var t=backTarget(); if(t) activate(t); };
  $('homeBtn').onclick=function(){ activate('home'); };

  // keep the saved spot fresh while reading, and whenever the page is left/closed
  var saveTimer=null;
  $('main').addEventListener('scroll',function(){
    if(saveTimer) return;
    saveTimer=setTimeout(function(){saveTimer=null; rememberScroll(); savePos();},500);
  },{passive:true});
  document.addEventListener('visibilitychange',function(){
    if(document.hidden){ rememberScroll(); savePos(); }
  });
  window.addEventListener('pagehide',function(){ rememberScroll(); savePos(); });

  document.querySelector('.shell').addEventListener('click', function(e){
    var el = e.target.closest('[data-target]');
    if(!el) return;
    e.preventDefault();
    var target = el.getAttribute('data-target');
    // normal picks start at the top; only "Continue reading" returns to the exact spot
    activate(target, true, el.hasAttribute('data-restore') ? (POS.s[target]||0) : 0);
    closeDrawer();   // picking a tab / wiki-link closes the drawer, on every device
  });

  // go to the previous / next article (shared by edge-taps and the ← / → keys)
  function goPager(which){
    var doc=document.querySelector('.doc.active'); if(!doc) return false;
    var a=doc.querySelector(which==='prev'?'.pager-prev':'.pager-next');
    var t=a && a.getAttribute('data-target'); if(!t) return false;
    activate(t); return true;
  }

  // ---- edge-tap paging: tap the far left / right screen edge to go prev / next ----
  // Touch only; never blocks scrolling, text selection or links (we only act on a clean tap).
  (function(){
    var main=$('main'), pd=null;
    function flash(side){
      var d=document.createElement('div'); d.className='edge-flash '+side; document.body.appendChild(d);
      requestAnimationFrame(function(){d.classList.add('show');});
      setTimeout(function(){d.classList.remove('show');},150);
      setTimeout(function(){if(d.parentNode)d.parentNode.removeChild(d);},340);
    }
    main.addEventListener('pointerdown',function(e){
      pd={x:e.clientX,y:e.clientY,t:Date.now(),type:e.pointerType};
    },{passive:true});
    main.addEventListener('pointerup',function(e){
      var d=pd; pd=null;
      if(!edges || !d) return;
      if(d.type!=='touch') return;                              // a finger tap, not mouse / pen
      if(!body.classList.contains('sidebar-collapsed')) return; // ignore while the drawer is open
      if(Date.now()-d.t>450) return;                            // long-press is not a tap
      if(Math.abs(e.clientX-d.x)>12 || Math.abs(e.clientY-d.y)>12) return;  // moved = scroll / swipe
      if(window.getSelection && String(window.getSelection())) return;      // selecting text
      if(e.target.closest('a,button,input,textarea,select,summary,label,.wikilink')) return;
      var w=window.innerWidth, edge=Math.min(90, w*0.09);
      if(e.clientX<=edge){ if(goPager('prev')) flash('left'); }
      else if(e.clientX>=w-edge){ if(goPager('next')) flash('right'); }
    },{passive:true});
  })();

  // ---- sidebar filter ----
  var filter = document.getElementById('filter');
  filter.addEventListener('input', function(){
    var q = filter.value.trim().toLowerCase();
    document.querySelectorAll('.group').forEach(function(g){
      var any=false;
      g.querySelectorAll('.tab').forEach(function(t){
        var hit = t.textContent.toLowerCase().indexOf(q)>=0;
        t.style.display = hit?'':'none'; if(hit) any=true;
      });
      g.style.display = any?'':'none';
      if(q && any) g.open = true;
    });
  });

  // ---- "Continue reading" shortcut on the home page ----
  (function(){
    var card=$('homeResume'), out=$('homeResumeTitle');
    if(!card||!out) return;
    var t=POS.f;
    if(!t || isNavView(t) || !document.getElementById('doc-'+t)) return;
    var tab=null;
    for(var i=0;i<tabs.length;i++){ if(tabs[i].getAttribute('data-target')===t){tab=tabs[i];break;} }
    out.textContent = tab ? (tab.querySelector('.tab-title')||tab).textContent : t;
    card.setAttribute('data-target', t);
    card.setAttribute('data-restore', '1');   // this one goes back to the exact spot, not the top
    card.setAttribute('href', '#'+t);
    card.hidden = false;
  })();

  // ---- where to open: the address hash wins, then your last spot, then home ----
  var start = (location.hash||'').replace(/^#/,'');
  var opened = false;
  if(start) opened = activate(start, false, POS.s[start]||0);
  if(!opened && startMode==='resume' && POS.t) opened = activate(POS.t, false, POS.s[POS.t]||0);
  if(!opened) opened = activate('home', false);
  if(!opened) activate(INITIAL, false);
  window.addEventListener('hashchange', function(){
    var h=(location.hash||'').replace(/^#/,''); if(h) activate(h,false);
  });
})();
</script>
</body>
</html>
"""
if __name__ == "__main__":
    main()

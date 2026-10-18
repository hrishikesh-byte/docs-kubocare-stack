"""Give every doc a header, contents sidebar and sections, then rebuild index.html.

Safe to re-run: structure added by a previous run is stripped and rebuilt.
Usage: python3 -I tools/build_docs.py   (from the repo root)
"""
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {"index.html"}
MERMAID = (
    "<script type=\"module\">import mermaid from "
    "'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';"
    "mermaid.initialize({startOnLoad:true});</script>"
)
CSS = """*{box-sizing:border-box}
body{font:15px/1.6 system-ui,sans-serif;margin:0;color:#1f2328;background:#fff}
a{color:#0969da}
.doc-header{background:#f6f8fa;border-bottom:1px solid #d0d7de;padding:1.2rem 1.5rem}
.doc-header h1{margin:.3rem 0;font-size:1.7rem;line-height:1.25}
.crumbs{font-size:13px;color:#59636e}.crumbs a{text-decoration:none}
.meta{margin:0;font-size:13px;color:#59636e}
.badge{display:inline-block;padding:0 .5em;border-radius:1em;font-size:12px;background:#ddf4ff;color:#0550ae;margin-right:.4em}
.badge.old{background:#fff1e5;color:#953800}
.layout{display:grid;grid-template-columns:270px minmax(0,1fr);gap:2rem;max-width:1320px;margin:0 auto;padding:1.5rem}
.toc{position:sticky;top:1rem;align-self:start;max-height:calc(100vh - 2rem);overflow:auto;font-size:13.5px;border-right:1px solid #d0d7de;padding-right:1rem}
.toc-title{font-weight:600;text-transform:uppercase;letter-spacing:.04em;font-size:12px;color:#59636e;margin:0 0 .5rem}
.toc ul{list-style:none;margin:0;padding:0}.toc li{margin:.25rem 0}
.toc ul ul{padding-left:.9rem;border-left:2px solid #eaeef2;margin:.2rem 0 .4rem}
.toc a{text-decoration:none;color:#1f2328}.toc a:hover{color:#0969da}
main{min-width:0}
.doc-section{border-top:1px solid #eaeef2;padding-top:.4rem;margin-top:1.6rem}
.doc-section.intro{border:0;margin-top:0;padding-top:0}
h2{font-size:1.35rem;margin:.6rem 0}h3{font-size:1.1rem}
h2,h3,h4{scroll-margin-top:1rem}
.top{text-align:right;font-size:12px;margin:.6rem 0 0}.top a{color:#59636e;text-decoration:none}
code,pre{font-family:ui-monospace,monospace;font-size:13px;background:#f6f8fa;border-radius:4px}
code{padding:.1em .3em}pre{padding:.8rem;overflow:auto}pre code{padding:0;background:none}
table{border-collapse:collapse;display:block;overflow:auto;margin:1rem 0}
th,td{border:1px solid #d0d7de;padding:.35rem .7rem;text-align:left;vertical-align:top}
th{background:#f6f8fa}
blockquote{margin:0;padding:0 1rem;color:#59636e;border-left:.25em solid #d0d7de}
pre.mermaid{background:none;text-align:center}
.doc-footer{max-width:1320px;margin:0 auto;padding:1rem 1.5rem 2rem;font-size:13px;color:#59636e;border-top:1px solid #d0d7de}
@media (max-width:1000px){.layout{grid-template-columns:1fr}.toc{position:static;max-height:none;border-right:0;border-bottom:1px solid #d0d7de;padding:0 0 1rem}}"""

H1 = re.compile(r'<h1 id="([^"]*)">(.*?)</h1>', re.S)
HEAD = re.compile(r'<h([23]) id="([^"]+)">(.*?)</h\1>', re.S)
TAGS = re.compile(r"<[^>]+>")


def text(s):
    return html.unescape(TAGS.sub("", s)).strip()


def kind(rel):
    top = rel.parts[0] if len(rel.parts) > 1 else ""
    return {"decisions": "Decision", "evidence": "Evidence", "work-log": "Work log"}.get(top, "Core doc")


def raw_body(page):
    """Return (h1 html, content html) whether or not the page was structured before."""
    body = page.split("<body>", 1)[1].rsplit("</body>", 1)[0].replace(MERMAID, "")
    if "<!-- doc:content -->" in body:
        h1 = H1.search(body.split("<!-- doc:content -->")[0]).group(0)
        content = body.split("<!-- doc:content -->", 1)[1].split("<!-- /doc:content -->", 1)[0]
        content = re.sub(r'<section class="doc-section[^"]*"[^>]*>\n?', "", content)
        content = re.sub(r'<p class="top">.*?</p>\n?</section>\n?', "", content)
        return h1, content.strip() + "\n"
    m = H1.search(body)
    if not m:
        return None, body
    return m.group(0), body[m.end():].lstrip("\n")


def toc_html(content):
    items, out = [], ['<ul>']
    for lvl, hid, inner in HEAD.findall(content):
        items.append((int(lvl), hid, re.sub(r"</?a[^>]*>", "", inner)))
    open_sub = False
    for i, (lvl, hid, inner) in enumerate(items):
        if lvl == 3 and not open_sub:
            if i == 0:
                out.append("<li>")
            out.append("<ul>")
            open_sub = True
        elif lvl == 2:
            if open_sub:
                out.append("</ul>")
                open_sub = False
            if i:
                out.append("</li>")
            out.append("<li>")
        out.append(f'<a href="#{hid}">{inner}</a>' if lvl == 2 else f'<li><a href="#{hid}">{inner}</a></li>')
    if open_sub:
        out.append("</ul>")
    if items:
        out.append("</li>")
    out.append("</ul>")
    return "".join(out)


def sections(content):
    parts = re.split(r"(?=<h2 id=)", content)
    out = []
    for i, part in enumerate(parts):
        if not part.strip():
            continue
        if part.startswith("<h2 id="):
            hid = re.match(r'<h2 id="([^"]+)"', part).group(1)
            out.append(f'<section class="doc-section" aria-labelledby="{hid}">\n{part.rstrip()}\n'
                       '<p class="top"><a href="#top">Back to top</a></p>\n</section>\n')
        else:
            out.append(f'<section class="doc-section intro">\n{part.rstrip()}\n'
                       '<p class="top"><a href="#top">Back to top</a></p>\n</section>\n')
    return "".join(out)


def meta(rel, title, intro_text):
    k = kind(rel)
    bits = [f'<span class="badge">{k}</span>']
    d = re.match(r"(\d{4}-\d{2}-\d{2})_", rel.name)
    if d:
        bits.append(f"Date {d.group(1)}")
    a = re.match(r"(ADR-\d{4})", rel.name)
    if a:
        bits.append(a.group(1))
        if re.search(r"superseded", intro_text, re.I):
            bits.insert(1, '<span class="badge old">Superseded</span>')
    bits.append(f"<code>{html.escape(str(rel))}</code>")
    return " ".join(bits[:2]) + " " + " &middot; ".join(bits[2:])


def page_html(title, head_block, toc, main, footer, mermaid):
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
        f"<title>{html.escape(title)}</title>\n<style>\n{CSS}\n</style>\n</head>\n<body>\n"
        f"{head_block}{toc}{main}{footer}"
        + (MERMAID + "\n" if mermaid else "")
        + "</body>\n</html>\n"
    )


def first_para(content):
    m = re.search(r"<p>(.*?)</p>", content, re.S)
    t = re.sub(r"\s+", " ", text(m.group(1))) if m else ""
    return t if len(t) <= 220 else t[:220].rsplit(" ", 1)[0] + " ..."


def build_doc(path, docs):
    rel = path.relative_to(ROOT)
    h1, content = raw_body(path.read_text(encoding="utf-8"))
    if h1 is None:
        print(f"skip (no h1): {rel}")
        return
    title = text(H1.search(h1).group(2))
    intro = re.split(r"(?=<h2 id=)", content)[0]
    up = "../" * (len(rel.parts) - 1)
    crumb = f'<a href="{up}index.html">Stack docs</a> / {kind(rel)}'
    head_block = (
        '<!-- doc:header -->\n<header class="doc-header" id="top">\n'
        f'<nav class="crumbs" aria-label="Breadcrumb">{crumb}</nav>\n{h1}\n'
        f'<p class="meta">{meta(rel, title, text(intro))}</p>\n</header>\n<!-- /doc:header -->\n'
    )
    toc = ('<div class="layout">\n<nav class="toc" aria-label="Contents">\n<p class="toc-title">Contents</p>\n'
           f"{toc_html(content)}\n<p class=\"toc-title\" style=\"margin-top:1rem\"><a href=\"{up}index.html\">All docs</a></p>\n</nav>\n")
    main = f"<main>\n<!-- doc:content -->\n{sections(content)}<!-- /doc:content -->\n</main>\n</div>\n"
    footer = (f'<footer class="doc-footer"><a href="{up}index.html">All docs</a> &middot; '
              '<a href="#top">Back to top</a></footer>\n')
    path.write_text(page_html(title, head_block, toc, main, footer, 'class="mermaid"' in content),
                    encoding="utf-8")
    docs.append({"rel": rel, "title": title, "kind": kind(rel), "summary": first_para(intro),
                 "superseded": bool(re.search(r"superseded", text(intro), re.I)) and kind(rel) == "Decision"})


def build_index(docs):
    order = ["STATUS.html", "DESIGN.html", "RUNBOOK.html", "REPO_GUIDE.html"]
    groups = [
        ("start-here", "Start here", "Where the work is, how the stack fits together and how to run it.",
         sorted([d for d in docs if d["kind"] == "Core doc" and d["rel"].name in order],
                key=lambda d: order.index(d["rel"].name))),
        ("work-log", "Work log", "One entry per piece of work, newest first.",
         sorted([d for d in docs if d["kind"] == "Work log"], key=lambda d: d["rel"].name, reverse=True)),
        ("other-docs", "Other docs", "Notes and inputs that are not core docs.",
         sorted([d for d in docs if d["kind"] == "Core doc" and d["rel"].name not in order],
                key=lambda d: str(d["rel"]))),
        ("decisions", "Decisions (ADRs)", "One record per real choice the plan did not settle, in number order.",
         sorted([d for d in docs if d["kind"] == "Decision"], key=lambda d: d["rel"].name)),
        ("evidence", "Evidence", "Measured results, newest first.",
         sorted([d for d in docs if d["kind"] == "Evidence"], key=lambda d: d["rel"].name, reverse=True)),
    ]
    toc = "<ul>" + "".join(f'<li><a href="#{gid}">{name}</a> ({len(items)})</li>' for gid, name, _, items in groups) + "</ul>"
    body = []
    for gid, name, blurb, items in groups:
        rows = []
        for d in items:
            label = re.match(r"(ADR-\d{4}|\d{4}-\d{2}-\d{2})", d["rel"].name)
            tag = '<span class="badge old">Superseded</span>' if d["superseded"] else ""
            rows.append(f'<tr><td>{label.group(1) if label else ""}</td>'
                        f'<td><a href="{d["rel"]}">{html.escape(d["title"])}</a> {tag}</td>'
                        f'<td>{html.escape(d["summary"])}</td></tr>')
        body.append(f'<section class="doc-section" aria-labelledby="{gid}">\n<h2 id="{gid}">{name}</h2>\n'
                    f"<p>{blurb}</p>\n<table>\n<tr><th>Ref</th><th>Doc</th><th>Summary</th></tr>\n"
                    + "\n".join(rows) + '\n</table>\n<p class="top"><a href="#top">Back to top</a></p>\n</section>\n')
    head_block = ('<header class="doc-header" id="top">\n<nav class="crumbs">kubocare-stack</nav>\n'
                  '<h1 id="stack-docs">KuboCare stack docs index</h1>\n'
                  f'<p class="meta">{len(docs)} docs. Start with STATUS. Rebuilt by <code>tools/build_docs.py</code>.</p>\n'
                  '<p><input id="q" type="search" placeholder="Filter docs by title or summary" '
                  'style="width:100%;max-width:520px;padding:.45rem .6rem;border:1px solid #d0d7de;border-radius:6px;margin-top:.6rem"></p>\n</header>\n')
    nav = f'<div class="layout">\n<nav class="toc" aria-label="Contents">\n<p class="toc-title">Contents</p>\n{toc}\n</nav>\n'
    script = ("<script>document.getElementById('q').addEventListener('input',e=>{const q=e.target.value.toLowerCase();"
              "document.querySelectorAll('main tr').forEach((r,i)=>{if(r.querySelector('th'))return;"
              "r.style.display=r.textContent.toLowerCase().includes(q)?'':'none'})})</script>\n")
    main = "<main>\n" + "".join(body) + "</main>\n</div>\n"
    (ROOT / "index.html").write_text(page_html("KuboCare stack docs index", head_block, nav, main + script, "", False),
                                     encoding="utf-8")


def main():
    docs = []
    for p in sorted(ROOT.rglob("*.html")):
        if ".git" in p.parts or "tools" in p.parts or p.name in SKIP or p.is_symlink():
            continue
        build_doc(p, docs)
    build_index(docs)
    print(f"structured {len(docs)} docs, index rebuilt")


main()

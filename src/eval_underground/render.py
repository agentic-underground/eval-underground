"""The matrix (or a mini leaderboard picked from it) as text. Pure functions of the matrix dict.

Every number is shown to one decimal and links to its preferred source; its title carries the
locator and the verbatim text it was read from. A disputed cell is marked and lists every report.
"""
import csv
import io
import json
from html import escape

EMPTY = "—"


def _fmt(v):
    return f"{v:.1f}"


def _grid(m):
    by = {(c["model"], c["column"]): c for c in m["cells"]}
    return [(row, [by.get((row["id"], col["id"])) for col in m["columns"]]) for row in m["rows"]]


def _sources_line(m):
    return [(s["title"], s["url"], s.get("retrieved", "")) for s in m["sources"].values()]


def as_json(m):
    return json.dumps(m, indent=1, ensure_ascii=False, default=str) + "\n"  # YAML dates → ISO text


def as_csv(m):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["model", *(c["label"] for c in m["columns"])])
    for row, cells in _grid(m):
        w.writerow([row["id"], *("" if c is None else _fmt(c["value"]) for c in cells)])
    return out.getvalue()


def as_markdown(m):
    lines = ["| model | " + " | ".join(c["label"] for c in m["columns"]) + " |",
             "|---|" + "---:|" * len(m["columns"])]
    notes = []
    for row, cells in _grid(m):
        out = []
        for c in cells:
            if c is None:
                out.append(EMPTY)
                continue
            text = f'[{_fmt(c["value"])}]({c["sources"][0]["url"]})'
            if c["status"] == "disputed":
                notes.append(f'{row["id"]}: ' + "; ".join(f'{_fmt(s["value"])} ({s["source"]}, {s["locator"]})'
                                                          for s in c["sources"]))
                text += f" [^{len(notes)}]"
            out.append(text)
        lines.append(f'| {row["id"]} | ' + " | ".join(out) + " |")
    lines += ["", "Sources: " + "; ".join(f"[{t}]({u}), retrieved {r}" for t, u, r in _sources_line(m))]
    lines += [f"[^{i}]: disputed — {n}" for i, n in enumerate(notes, 1)]
    return "\n".join(lines) + "\n"


def _a(v):
    return escape(str(v), quote=True)


def _td(c, col_id):
    if c is None:
        return f'<td class="evu-empty" data-column="{_a(col_id)}">{EMPTY}</td>'
    top = c["sources"][0]
    title = "\n".join(f'{s["source"]}: {_fmt(s["value"])} — {s["locator"]} — verbatim {s["verbatim"]}'
                      for s in c["sources"])
    mark = '<span class="evu-disputed" title="sources disagree">±</span>' if c["status"] == "disputed" else ""
    return (f'<td data-column="{_a(col_id)}" data-value="{c["value"]!r}"><a href="{_a(top["url"])}" '
            f'title="{_a(title)}">{_fmt(c["value"])}</a>{mark}</td>')


MINI_STYLE = """
.evu{--evu-bg:#fff;--evu-fg:#1d1d1f;--evu-muted:#6b6b70;--evu-line:#e3e3e8;--evu-accent:#4a3fc4;--evu-warn:#a85400;
 background:var(--evu-bg);color:var(--evu-fg);font:14px/1.45 system-ui,sans-serif;margin:1em 0;max-width:100%;overflow-x:auto}
@media (prefers-color-scheme:dark){.evu{--evu-bg:#151517;--evu-fg:#ececf0;--evu-muted:#9a9aa3;--evu-line:#2c2c31;
 --evu-accent:#a89bff;--evu-warn:#f0a050}}
.evu table{border-collapse:collapse;font-variant-numeric:tabular-nums}
.evu th,.evu td{border-bottom:1px solid var(--evu-line);padding:6px 10px;text-align:right;vertical-align:bottom}
.evu th:first-child,.evu td:first-child{text-align:left}
.evu th{font-weight:600;font-size:12px}
.evu td a{color:var(--evu-accent);text-decoration:none}
.evu td a:hover{text-decoration:underline}
.evu .evu-empty{color:var(--evu-muted)}
.evu .evu-disputed{color:var(--evu-warn);font-size:11px;margin-left:2px}
.evu figcaption{color:var(--evu-muted);font-size:12px;margin-top:6px}
.evu figcaption a{color:inherit}
"""


def _table(m, sortable=False):
    def th(c):
        label = escape(c["label"])
        if sortable:  # a button, so the sort is reachable from the keyboard too
            label = f'<button type="button" class="evu-sort">{label}</button>'
        return f'<th data-column="{_a(c["id"])}">{label}</th>'
    head = "".join(th(c) for c in m["columns"])
    body = []
    for row, cells in _grid(m):
        attrs = f'data-family="{_a(row["family"])}" data-kind="{_a(row["kind"])}"'
        body.append(f'<tr {attrs}><td>{escape(row["id"])}</td>'
                    + "".join(_td(c, col["id"]) for c, col in zip(cells, m["columns"])) + "</tr>")
    return f'<table><thead><tr><th>model</th>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def _caption(m):
    srcs = "; ".join(f'<a href="{_a(u)}">{escape(t)}</a>' + (f", retrieved {escape(str(r))}" if r else "")
                     for t, u, r in _sources_line(m))
    return (f"<figcaption>Published scores, 0–100. Every number links to its source. Source: {srcs}. "
            "Made with eval-underground.</figcaption>")


def mini_html(m):
    """A self-contained fragment: paste it into a post, or open it on its own. Styles are scoped to .evu."""
    return f'<figure class="evu"><style>{MINI_STYLE}</style>{_table(m)}{_caption(m)}</figure>\n'


PAGE_SCRIPT = """
(function(){
  var page=document.querySelector('.evu-page');
  function apply(){
    var fam=page.querySelector('#evu-family').value, kind=page.querySelector('#evu-kind').value;
    page.querySelectorAll('tbody tr').forEach(function(tr){
      tr.hidden=(fam&&tr.dataset.family!==fam)||(kind&&tr.dataset.kind!==kind);
    });
  }
  page.querySelectorAll('select').forEach(function(s){s.addEventListener('change',apply);});
  // Sort by a column: best first, a second press reverses; an empty cell always goes last.
  page.querySelectorAll('button.evu-sort').forEach(function(btn){
    btn.addEventListener('click',function(){
      var th=btn.closest('th'), col=th.dataset.column, tbody=page.querySelector('tbody');
      var desc=th.getAttribute('aria-sort')!=='descending';
      page.querySelectorAll('thead th').forEach(function(h){h.removeAttribute('aria-sort');});
      th.setAttribute('aria-sort',desc?'descending':'ascending');
      var rows=Array.prototype.slice.call(tbody.rows);
      function val(tr){
        var td=tr.querySelector('td[data-column="'+CSS.escape(col)+'"]');
        return td&&td.dataset.value!==undefined?parseFloat(td.dataset.value):null;
      }
      rows.sort(function(a,b){
        var x=val(a), y=val(b);
        if(x===null||y===null) return (x===null)-(y===null);
        return desc?y-x:x-y;
      });
      rows.forEach(function(tr){tbody.appendChild(tr);});
    });
  });
  page.querySelectorAll('input[data-toggle]').forEach(function(box){
    box.addEventListener('change',function(){
      page.querySelectorAll('[data-column="'+CSS.escape(box.dataset.toggle)+'"]').forEach(function(el){
        el.hidden=!box.checked;
      });
    });
  });
})();
"""

PAGE_STYLE = """
html,body{margin:0;background:#fff}
@media (prefers-color-scheme:dark){html,body{background:#151517}}
.evu-page{padding:16px}
.evu-page h1{font:600 18px system-ui,sans-serif;margin:0 0 12px}
.evu-page fieldset{border:1px solid var(--evu-line);border-radius:8px;margin:0 0 12px;padding:8px 12px;font-size:13px}
.evu-page legend{color:var(--evu-muted);font-size:12px}
.evu-page fieldset label{display:inline-block;margin:2px 14px 2px 0;white-space:nowrap}
.evu-page button.evu-sort{all:unset;cursor:pointer}
.evu-page button.evu-sort:focus-visible{outline:2px solid var(--evu-accent);outline-offset:2px}
.evu-page th[aria-sort=descending] button.evu-sort::after{content:" ▼"}
.evu-page th[aria-sort=ascending] button.evu-sort::after{content:" ▲"}
[hidden]{display:none!important}
"""


def page_html(m, title="Open-weight models — published benchmark scores"):
    """The whole matrix on one page: hide columns, filter by family and base/instruct."""
    families = sorted({r["family"] for r in m["rows"]})
    toggles = "".join(f'<label><input type="checkbox" checked data-toggle="{_a(c["id"])}"> {escape(c["label"])}</label>'
                      for c in m["columns"])
    fam = "".join(f'<option value="{_a(f)}">{escape(f)}</option>' for f in families)
    controls = (f'<fieldset><legend>columns</legend>{toggles}</fieldset>'
                f'<fieldset><legend>rows</legend><label>family <select id="evu-family"><option value="">all</option>'
                f'{fam}</select></label><label>kind <select id="evu-kind"><option value="">all</option>'
                '<option>base</option><option>instruct</option></select></label></fieldset>')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(title)}</title><style>{MINI_STYLE}{PAGE_STYLE}</style></head><body>'
            f'<div class="evu evu-page"><h1>{escape(title)}</h1>{controls}{_table(m, sortable=True)}{_caption(m)}</div>'
            f'<script>{PAGE_SCRIPT}</script></body></html>\n')

"""The matrix: column identity, conflict marking, and picking a mini leaderboard out of it.

Pure functions over plain dicts. No file, network or clock is touched here.
"""
import difflib

SETTING_FIELDS = ("protocol", "mode", "shots", "metric")

# When sources report one cell differently, the one shown first. Every report stays listed.
SOURCE_PREFERENCE = ("paper", "model_card", "leaderboard", "index", "run")


class PickError(ValueError):
    """A model or column the writer asked for is not in the matrix, or names more than one column."""


def _setting(setting):
    return {f: str(setting.get(f, "unstated")) for f in SETTING_FIELDS}


def column_id(benchmark, setting):
    """One column is one benchmark under one setting; MMLU-Pro 5-shot and 0-shot never share one."""
    return "|".join((benchmark, *_setting(setting).values()))


def column_label(benchmark, setting):
    s = _setting(setting)
    parts = [benchmark] + [v for v in (s["protocol"], s["mode"]) if v != "unstated"]
    if s["shots"] != "unstated":
        parts.append(f'{s["shots"]}-shot')
    if s["metric"] != "unstated":
        parts.append(s["metric"])
    return " · ".join(parts)


def _rank(kind):
    return SOURCE_PREFERENCE.index(kind) if kind in SOURCE_PREFERENCE else len(SOURCE_PREFERENCE)


def build_matrix(sources, cells_by_source, models):
    """Every source's cells in one matrix. Reports of one cell that differ show the preferred source's
    value, are marked disputed, and keep every report. A score whose model has no row raises KeyError."""
    rows = {m["id"]: m for m in models}
    columns, reports = {}, {}
    for sid in sorted(cells_by_source):
        src = sources[sid]
        for c in cells_by_source[sid]:
            if c["model"] not in rows:
                raise KeyError(f"{sid}: {c['model']} has a score but no model row")
            cid = column_id(c["benchmark"], c["setting"])
            columns.setdefault(cid, {"id": cid, "benchmark": c["benchmark"], **_setting(c["setting"]),
                                     "label": column_label(c["benchmark"], c["setting"])})
            reports.setdefault((c["model"], cid), []).append({
                "source": sid, "kind": src["kind"], "url": src["url"], "value": float(c["value"]),
                "locator": c.get("locator", ""), "verbatim": c.get("verbatim", "")})
    cells = []
    for (model, cid), rs in sorted(reports.items()):
        rs.sort(key=lambda r: (_rank(r["kind"]), r["source"]))
        cells.append({"model": model, "column": cid, "value": rs[0]["value"],
                      "status": "disputed" if len({r["value"] for r in rs}) > 1 else "agreed", "sources": rs})
    used = {c["model"] for c in cells}
    return {
        "columns": sorted(columns.values(), key=lambda c: (c["benchmark"], c["id"])),
        "rows": [m for m in models if m["id"] in used],
        "cells": cells,
        "sources": {sid: sources[sid] for sid in sorted({r["source"] for c in cells for r in c["sources"]})},
    }


def _column_for(query, columns):
    exact = [c for c in columns if c["id"] == query]
    if exact:
        return exact[0]
    q = query.casefold()
    named = [c for c in columns if c["benchmark"].casefold() == q] or \
            [c for c in columns if c["label"].casefold().startswith(q)]
    if len(named) == 1:
        return named[0]
    if named:
        raise PickError(f"column {query!r} means {len(named)} columns; name one by its id:\n  "
                        + "\n  ".join(f'{c["id"]}   ({c["label"]})' for c in named))
    near = difflib.get_close_matches(query, sorted({c["benchmark"] for c in columns}), n=5, cutoff=0.3)
    raise PickError(f"no column {query!r}" + (f"; did you mean: {', '.join(near)}" if near else ""))


def pick(matrix, model_ids, column_queries):
    """A mini leaderboard: the asked-for rows and columns, in the order asked, with their cells and sources."""
    rows = {r["id"]: r for r in matrix["rows"]}
    missing = [m for m in model_ids if m not in rows]
    if missing:
        lines = []
        for m in missing:
            near = difflib.get_close_matches(m, rows, n=5, cutoff=0.6)
            lines.append(f"no model {m!r}" + (f"; did you mean: {', '.join(near)}" if near else ""))
        raise PickError("\n".join(lines))
    cols = [_column_for(q, matrix["columns"]) for q in column_queries]
    want = {(m, c["id"]) for m in model_ids for c in cols}
    cells = [c for c in matrix["cells"] if (c["model"], c["column"]) in want]
    used = {r["source"] for c in cells for r in c["sources"]}
    return {"rows": [rows[m] for m in model_ids], "columns": cols, "cells": cells,
            "sources": {k: v for k, v in matrix["sources"].items() if k in used}}

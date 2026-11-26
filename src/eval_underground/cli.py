"""eval-underground — published benchmark scores for open-weight model families.

    eval-underground import open-llm-leaderboard-v2    fetch the archive, check its sha256, write data/
    eval-underground matrix --out out/                 the whole matrix: index.html, .md, .csv, .json
    eval-underground mini --model A --model B --column MMLU-Pro --out post/
                                                       a mini leaderboard to embed: .html, .md, .csv, .json
"""
import argparse
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

from . import core, leaderboard, render, store

ROOT = Path(__file__).resolve().parents[2]


def _data_dir(args):
    return Path(args.data or os.environ.get("EVAL_UNDERGROUND_DATA") or ROOT / "data")


def _matrix(args):
    sources, cells, models = store.load(_data_dir(args))
    return core.build_matrix(sources, cells, models)


def _write(out, stem, m, html):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{stem}.html").write_text(html)
    (out / f"{stem}.md").write_text(render.as_markdown(m))
    (out / f"{stem}.csv").write_text(render.as_csv(m))
    (out / f"{stem}.json").write_text(render.as_json(m))
    return [str(out / f"{stem}.{ext}") for ext in ("html", "md", "csv", "json")]


def cmd_matrix(args):
    m = _matrix(args)
    written = _write(args.out, "index", m, render.page_html(m))
    print(f"{len(m['rows'])} models × {len(m['columns'])} columns, {len(m['cells'])} cells")
    print("\n".join(written))
    return 0


def cmd_mini(args):
    try:
        m = core.pick(_matrix(args), args.model, args.column)
    except core.PickError as e:
        print(f"eval-underground: {e}", file=sys.stderr)
        return 2
    print("\n".join(_write(args.out, "mini", m, render.mini_html(m))))
    return 0


def _cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "eval-underground"


def fetch(source):
    """The source document, from the cache or its URL; refused unless its sha256 is the recorded one."""
    path = _cache_dir() / source["id"] / source["revision"] / Path(source["url"]).name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"fetching {source['url']}", file=sys.stderr)
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(source["url"], tmp)
        tmp.rename(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != source["sha256"]:
        raise SystemExit(f"eval-underground: {path} has sha256 {digest}, the source record says "
                         f"{source['sha256']}. Delete it to fetch again, or update the record deliberately.")
    return path


def cmd_import(args):
    data = _data_dir(args)
    sources, _, models = store.load(data)
    if args.source != "open-llm-leaderboard-v2":
        print(f"eval-underground: no importer for {args.source!r}; known: open-llm-leaderboard-v2", file=sys.stderr)
        return 2
    try:
        import pyarrow.parquet as pq
    except ImportError:
        print("eval-underground: importing the leaderboard needs pyarrow: "
              "pip install 'eval-underground[import]'", file=sys.stderr)
        return 2
    rows = pq.read_table(fetch(sources[args.source])).to_pylist()
    cells, rows_out = leaderboard.to_cells(rows)
    store.dump(data / "cells" / f"{args.source}.yaml", {"source": args.source, "cells": cells})
    by_id = {m["id"]: m for m in models}
    by_id.update({m["id"]: m for m in rows_out})
    store.dump(data / "models.yaml", {"models": sorted(by_id.values(), key=lambda m: m["id"])})
    print(f"{args.source}: {len(cells)} cells, {len(rows_out)} models")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="eval-underground", description=__doc__.split("\n")[0])
    p.add_argument("--data", help="the data directory (default: the repository's data/)")
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("import", help="fetch a source, check its sha256, and write its cells")
    i.add_argument("source")
    i.set_defaults(fn=cmd_import)
    mx = sub.add_parser("matrix", help="render the whole matrix")
    mx.add_argument("--out", default="out")
    mx.set_defaults(fn=cmd_matrix)
    mi = sub.add_parser("mini", help="a mini leaderboard to embed")
    mi.add_argument("--model", action="append", required=True, help="a model id, e.g. Qwen/Qwen2.5-7B-Instruct")
    mi.add_argument("--column", action="append", required=True, help="a benchmark name or column id")
    mi.add_argument("--out", default="out/mini")
    mi.set_defaults(fn=cmd_mini)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

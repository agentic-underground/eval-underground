"""The reviewed data, as text in the repository: one file per source, so every number has a history.

    data/sources/<id>.yaml   where a source lives: URL, revision, retrieved, sha256
    data/cells/<id>.yaml     what was read from it: model, benchmark, setting, value, locator, verbatim
    data/models.yaml         one row per model
"""
from pathlib import Path

import yaml

# The C loader reads the 750 KB leaderboard file in 0.07 s; the pure-Python one takes 0.56 s.
_Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def _read(p):
    return yaml.load(Path(p).read_text(), Loader=_Loader)


def load(data_dir):
    d = Path(data_dir)
    sources = {}
    for p in sorted((d / "sources").glob("*.yaml")):
        s = _read(p)
        if s["id"] != p.stem:
            raise ValueError(f"{p}: id {s['id']!r} does not match its file name")
        sources[s["id"]] = s
    cells = {}
    for p in sorted((d / "cells").glob("*.yaml")):
        if p.stem not in sources:
            raise ValueError(f"{p}: no source record data/sources/{p.stem}.yaml")
        cells[p.stem] = _read(p)["cells"]
    models = _read(d / "models.yaml")["models"] if (d / "models.yaml").exists() else []
    return sources, cells, models


def dump(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=120))

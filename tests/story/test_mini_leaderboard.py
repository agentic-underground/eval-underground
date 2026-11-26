"""STORY — a writer picks three open-weight models and two benchmarks, runs one command, and gets a
mini leaderboard to embed in a post: every number is the published one, and links to where it was
published.

The DRIVER is the command line, as the writer types it. The WITNESS is independent of the tool's
code: it parses the produced HTML with the standard library and checks every number against the
verbatim value recorded in the reviewed data file, so a renderer that drew the wrong number, or
dropped the link, is caught.
"""
import csv
import functools
import json
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MODELS = ["Qwen/Qwen2.5-7B-Instruct", "meta-llama/Llama-3.1-8B-Instruct", "google/gemma-2-9b-it"]
COLUMNS = ["MMLU-Pro", "IFEval"]


class Table(HTMLParser):
    """Rows of (text, href) per cell, read from the first <table>."""

    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell, self._href, self._in = [], None, None, None, False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell, self._href = "", None
        elif tag == "a" and self._cell is not None:
            self._href = dict(attrs).get("href")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None:
            self._row.append((self._cell.strip(), self._href))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell += data


@functools.cache
def _reviewed():
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    return yaml.load((ROOT / "data/cells/open-llm-leaderboard-v2.yaml").read_text(), Loader=loader)["cells"]


def published(model, benchmark):
    """The witness's own reading: the verbatim raw value the source printed, as a percentage."""
    values = {round(float(c["verbatim"]) * 100, 1) for c in _reviewed()
              if c["model"] == model and c["benchmark"] == benchmark}
    assert len(values) == 1, f"{model} {benchmark}: the source reports {values}"
    return values.pop()


def test_a_writer_builds_a_mini_leaderboard_that_cites_its_sources(tmp_path):
    args = ["uv", "run", "--frozen", "--quiet", "eval-underground", "mini", "--out", str(tmp_path)]
    for m in MODELS:
        args += ["--model", m]
    for c in COLUMNS:
        args += ["--column", c]
    done = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr

    source = yaml.safe_load((ROOT / "data/sources/open-llm-leaderboard-v2.yaml").read_text())
    page = Table()
    page.feed((tmp_path / "mini.html").read_text())
    header, *body = page.rows
    assert len(header) == 1 + len(COLUMNS), header
    for i, col in enumerate(COLUMNS, 1):
        assert header[i][0].startswith(col), header
    assert [r[0][0] for r in body] == MODELS
    for row in body:
        for i, col in enumerate(COLUMNS, 1):
            text, href = row[i]
            assert float(text) == published(row[0][0], col), (row[0][0], col, text)
            assert href == source["url"], (row[0][0], col, href)

    md = (tmp_path / "mini.md").read_text()
    assert all(m in md for m in MODELS) and source["url"] in md
    as_json = json.loads((tmp_path / "mini.json").read_text())
    assert [r["id"] for r in as_json["rows"]] == MODELS
    with open(tmp_path / "mini.csv", newline="") as f:
        assert [r["model"] for r in csv.DictReader(f)] == MODELS

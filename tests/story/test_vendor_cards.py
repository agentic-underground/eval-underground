"""STORY — a writer compares the four small Qwen3.5 models on MMLU-Pro as Qwen itself reported them,
and every number links to the model's own card at the exact revision it was read from.

The card scores entered the data only where two blind readings, made by different methods, agreed.
The WITNESS is the reviewed data, read with no code from the tool: each number must be the verbatim
text recorded from that model's own card, and its link must be that card's pinned URL.
"""
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
# The 0.8B/2B card states the mode of its table; the 4B/9B card does not, so they are two columns.
THINKING, UNSTATED = "MMLU-Pro · Qwen3.5 model card · thinking", "MMLU-Pro · Qwen3.5 model card"
WANT = {"Qwen/Qwen3.5-0.8B": THINKING, "Qwen/Qwen3.5-2B": THINKING,
        "Qwen/Qwen3.5-4B": UNSTATED, "Qwen/Qwen3.5-9B": UNSTATED}


def _yaml(rel):
    return yaml.load((ROOT / rel).read_text(), Loader=_LOADER)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self._row, self._href, self._text = [], None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._href, self._text = None, ""
        elif tag == "a":
            self._href = dict(attrs).get("href")

    def handle_data(self, data):
        if self._text is not None:
            self._text += data

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None:
            self._row.append((self._text.strip(), self._href))
            self._text = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def test_a_writer_compares_the_small_qwen35_models_as_qwen_reported_them(tmp_path):
    args = ["uv", "run", "--frozen", "--quiet", "eval-underground", "mini", "--out", str(tmp_path),
            "--column", THINKING, "--column", UNSTATED]
    for m in WANT:
        args += ["--model", m]
    done = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr

    page = Links()
    page.feed((tmp_path / "mini.html").read_text())
    header, *body = page.rows
    labels = [h for h, _ in header][1:]
    assert labels == [THINKING, UNSTATED], labels
    assert [r[0][0] for r in body] == list(WANT)
    for row in body:
        model = row[0][0]
        own = f"hf-card-{model.split('/')[1].lower()}"
        card = _yaml(f"data/sources/{own}.yaml")
        mode = "thinking" if WANT[model] == THINKING else "unstated"
        verbatim = {c["verbatim"] for c in _yaml(f"data/cells/{own}.yaml")["cells"]
                    if c["model"] == model and c["benchmark"] == "MMLU-Pro" and c["setting"]["mode"] == mode}
        assert len(verbatim) == 1, (model, verbatim)
        text, href = row[1 + labels.index(WANT[model])]
        assert float(text) == float(verbatim.pop()), (model, text)
        assert href == card["url"] and card["revision"] in href, (model, href)
        other, _ = row[1 + (1 - labels.index(WANT[model]))]
        assert other == "—", (model, "a score under a setting its card did not report", other)

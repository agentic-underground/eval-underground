"""STORY — a reader opens the whole matrix, hides a benchmark they do not care about, narrows it to one
family, sorts by MMLU-Pro, and the best model of that family is on top, its number linking to the row
and column it was published in.

The DRIVER is a real browser, clicking and choosing as a person does. The WITNESS for every claim is
the reviewed data file, read here with no code from the tool: which models a family has, which value
was published, and where. A page that hid the wrong column, filtered the wrong rows or sorted wrongly
disagrees with it.

Needs a browser once per machine: `uv run playwright install chromium-headless-shell`.
"""
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
FAMILY, HIDE, SORT = "google", "GPQA", "MMLU-Pro"
_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def _yaml(rel):
    return yaml.load((ROOT / rel).read_text(), Loader=_LOADER)


@pytest.fixture
def page(tmp_path):
    sync_api = pytest.importorskip("playwright.sync_api")
    done = subprocess.run(["uv", "run", "--frozen", "--quiet", "eval-underground", "matrix", "--out", str(tmp_path)],
                          cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except sync_api.Error as e:
            pytest.fail(f"no browser: run `uv run playwright install chromium-headless-shell` ({e})")
        try:
            p = browser.new_page()
            p.goto((tmp_path / "index.html").as_uri())
            yield p
        finally:
            browser.close()


def visible_column_labels(p):
    return [t.strip() for t in p.locator("thead th:visible").all_inner_texts()]


def test_a_reader_narrows_the_matrix_to_one_family_and_sorts_it(page):
    p = page
    models = {m["id"]: m for m in _yaml("data/models.yaml")["models"]}
    cells = _yaml("data/cells/open-llm-leaderboard-v2.yaml")["cells"]
    source_url = _yaml("data/sources/open-llm-leaderboard-v2.yaml")["url"]

    # hide a benchmark
    p.locator("fieldset label", has_text=HIDE).locator("input").uncheck()
    shown = visible_column_labels(p)
    assert not any(h.startswith(HIDE) for h in shown), shown
    assert len(shown) == 1 + 5, shown

    # one family
    p.select_option("#evu-family", FAMILY)
    rows = p.locator("tbody tr:visible")
    family = sorted(i for i, m in models.items() if m["family"] == FAMILY)
    assert sorted(t.split("\t")[0].strip() for t in rows.all_inner_texts()) == family

    # sort by a benchmark: best first
    p.locator("thead th:visible", has_text=SORT).click()
    col = next(i for i, h in enumerate(visible_column_labels(p)) if h.startswith(SORT))
    names = [r.locator("td:visible").nth(0).inner_text().strip() for r in rows.all()]
    # the number is the link's text; a disputed cell also carries a mark beside it
    shown_values = [(lambda a: a.inner_text().strip() if a.count() else "—")(r.locator("td:visible").nth(col).locator("a"))
                    for r in rows.all()]
    numbers = [float(v) for v in shown_values if v != "—"]
    assert numbers == sorted(numbers, reverse=True), shown_values

    published = {}
    for c in cells:
        if c["benchmark"] == SORT and models[c["model"]]["family"] == FAMILY:
            published.setdefault(c["model"], []).append(c)
    best = max(published, key=lambda m: max(float(c["verbatim"]) for c in published[m]))
    assert names[0] == best, (names[:3], best)
    assert numbers[0] in {round(float(c["verbatim"]) * 100, 1) for c in published[best]}

    # …and follow its number to where it was published
    link = rows.first.locator("td:visible").nth(col).locator("a")
    assert link.get_attribute("href") == source_url
    assert any(c["locator"] in link.get_attribute("title") for c in published[best])

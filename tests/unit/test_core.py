import pytest

from eval_underground import core, leaderboard

SRC = {"lb": {"id": "lb", "kind": "leaderboard", "url": "https://example.org/lb"},
       "card": {"id": "card", "kind": "model_card", "url": "https://example.org/card"}}
MMLU5 = {"protocol": "lb-v2", "shots": 5, "metric": "acc"}


def cell(model, value, benchmark="MMLU-Pro", setting=MMLU5, verbatim=None):
    return {"model": model, "benchmark": benchmark, "setting": setting, "value": value,
            "locator": "row 1", "verbatim": verbatim or str(value)}


def models(*ids):
    return [{"id": i, "family": i.split("/")[0], "params_b": 1.0, "kind": "base"} for i in ids]


def test_one_benchmark_under_two_settings_is_two_columns():
    other = {**MMLU5, "shots": 0}
    m = core.build_matrix(SRC, {"lb": [cell("a/x", 40.0), cell("a/x", 30.0, setting=other)]}, models("a/x"))
    assert len(m["columns"]) == 2
    assert {c["label"] for c in m["columns"]} == {"MMLU-Pro · lb-v2 · 5-shot · acc", "MMLU-Pro · lb-v2 · 0-shot · acc"}


def test_two_sources_disagreeing_show_the_preferred_one_and_are_marked_disputed():
    m = core.build_matrix(SRC, {"lb": [cell("a/x", 40.0)], "card": [cell("a/x", 41.5)]}, models("a/x"))
    (c,) = m["cells"]
    assert c["value"] == 41.5 and c["status"] == "disputed"
    assert [s["source"] for s in c["sources"]] == ["card", "lb"]


def test_agreeing_reports_are_one_agreed_cell():
    m = core.build_matrix(SRC, {"lb": [cell("a/x", 40.0), cell("a/x", 40.0)]}, models("a/x"))
    (c,) = m["cells"]
    assert c["status"] == "agreed" and len(c["sources"]) == 2


def test_a_score_for_a_model_with_no_row_is_refused_by_name():
    with pytest.raises(KeyError, match="b/y"):
        core.build_matrix(SRC, {"lb": [cell("b/y", 1.0)]}, models("a/x"))


def test_pick_keeps_the_order_asked_for_and_matches_a_benchmark_by_name():
    m = core.build_matrix(SRC, {"lb": [cell("a/x", 1.0), cell("a/y", 2.0),
                                       cell("a/x", 3.0, benchmark="IFEval", setting={"shots": 0})]},
                          models("a/x", "a/y"))
    p = core.pick(m, ["a/y", "a/x"], ["ifeval", "MMLU-Pro"])
    assert [r["id"] for r in p["rows"]] == ["a/y", "a/x"]
    assert [c["benchmark"] for c in p["columns"]] == ["IFEval", "MMLU-Pro"]
    assert {(c["model"], c["value"]) for c in p["cells"]} == {("a/x", 3.0), ("a/x", 1.0), ("a/y", 2.0)}


def test_pick_refuses_an_unknown_model_and_names_the_near_ones():
    m = core.build_matrix(SRC, {"lb": [cell("a/x-7b", 1.0)]}, models("a/x-7b"))
    with pytest.raises(core.PickError, match="a/x-7b"):
        core.pick(m, ["a/x-7"], ["MMLU-Pro"])


def test_pick_refuses_a_benchmark_name_that_means_two_columns():
    m = core.build_matrix(SRC, {"lb": [cell("a/x", 1.0), cell("a/x", 2.0, setting={**MMLU5, "shots": 0})]},
                          models("a/x"))
    with pytest.raises(core.PickError, match="0-shot"):
        core.pick(m, ["a/x"], ["MMLU-Pro"])


ROW = {"fullname": "Org/M-7B-Instruct", "eval_name": "Org_M-7B-Instruct_bfloat16", "Precision": "bfloat16",
       "Official Providers": True, "#Params (B)": 7.6, "Type": "💬 chat models (RLHF, DPO, IFT, ...)",
       "IFEval Raw": 0.75, "BBH Raw": 0.5, "MATH Lvl 5 Raw": 0.25, "GPQA Raw": 0.3, "MUSR Raw": 0.4,
       "MMLU-PRO Raw": 0.4316, "Upload To Hub Date": "2024-09-16"}


def test_the_leaderboard_import_reads_raw_scores_as_percentages_and_keeps_the_verbatim():
    cells, rows = leaderboard.to_cells([ROW, {**ROW, "fullname": "Other/Fine-Tune", "Official Providers": False}])
    assert [r["id"] for r in rows] == ["Org/M-7B-Instruct"]
    assert rows[0]["kind"] == "instruct" and rows[0]["params_b"] == 7.6
    mmlu = next(c for c in cells if c["benchmark"] == "MMLU-Pro")
    assert mmlu["value"] == 43.16 and mmlu["verbatim"] == "0.4316"
    assert mmlu["setting"] == {"protocol": "Open LLM Leaderboard v2", "shots": 5, "metric": "acc"}
    assert "Org_M-7B-Instruct_bfloat16" in mmlu["locator"] and "MMLU-PRO Raw" in mmlu["locator"]
    assert len(cells) == 6


def test_a_pretrained_row_is_base():
    _, rows = leaderboard.to_cells([{**ROW, "Type": "🟢 pretrained"}])
    assert rows[0]["kind"] == "base"


# --- two blind readings of one source -------------------------------------------------------------

def reading(model, bench, value, mode="unstated", group="Knowledge & STEM"):
    return {"model": model, "benchmark": bench, "mode": mode, "value": value, "verbatim": str(value), "group": group}


CARD = {"id": "card", "kind": "model_card", "url": "https://example.org/card", "protocol": "Qwen3.5 model card",
        "table": "Benchmark Results › Language"}


def test_two_readings_that_match_are_agreed_cells_with_the_card_as_their_setting():
    a = [reading("Q/x", "MMLU-Pro", 82.5)]
    agreed, held = core.agree(CARD, a, [dict(r) for r in a])
    assert held == []
    (c,) = agreed
    assert c["setting"] == {"protocol": "Qwen3.5 model card", "mode": "unstated"}
    assert c["value"] == 82.5 and c["verbatim"] == "82.5"
    assert c["locator"] == "Benchmark Results › Language, group 'Knowledge & STEM', row 'MMLU-Pro', column 'Q/x'"


def test_a_value_the_readings_disagree_on_is_held_with_both_readings():
    agreed, held = core.agree(CARD, [reading("Q/x", "MMLU-Pro", 82.5)], [reading("Q/x", "MMLU-Pro", 85.2)])
    assert agreed == []
    (h,) = held
    assert (h["a"]["value"], h["b"]["value"]) == (82.5, 85.2)


def test_a_cell_only_one_reading_found_is_held():
    agreed, held = core.agree(CARD, [reading("Q/x", "MMLU-Pro", 82.5), reading("Q/x", "IFEval", 91.0)],
                              [reading("Q/x", "MMLU-Pro", 82.5)])
    assert [c["benchmark"] for c in agreed] == ["MMLU-Pro"]
    assert held[0]["b"] is None and held[0]["a"]["benchmark"] == "IFEval"


def test_one_benchmark_in_two_modes_is_two_cells():
    both = [reading("Q/x", "IFEval", 70.0, mode="non-thinking"), reading("Q/x", "IFEval", 80.0, mode="thinking")]
    agreed, held = core.agree(CARD, both, [dict(r) for r in both])
    assert held == [] and len(agreed) == 2
    m = core.build_matrix({"card": CARD}, {"card": agreed}, models("Q/x"))
    assert sorted(c["label"] for c in m["columns"]) == ["IFEval · Qwen3.5 model card · non-thinking",
                                                         "IFEval · Qwen3.5 model card · thinking"]


def test_among_cards_that_agree_the_one_about_the_model_is_shown_first():
    own = {"id": "z-own", "kind": "model_card", "url": "https://example.org/own", "model": "Q/x"}
    other = {"id": "a-other", "kind": "model_card", "url": "https://example.org/other", "model": "Q/y"}
    m = core.build_matrix({"z-own": own, "a-other": other},
                          {"z-own": [cell("Q/x", 50.0)], "a-other": [cell("Q/x", 50.0)]}, models("Q/x"))
    assert [s["source"] for s in m["cells"][0]["sources"]] == ["z-own", "a-other"]


def test_a_column_named_by_its_whole_label_is_that_column_even_when_it_prefixes_another():
    base = {"protocol": "card"}
    m = core.build_matrix(SRC, {"lb": [cell("a/x", 1.0, setting=base),
                                       cell("a/x", 2.0, setting={**base, "mode": "thinking"})]}, models("a/x"))
    (col,) = core.pick(m, ["a/x"], ["MMLU-Pro · card"])["columns"]
    assert col["label"] == "MMLU-Pro · card"

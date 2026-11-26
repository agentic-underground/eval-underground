"""The Open LLM Leaderboard v2 archive → cells and model rows.

Only rows the leaderboard marks `Official Providers` are taken: each family's own releases, not
community fine-tunes. Values are the RAW scores (0–1, printed verbatim) as percentages, not the
leaderboard's chance-normalised ones, so they sit in the same columns as a model card's accuracy.

Shots and metrics are the leaderboard's own statement of them, in its "About" page
(data/sources/open-llm-leaderboard-v2.yaml names it); the archive itself carries none.
"""

PROTOCOL = "Open LLM Leaderboard v2"

# archive column → (benchmark, shots, metric), as the About page states them.
BENCHMARKS = {
    "IFEval Raw": ("IFEval", 0, "strict acc (prompt+inst mean)"),
    "BBH Raw": ("BBH", 3, "acc_norm"),
    "MATH Lvl 5 Raw": ("MATH Lvl 5", 4, "exact_match"),
    "GPQA Raw": ("GPQA", 0, "acc_norm"),
    "MUSR Raw": ("MuSR", 0, "acc_norm"),
    "MMLU-PRO Raw": ("MMLU-Pro", 5, "acc"),
}


def _kind(type_label):
    return "base" if "pretrained" in type_label else "instruct"


def to_cells(rows):
    """Archive rows → (cells, model rows). Pure; the caller reads the parquet."""
    cells, models = [], {}
    for r in sorted(rows, key=lambda r: (r["fullname"], r["eval_name"])):
        if not r.get("Official Providers"):
            continue
        mid = r["fullname"]
        models.setdefault(mid, {"id": mid, "family": mid.split("/")[0], "params_b": r["#Params (B)"],
                                "kind": _kind(r["Type"]), "released": r.get("Upload To Hub Date") or ""})
        for col, (bench, shots, metric) in BENCHMARKS.items():
            raw = r.get(col)
            if raw is None:
                continue
            cells.append({"model": mid, "benchmark": bench,
                          "setting": {"protocol": PROTOCOL, "shots": shots, "metric": metric},
                          # full precision: rounding here AND at display shows 75.8 for 0.75852
                          "value": round(raw * 100, 10), "verbatim": repr(raw),
                          "locator": f"row eval_name={r['eval_name']}, column '{col}'"})
    return cells, sorted(models.values(), key=lambda m: m["id"])

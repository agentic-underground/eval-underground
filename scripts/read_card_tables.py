#!/usr/bin/env python3
"""One reading of a model card's benchmark table, by parsing it: the first of two blind readings.

    scripts/read_card_tables.py <card.md> <source-id> <model-prefix> > data/extractions/<source-id>/a.yaml

Reads the first HTML <table> after the "### Language" heading. Takes every numeric cell in a column
whose header starts with <model-prefix> (e.g. "Qwen3.5-"), as model "<org>/<header>" where the org is
the prefix's owner given as "Qwen/Qwen3.5-". A one-cell row is a group header; the mode is
"non-thinking" or "thinking" only where the table itself says so — a "Non-Thinking Mode" row, or a group
labelled "(Thinking)" — and "unstated" otherwise.

The second reading is made by eye, by someone who has not seen this one; `eval-underground agree`
compares them.
"""
import html
import re
import sys

import yaml


def text(cell):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", cell))).strip()


def read(card, prefix):
    org, _, head = prefix.partition("/")
    start = card.index("### Language")
    table = re.search(r"<table.*?</table>", card[start:], flags=re.S).group(0)
    rows = [[text(c) for c in re.findall(r"<t[dh][^>]*>.*?</t[dh]>", r, flags=re.S)]
            for r in re.findall(r"<tr.*?</tr>", table, flags=re.S)]
    header, cells, group, section_mode = rows[0], [], "", "unstated"
    wanted = [(i, h) for i, h in enumerate(header) if h.startswith(head)]
    for row in rows[1:]:
        if len(row) == 1:
            group = row[0]
            label = group.casefold().replace("）", ")")
            if "non-thinking mode" in label:
                section_mode = "non-thinking"
            elif "thinking mode" in label:
                section_mode = "thinking"
            continue
        label = group.casefold().replace("）", ")")
        mode = "non-thinking" if "(non-thinking" in label else "thinking" if "(thinking" in label else section_mode
        for i, h in wanted:
            v = row[i] if i < len(row) else ""
            if re.fullmatch(r"-?\d+(?:\.\d+)?", v):
                cells.append({"model": f"{org}/{h}", "benchmark": row[0], "mode": mode,
                              "value": float(v), "verbatim": v, "group": group})
    return cells


def main():
    card, source, prefix = sys.argv[1], sys.argv[2], sys.argv[3]
    cells = read(open(card, encoding="utf-8").read(), prefix)
    yaml.safe_dump({"source": source, "cells": cells}, sys.stdout, sort_keys=False, allow_unicode=True)


if __name__ == "__main__":
    main()

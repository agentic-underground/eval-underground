# eval-underground

**Where an open-weight model stands, from the scores already published for it.**

eval-underground collects the benchmark scores that leaderboards and model vendors have published for
open-weight model families, puts them in one matrix, and turns any slice of it into a mini
leaderboard you can drop into a blog post, a README or a paper. **Every number links to the source it
was read from**, with the exact row and column, and the verbatim value.

```console
$ eval-underground mini \
    --model Qwen/Qwen2.5-7B-Instruct --model meta-llama/Llama-3.1-8B-Instruct --model google/gemma-2-9b-it \
    --column "MMLU-Pro · Open LLM Leaderboard v2 · 5-shot · acc" \
    --column "IFEval · Open LLM Leaderboard v2 · 0-shot · strict acc (prompt+inst mean)" --out post/
post/mini.html   post/mini.md   post/mini.csv   post/mini.json
```

A column is one benchmark under one setting, so `--column MMLU-Pro` alone is refused when MMLU-Pro
has been published under several settings; the refusal lists each column's label to choose from.

| model | MMLU-Pro · Open LLM Leaderboard v2 · 5-shot · acc | IFEval · Open LLM Leaderboard v2 · 0-shot · strict acc (prompt+inst mean) |
|---|---:|---:|
| Qwen/Qwen2.5-7B-Instruct | 42.9 | 75.9 |
| meta-llama/Llama-3.1-8B-Instruct | 38.0 | 49.2 |
| google/gemma-2-9b-it | 38.8 | 74.4 |

`mini.html` is a self-contained fragment (its styles are scoped, and it follows light and dark mode):
paste it into a page, or open it on its own.

## Install

```console
$ git clone https://github.com/agentic-underground/eval-underground && cd eval-underground
$ uv sync                     # or: pip install -e .
$ uv run eval-underground matrix --out out/   # the whole matrix: out/index.html, .md, .csv, .json
```

`out/index.html` is one page with every model: hide benchmarks, narrow to one family or to base or
instruct models, and sort by any column (best first; press again to reverse).

The reviewed data ships in `data/`, so `matrix` and `mini` work offline. Re-importing a source needs
`pip install 'eval-underground[import]'` (pyarrow).

## What the matrix is

| element | what it is |
|---|---|
| **row** | one model: its Hugging Face id, family, parameters, base or instruct |
| **column** | one benchmark **under one setting**: protocol, shots, metric. `MMLU-Pro · 5-shot` and `MMLU-Pro · 0-shot` are two columns and are never compared |
| **cell** | a score on a 0–100 scale, with its source, locator and the verbatim value it was read from |

**The matrix is sparse on purpose.** An empty cell means nobody published that number under that
setting; it is never filled from a different setting.

**Conflicts are shown, never resolved silently.** When two reports of one cell differ (two
submissions of one model, or a model card against a leaderboard), the cell shows the preferred
source (paper › model card › leaderboard), is marked `±`, and lists every report.

## Sources

Every source has a record in [`data/sources/`](data/sources): URL, revision, the date it was
retrieved and the sha256 of the exact file. `eval-underground import` refuses a file whose sha256
does not match its record.

| source | what is taken |
|---|---|
| [Open LLM Leaderboard v2 archive](https://huggingface.co/datasets/open-llm-leaderboard/contents) (Hugging Face, revision `9c09a7c`) | rows marked *Official Providers* — each family's own releases, not community fine-tunes — and the six raw scores as percentages. Shots and metrics are the leaderboard's own statement of them, on its [About page](https://huggingface.co/docs/leaderboards/open_llm_leaderboard/about) |

| Qwen3.5 model cards (Qwen, Hugging Face), one record per card at a pinned revision: 0.8B, 2B, 4B, 9B, 27B, 35B-A3B, 122B-A10B, 397B-A17B | the *Language* benchmark table's Qwen3.5 columns. The mode (thinking / non-thinking) is recorded only where the table states it, so a card that does not say gets its own column rather than a guess |

**A score read from prose or a table is read twice, blind.** One reading parses the table
([`scripts/read_card_tables.py`](scripts/read_card_tables.py)); the other is made by eye by a reader
who has not seen the first. Both are kept in `data/extractions/<source>/`. `eval-underground agree
<source>` admits only the cells where the two match; anything else waits in `data/held/` for a person,
and never reaches the matrix. Parameter counts are Hugging Face's own (the safetensors total, which
for a vision-language model includes its vision tower).

The leaderboard archive's scores belong to its publishers; eval-underground re-presents them with
attribution and links back to every one.

## Development

```console
$ uv run --frozen playwright install chromium-headless-shell   # once per machine, for the page story
$ just check      # unit + story tests, offline, a few seconds
$ just hooks      # once per clone: every commit and push is swept for anything that should not be public
```

The story tests drive the real command (and, for the matrix page, a real headless browser) and check
what a person would see against the reviewed data, read by code that shares nothing with the renderer.
The gate runs uv with `--frozen`, so the lockfile is never re-resolved against a machine's own index.

## License

[MIT](LICENSE). Benchmark scores are facts published by their sources, cited per cell.

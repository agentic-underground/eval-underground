# The exit code is the verdict.

_default:
    @just --list

# is the arithmetic right?
unit:
    uv run --frozen --quiet pytest -q tests/unit

# can a person do the thing, end to end, with the real command and the real data?
story:
    uv run --frozen --quiet pytest -q tests/story

# the gate: every level that runs offline
check: unit story

# anything that should not be public, in the staged tree / in the whole history
sweep:
    python3 scripts/sweep.py

sweep-history:
    python3 scripts/sweep.py --history

# once per clone: point git at the sweep hooks
hooks:
    git config core.hooksPath .githooks

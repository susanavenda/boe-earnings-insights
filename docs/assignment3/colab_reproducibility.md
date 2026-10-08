# Assignment 3 notebook reproducibility

## Submission notebook

Use `notebooks/boe_earnings_insights.ipynb`. The repository is public and Stage 0 clones:

`https://github.com/susanavenda/boe-earnings-insights.git`

No GitHub token or other repository credential is required. Model API keys are optional and remain blank in the submitted path; the deterministic extractive pipeline runs without them.

**Install:** hosted notebook CI uses `uv sync --frozen --all-extras` from `uv.lock` (CPU torch on Linux). Lightweight tests use `uv sync --frozen --extra test`. Google Colab does not use uv — Stage 0 / pip-only machines still run `pip install -r requirements.txt`, which is exported from the lock. Do not hand-edit that file.

## Verified evidence

| Check | Evidence | Result |
|---|---|---|
| Public access | GitHub repository metadata checked on 8 October 2026 | `visibility: public` |
| Public shallow clone | Fresh destination, no local database, no GitHub credential | Pass |
| Full hosted clean run | GitHub Actions run `37339787866`, Ubuntu 24.04, Python 3.12, commit `63eb56f` | Pass in 2 h 29 min 11 s |
| Notebook cells | Workflow checks every code cell for missing execution counts or error outputs | 0 unrun, 0 errors |
| Tests after database build | `pytest tests/ -q -m "not slow"` inside the notebook workflow (that run used pip; current workflow is `uv run pytest` with the same args) | Pass |
| Submission tables | `scripts/export_tables.py` after the green run | 16 CSV/manifest files uploaded with the executed notebook |

The hosted run is strong reproducibility evidence, but it is not described as a Google Colab timing measurement. A final clean Colab Run All remains the one manual acceptance check for Issue #76.

## Clean Colab procedure

1. Open the notebook from the public GitHub repository in an incognito browser.
2. In Colab choose **Runtime → Disconnect and delete runtime**, then reconnect.
3. Leave every optional API-key environment variable unset.
4. Choose **Runtime → Run all**.
5. Record the start time, finish time, final Stage 4 KPIs and any failed cell.
6. Download the executed notebook as IPYNB and keep it with the final submission files.

Expected inputs are already committed: 148 transcript PDFs and 123 Excel packs. A fresh run therefore rebuilds `data/boe.sqlite`; it does not depend on a local or previously cached database.

## Time and fallback

Allow at least three hours. The clean GitHub Actions run took 2 h 29 min on an Ubuntu hosted runner, and free Colab capacity can be slower.

If Colab disconnects before completion:

1. Submit the latest green executed notebook as the reproducible IPYNB evidence.
2. Download the `executed-notebook` artifact from run `37339787866` before it expires on 19 October 2026, or from a later GitHub Release (`a3-final-<short-sha>`) created by a green notebook run on `main`.
3. Include its `data/exports/` CSV files in the submission bundle.
4. State clearly in the report that the recorded 2 h 29 min runtime is from GitHub Actions, not Colab.

This fallback preserves the executed cells and required CSV outputs while the public source notebook remains independently rerunnable from committed inputs.

## Final acceptance record

Complete after the manual Colab test:

| Field | Value |
|---|---|
| Date | `[enter date]` |
| Reviewer | Rafael Navas |
| Colab runtime type | `[enter value]` |
| Start–finish | `[enter times]` |
| Wall-clock runtime | `[enter duration]` |
| Result | `[pass / stopped at cell …]` |
| Executed notebook location | `[enter Drive/GitHub location]` |

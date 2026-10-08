# Data

| Path | Role |
|---|---|
| `raw/transcripts/` | **INPUT** — HSBC / Barclays Q&A PDFs, plus Credit Suisse 2020–2022 out-of-sample (Motley Fool / Roic reconstructions; protocol episode is Q4 2022 only) |
| `structured/` | **INPUT** — Excel data packs (HSBC, Barclays, CS 4-KPI sheets from SEC 6-K Exhibit 99.1) |
| `boe.sqlite` | **System of record** — notebook + scripts (gitignored) |
| `processed/` | **Internal** — scratch CSVs (`BOE_EXPORT_CSV=1` mirrors, `all_qa_pairs.csv`). Gitignored; not for citing or submission |
| `exports/` | **Submission tables** — headline tables as CSV plus `MANIFEST.md` (run ID, commit, headline figures). Tracked |

Rebuild the DB by running the notebook (Stage 0+) or product scripts under `scripts/`. See [`../docs/code.md`](../docs/code.md).

## Submission tables (`exports/`)

`scripts/export_tables.py` writes one CSV per headline table from `boe.sqlite` and a `MANIFEST.md` with the run and commit they came from. `qa_pairs.csv` is slim (pair_id, bank, quarter, source, analyst, question, answer) so the Assignment 3 submission includes the text; every other table drops question/answer text. The notebook workflow runs it after every clean run and uploads `data/exports/` with `executed.ipynb` in the `executed-notebook` artifact.

To publish those files as a GitHub Release (no download step): Actions → notebook → Run workflow, choose `main`, and set **release_tag** (for example `a3-final`). After a green run the workflow creates the release with the executed notebook, `MANIFEST.md`, and `data_exports.zip`. Leave the tag blank to skip.

Commit the CSVs **once**, from the artifact of the final green run, so the submitted files match the cited run. Don't edit them by hand; to refresh, re-export from a new green run and commit that artifact's `data/exports/` instead.

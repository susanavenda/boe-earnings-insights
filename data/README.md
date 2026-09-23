# Data

| Path | Role |
|---|---|
| `raw/transcripts/` | **INPUT** — HSBC / Barclays Q&A PDFs, plus Credit Suisse Q4 2022 out-of-sample |
| `structured/` | **INPUT** — Excel data packs (HSBC, Barclays, CS 4Q22 4-KPI sheet) |
| `boe.sqlite` | **System of record** — notebook + scripts (gitignored) |
| `processed/` | Unused placeholder (do not rely on CSVs here) |

Rebuild the DB by running the notebook (Stage 0+) or product scripts under `scripts/`.

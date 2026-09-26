# Data

| Path | Role |
|---|---|
| `raw/transcripts/` | **INPUT** — HSBC / Barclays Q&A PDFs, plus Credit Suisse 2020–2022 out-of-sample (Motley Fool / Roic reconstructions; protocol episode is Q4 2022 only) |
| `structured/` | **INPUT** — Excel data packs (HSBC, Barclays, CS 4-KPI sheets from SEC 6-K Exhibit 99.1) |
| `boe.sqlite` | **System of record** — notebook + scripts (gitignored) |
| `processed/` | Unused placeholder (do not rely on CSVs here) |

Rebuild the DB by running the notebook (Stage 0+) or product scripts under `scripts/`.

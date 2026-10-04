# Factory scripts

Notebook Stages 1–9 import these, or call them with `subprocess`. Do not delete a file because the notebook does not `import` it — several are **CLI extras** used off-notebook.

Full stage → table map: [`../docs/code.md`](../docs/code.md).

## Factory (imported or subprocess from the notebook)

| Script | Role | Typical command |
|---|---|---|
| `store.py` | SQLite system of record | `python scripts/store.py --list` |
| `periods.py` | `calendar_period` / peer window 2012–2025 | imported only |
| `segment_transcripts.py` | Per-bank speaker parse | imported only |
| `build_a1_evidence.py` | Manifest, Q&A pairs, M3 claims | `python scripts/build_a1_evidence.py` |
| `topic_modeling.py` | BERTopic / LDA helpers | imported only |
| `sentiment.py` | FinBERT + LDSA scoring | `python scripts/sentiment.py --qa --no-finbert` (lexicon only) |
| `score_qa_sentiment.py` | Thin `--qa` wrapper (loads FinBERT) | `python scripts/score_qa_sentiment.py --unit both` |
| `score_sentiment_human.py` | M4 gold scorer (`90` + `60` names) | `python scripts/score_sentiment_human.py` |
| `build_sentiment_gold_pack.py` | Build the 90-pair pack + 60 aliases | `python scripts/build_sentiment_gold_pack.py --reuse-m2a` |
| `build_metric_briefs.py` | Extractive four-KPI briefs | `python scripts/build_metric_briefs.py` |
| `build_supervisory_episode.py` | Protocol cases A1–A3 / N1 | `python scripts/build_supervisory_episode.py` |
| `generate_pra_note.py` | PRA one-pager (UTF-8) | `python scripts/generate_pra_note.py` |
| `compare_llm_sentiment.py` | Optional LLM vs FinBERT (skips without key) | `python scripts/compare_llm_sentiment.py --n 20` |
| `finetune_sentiment.py` | Light FT; promotion gate | GPU; not in CI coverage |
| `fetch_press_coverage.py` | Optional Yahoo attempt, **not a signal** | `python scripts/fetch_press_coverage.py` |
| `generate_synthetic_pra_log.py` | Stage 10 invented desk log | `python scripts/generate_synthetic_pra_log.py` |
| `score_m2a_human.py` | Aidan 8-way agreement | `python scripts/score_m2a_human.py` |
| `label_agreement.py` | Pitch export of M4 / FT numbers | `python scripts/label_agreement.py` |
| `build_qa_browser_export.py` | Flatten scored Q&A for the desk Browse tab | `python scripts/build_qa_browser_export.py` |
| `export_tables.py` | Headline tables → `data/exports/*.csv` + `MANIFEST.md` (run ID, commit) for submission | `python scripts/export_tables.py` |

Run from **repo root** so `ROOT = Path(__file__).parents[1]` finds `data/` and `docs/`.

Needs `data/boe.sqlite` already built (notebook Stage 0+ or a previous script run), except the pure helpers (`periods`, `segment_transcripts`, `topic_modeling`).

## CLI extras (keep)

| Script | Role |
|---|---|
| `download_cs_years.py` | Extra CS 2020–2022 calls + SEC 6-K 4-KPI packs |
| `ingest_credit_suisse.py` | Append CS to sqlite; rebuild episodes (protocol stays `cs_2022_q4` only) |
| `build_credit_suisse_inputs.py` | Transcript / pack cleanup used by the download script |
| `migrate_to_db.py` | One-shot `data/processed` → `data/boe.sqlite` |
| `generate_a2_outputs.py` | A2 charts from sqlite **without** a BERTopic re-fit |

## Contracts worth knowing

- **`store`:** `configure(memory=True)` in the notebook (auto-flush to disk). Scripts use `configure(memory=False)` and `BOE_DB`.
- **`periods.calendar_period`:** `interim`/`q2` → `H1`; `annual`/`q4`/`fy` → `FY`. Peer gap is `matched_peer_gap()`: HSBC−Barclays, 2012–2025, unpaired dropped, never `fillna(0)`.
- **`sentiment`:** scores a copy of the text; stored `text` / `question_text` / `answer_text` are never rewritten.
- **Gold filenames:** write `sentiment_90_labels_<name>.csv`. A mid-pass coder can still save `sentiment_60_labels_<name>.csv`; both globs count. `sample_60_*` is Aidan’s M2a pack (still n=60).

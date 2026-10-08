# Factory code map

How `notebooks/boe_earnings_insights.ipynb` and `scripts/` build the pack. Pitch language lives in [`assignment2/`](assignment2/); this page is for people changing code.

**Canonical notebook:** `notebooks/boe_earnings_insights.ipynb` (not a copy at repo root).

```text
IR PDFs + Excel
    → Stage 1 segment / Q&A pairs
    → Stage 2 topics
    → Stage 3 FinBERT + LDSA
    → Stage 4 extractive four-KPI briefs
    → Stage 6 peer + pack vs Q&A
    → Stage 8 alert / watch / null
    → Stage 9 PRA note
```

System of record is `data/boe.sqlite` (`scripts/store.py`). Files under `data/raw/` and `data/structured/` are **inputs only**.

## Invariants (do not silently change)

| Rule | Where it is enforced |
|---|---|
| Four KPIs only: total income, operating costs, credit impairment/ECL, CET1 | `build_metric_briefs.METRIC_KW`, episode briefs, tests |
| Sentiment labels: Positive / Negative / Neutral (avoidance is behaviour, not a FinBERT class) | `sentiment.LABELS`, Stage 3 tests |
| Protocol output is alert / watch / null — not a firm rating | `build_supervisory_episode.build_protocol` |
| Reviewed protocol cases are exactly HSBC 2025-H1, Barclays 2026-H1, CS 2022-Q4 | `EPISODES` |
| Same A1–A3/N1 gates may run on other bank-quarters as **unreviewed** | `corpus_quarter_specs` |
| Extra CS years stay in the corpus; they are not extra protocol proofs | `build_cs_quarter_trend` |
| Peer default window is 2012–2025 (`both_complete`); missing stays missing; gap is HSBC−Barclays via `matched_peer_gap` | `periods.in_peer_window` |
| FT promotion is human gold only; a silver-dev lift is circular, not a promote | Stage 3.4 vs 3.7; `finetune_sentiment.py` |
| Join HSBC `interim`/`annual` to Barclays `q2`/`fy` via `calendar_period` | `periods.calendar_period` |
| `event_type=other` (e.g. HSBC equity-analysts meeting) stays on disk; default analyses use `results_call` | `event_type_from_source` |
| Human gold files are not recoded by scripts | scorers read CSVs; they do not rewrite labels |
| Sentiment pack: canonical `sentiment_90_*`; `sentiment_60_*` aliases still scored | `score_sentiment_human.iter_coder_label_files` |

## Stage → code → sqlite

| Stage | Notebook | Script | Typical tables / docs |
|---|---|---|---|
| 0 | root, TF stub, `store.configure(memory=True)` | `store.py` | `data/boe.sqlite` |
| 1 | parse PDFs, filter `results_call` | `segment_transcripts.py`, `build_a1_evidence.py` | `all_turns`, `qa_pairs`, `corpus_manifest`, `corpus_coverage` |
| 2 | BERTopic on HSBC+Barclays, `transform` CS | `topic_modeling.py` | `corpus_analyst`, `bertopic_topic_info` |
| 3 | turn + sentence FinBERT, LDSA | `sentiment.py`, `score_qa_sentiment.py` | `qa_pairs` sentiment columns |
| 3.7 / M4 | human gold | `build_sentiment_gold_pack.py`, `score_sentiment_human.py` | `docs/assignment2/human_labels/sentiment_*` |
| 4 | extractive briefs | `build_metric_briefs.py` | `metric_briefs_faithful` |
| 6 | peer gap, pack vs Q&A | `periods.py` | `peer_matched`, `peer_gap` |
| 8 | protocol | `build_supervisory_episode.py` | `episodes_json`, `protocol`, `metric_briefs` |
| 9 | PRA one-pager + full-corpus Browse export | `generate_pra_note.py`, `build_qa_browser_export.py` | `pra_notes.md`, `qa_pairs_full` |
| 10 | extras, not a Q&A signal | `generate_synthetic_pra_log.py`, `fetch_press_coverage.py` | `pra_supervisor_log`, press tables |

Logical names (`corpus_analyst`, `qa_pairs`, …) are aliases in `store._TABLE_ALIASES`. Call `store.save_df` / `load_df` with the logical name.

## Run

```bash
# once from repo root — pins live in pyproject.toml / uv.lock
uv sync --all-extras          # factory + desk (torch, BERTopic, streamlit)
# uv sync --extra test        # lightweight pytest only (no torch)

# Factory (GPU/IR) — venv on
.venv/bin/python -c "import store; store.configure(); print(store.info())"

# Lightweight tests (CI) — no torch
uv run pytest tests/ -q -m "not slow" --cov=scripts --cov-config=.coveragerc

# Desk (this repo)
streamlit run demo/app.py
```

Coverage gate is **80% of factory scripts**. GPU and one-shot CLIs are omitted in `.coveragerc`. Map of files: [`../scripts/README.md`](../scripts/README.md). Tests: [`../tests/README.md`](../tests/README.md).

## Env (no config.yaml)

| Var | Role |
|---|---|
| `BOE_ROOT` / `COLAB_ROOT` | Factory root if cwd is not the repo |
| `BOE_DB` | SQLite path (default `data/boe.sqlite`) |
| `BOE_EXPORT_CSV=1` | Also write CSV mirrors under `data/processed/` |
| `BOE_USE_LLM_PREPROCESSING=1` | BERTopic may read `llm_preprocessed_text` |
| `BOE_LLM_PROVIDER` + API key | Optional Stage 3.1c; skip if unset |
| `PYTHONUTF8=1` | Windows: notebook cell before Stage 9.1 |

Keys stay in the process env or a gitignored `.env`. Never commit them.

## What not to delete

`download_cs_years.py`, `ingest_credit_suisse.py`, `build_credit_suisse_inputs.py`, `migrate_to_db.py`, and `generate_a2_outputs.py` are **CLI extras**. The notebook may not import them; they are still how extra CS years, sqlite migrate, and A2 charts without a BERTopic re-fit are run.

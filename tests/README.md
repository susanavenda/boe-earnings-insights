# Tests

Lightweight checks for the factory. They do **not** re-run BERTopic or FinBERT (those need GPU and live models). The notebook is read as JSON for stage-presence assertions.

```bash
# from repo root — no torch
uv sync --extra test
uv run pytest tests/ -q -m "not slow"
```

CI (`.github/workflows/ci.yml`) runs `uv sync --frozen --extra test` (pandas / numpy / scikit-learn / openpyxl + pytest; no torch) and the same command with coverage.

## Coverage

Factory gate is **80%** of `scripts/` after omitting GPU / one-shot CLIs (see `.coveragerc`).

```bash
uv run pytest tests/ -q -m "not slow" --cov=scripts --cov-config=.coveragerc --cov-report=term-missing
```

Omitted on purpose: `finetune_sentiment.py`, `score_qa_sentiment.py`, `download_cs_years.py`, `ingest_credit_suisse.py`, `build_credit_suisse_inputs.py`, `generate_a2_outputs.py`, `migrate_to_db.py`, `label_agreement.py`.

`@pytest.mark.slow` is the 45–90 min full notebook re-run (`test_stage2_topic_modeling.py`). Skip it in CI.

## Files

| File | Stage / topic |
|---|---|
| `conftest.py` | `pythonpath=scripts`; fixtures `nb`, `nb_code`, `nb_markdown` |
| `test_stage0_setup.py` | portable root, TF stub |
| `test_stage1_evidence.py` | parsers, Q&A pairs, `event_type` |
| `test_stage2_topic_modeling.py` | timestamps, min topic size; BERTopic marked slow / skip |
| `test_stage3_sentiment.py` | 3-class labels, gold globs `90` + `60` |
| `test_stage4_summaries.py` | four-KPI lock, extractive briefs |
| `test_stage5_refinement.py` | Stage 5 still reads `corpus_analyst` |
| `test_stage6_comparison.py` | peer window 2012–2025; numeric HSBC−Barclays gap |
| `test_stage7_status.py` | A1 readout cells |
| `test_stage8_protocol.py` | three protocol cases; CS extra years not extra cases |
| `test_stage9_publish.py` | UTF-8 before PRA notes |
| `test_stage10_extras.py` | synthetic log; press is not a signal |
| `test_periods.py` | `calendar_period` join |
| `test_store.py` | sqlite aliases, memory flush |
| `test_llm_skip.py` | Stage 3.1c no-ops without keys |
| `test_notebook_portability.py` | no machine-local paths |
| `test_pipeline_together.py` | KPI names + period join aligned across modules |
| `test_factory_helpers.py` | pure helpers (briefs, protocol, gold pack, LM lexicon) |
| `test_mains_coverage.py` | script `main()` against tmp sqlite / tmp dirs |

Do not recode human label CSVs in tests. Scorers may write agreement JSON under a **monkeypatched** output path only.

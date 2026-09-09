# Assignment 1 docs — what to use

| File | Role | Status |
|---|---|---|
| **`Group9_CAM_EP_Assignment1.pdf`** | **Submitted Assignment 1** (scope & plan) | Canonical — use this |
| **`Group9_CAM_EP_Assignment1.docx`** | Editable source of the submission | Same content as PDF |
| **`Assignment1_project_scope_and_plan.md`** | Markdown mirror of the submitted scope | Kept in sync with Group9 doc |
| **`BoE_Earnings_Insights_Report.md`** (+ `.docx`) | **Technical findings report** (pipeline results) | For A2/A3 — *not* the A1 submission |
| **`BoE_Earnings_Insights_Report_DRAFT.docx`** | Old PureGym-adapted shell | **Obsolete** — do not edit or submit |

## Assignment vs course map

| Course week | Focus | Our deliverable |
|---|---|---|
| Week 1 | Market research, roles, roadmap, Porter’s, plan | **A1** scope & plan (14 Sep) |
| Week 2 | Ideation & idea validation | Research Q + 3 baselines as hypotheses |
| Week 3 | Business communication / pitch | **A2** preliminary pitch (28 Sep) |
| GenAI Parts 1–2 | LLMs, instruction tuning, efficiency, RAG | FinBERT, light domain FT, LLM summaries |
| Weeks 5–6 | Value demo, final presentation | **A3** report + pitch (12 Oct); **A4** reflection (19 Oct) |

## Consistency rules

1. **Banks:** HSBC + Barclays only (third US bank undecided / stretch).
2. **Team:** 7 members — Aidan, Alfred, Bupathi, Debanjan, Rafael, Susana Venda, Taz.
3. **Response norm:** 24-hour weekday (not 48-hour).
4. **Out of scope:** video; **fine-tuning from scratch**; peers beyond HSBC/Barclays.
5. **Light domain adaptation** of FinBERT (classifier head / last layers) is allowed as stretch and must be labelled as *not* training from scratch.
6. **Summariser:** A1 planned metric-grouped LLM summaries; current notebook uses DistilBART with Phi-4 as A3 upgrade.
7. **Baselines:** temporal · peer · structured-vs-unstructured.

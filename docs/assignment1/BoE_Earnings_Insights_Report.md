# Technical Report — Earnings Call Analysis for the Bank of England

**NLP topic modelling, financial sentiment analysis, and LLM-assisted summarisation across HSBC and Barclays earnings-call transcripts**

> **Not Assignment 1.** A1 (scope & plan) is `Group9_CAM_EP_Assignment1.pdf`. This document is the **findings / methods write-up** for A2–A3, aligned to that scope.

Cambridge Data Science Career Accelerator · Group 9 · 2026

| | |
|---|---|
| Banks | HSBC · Barclays (per A1; no third bank yet) |
| Team | Aidan, Alfred, Bupathi, Debanjan, Rafael, Susana Venda, Taz |
| Methods | BERTopic · Gensim LDA · FinBERT + LDSA · DistilBART summarisation (Phi-4 upgrade planned for A3) |
| Status | Pipeline executed on live corpus |
| Notebook | `notebooks/boe_earnings_insights.ipynb` |
| Word version | `BoE_Earnings_Insights_Report.docx` |
| A1 scope | `Group9_CAM_EP_Assignment1.pdf` |

Adapted from: Venda_Susana_CAM_C301 Week 4&5 Topic project (PureGym).

---

## Executive summary

### Business context

The Bank of England's Prudential Regulation Authority needs earlier warning of prudential stress than structured regulatory returns alone provide. This report applies topic modelling, financial sentiment analysis, and LLM-assisted summarisation to HSBC and Barclays earnings-call transcripts to test whether analyst Q&A carries a leading signal not visible in reported metrics alone.

### Findings

- **Corpus:** 13 transcript PDFs → **118 analyst Q&A turns** (HSBC 71, Barclays 47) across 2025–2026 reporting labels; 12 Excel packs for structured comparison.
- **Topic × period:** FinBERT net heatmaps by topic×quarter×bank (`sentiment_topic_quarter.csv`) answer how theme tone shifts across prints.
- **Topics:** Dominant BERTopic themes — (0) growth / US / franchise; (1) **costs and forward-looking questions**; (2) wealth management (HSBC-tilted). Topic 1 has the highest FinBERT negative share (**10%**).
- **Sentiment:** FinBERT is heavily **neutral (90%)** — consistent with hedged bank Q&A. LDSA lexicon is less neutral and agrees with FinBERT on **58%** of turns.
- **Structured vs unstructured:** Among **31** overlapping bank×quarter×metric observations, narrative tone and reported metric direction **disagree 74%** of the time. Credit impairment shows **0% agreement** on this sample. Treat as a preliminary divergence signal: FinBERT’s neutral bias compresses many narrative scores toward “flat”.

### Recommendation

Prioritise Topic 1 (cost / forward questions) and credit-impairment narrative for supervisory monitoring; expand matched-quarter coverage and hand-validate FinBERT negatives before treating divergence rates as operational alerts.

---

## 1. Introduction

**KPI snapshot:** Banks: 2 · Transcript PDFs: 13 · Analyst turns: 118 · Excel packs: 12 · Methods: BERTopic, LDA, FinBERT+LDSA, DistilBART, refined BERTopic.

HSBC and Barclays are UK-incorporated G-SIBs under full PRA oversight. The project segments analyst vs management turns, models themes and sentiment, summarises by prudential metric, and evaluates against temporal, peer, and structured-vs-unstructured baselines.

---

## 2. Data & methodology

### 2.1 Dataset overview

| Field | Detail |
|---|---|
| Sources | HSBC IR · Barclays IR |
| Transcripts | 13 PDFs under `data/raw/transcripts/` |
| Structured packs | 12 Excel files under `data/structured/` |
| Modelling corpus | 118 analyst turns after segmentation + cleaning |
| HSBC / Barclays | 71 / 47 analyst turns |
| Preprocessing | Lowercase · stopwords · number removal · NLTK tokenisation |

### 2.2 Methods

| Method | Purpose |
|---|---|
| BERTopic | Topic discovery on analyst Q&A |
| Gensim LDA | Independent topic cross-check |
| FinBERT | Financial-domain sentiment per turn |
| LDSA (lexicon) | Second sentiment signal |
| DistilBART | Metric-level summarisation sample (Phi-4 optional upgrade) |
| Refined BERTopic | Second pass on negative-leaning clusters |

---

## 3. Topic modelling — BERTopic

| Topic | Count | Name (abbrev.) |
|---|---|---|
| −1 | 25 | outliers |
| 0 | 51 | think / growth / us |
| 1 | 30 | question / costs / cost / year |
| 2 | 12 | wealth / management / hsbc |

**Interpretation:** Topic 0 dominates franchise/growth language. Topic 1 is the clearest cost / questioning cluster. Topic 2 is wealth-management oriented. Focused re-clustering on elevated-negative topics recovered wealth and cost/question sub-themes (`data/processed/refined_topic_info.csv`).

**Coherence (c_v):** BERTopic **0.48** vs LDA **0.35** on the same analyst corpus (`topic_coherence.csv`). Soft prints cross-checked against known results windows in `known_events_crosscheck.csv` (HSBC 2025-interim; Barclays 2026-q2).

---

## 4. Sentiment — FinBERT + LDSA

| Model | Neutral | Negative | Positive |
|---|---|---|---|
| FinBERT (zero-shot) | 106 (90%) | 7 (6%) | 5 (4%) |
| LDSA | 70 (59%) | 14 (12%) | 34 (29%) |

**By topic (FinBERT share):**

| Topic | Negative | Neutral | Positive |
|---|---|---|---|
| −1 | 8% | 88% | 4% |
| 0 | 2% | 90% | 8% |
| 1 | **10%** | 90% | 0% |
| 2 | 8% | 92% | 0% |

Limitation: FinBERT neutrality on hedged Q&A keeps net scores small. Hand-validation sample: `docs/hand_validation_sample.csv`.

### 4.1 Light domain fine-tune (worked example)

**Scope note (A1):** “Fine-tuning from scratch” is out of scope. This section is a **light domain adaptation** of existing FinBERT (frozen encoder → train head; then last two layers) — not training a new model from scratch.

To close the brief gap on model adaptation, we built **118 silver labels** on analyst turns (FinBERT∩LDSA agreement, high-confidence FinBERT non-neutral, LDSA signal, keyword override; 20 rows flagged from the hand-validation sample) and lightly adapted `ProsusAI/finbert`:

1. Freeze encoder; train classification head (8 epochs, lr 5e−4)  
2. Unfreeze last two encoder layers + head (4 epochs, lr 2e−5)  
3. Class-weighted cross-entropy; stratified 75/25 split (88 train / 30 test)

| Model | Accuracy | Macro-F1 | Weighted-F1 |
|---|---|---|---|
| Zero-shot FinBERT | 60% | **0.433** | 0.488 |
| Domain fine-tuned | 63% | **0.642** | 0.630 |

**Finding:** Zero-shot FinBERT almost never predicts *positive* on this held-out set (positive F1 = 0); the light fine-tune recovers positive recall and lifts macro-F1 by ~0.21. Trade-off: more neutral→positive shifts (inspect confusion in `data/processed/finetune_confusion.png`). Labels remain partly silver — enlarge pure human review before treating FT scores as production alerts.

Artifacts: `scripts/finetune_sentiment.py`, `data/processed/finetune_metrics.json`, `models/finbert-domain-ft/`, notebook Stage 3.4.

---

## 5. LLM-assisted summarisation

Sample: 8 turns × 4 metrics (total income, operating costs, credit impairment, CET1) via DistilBART-CNN with extractive keyword fallback (`data/processed/summary_sample.csv`). Quality is mixed (prompt echo common). For Assignment 3, upgrade to Phi-4-mini-instruct or a finance-tuned model and raise sample size.

---

## 6. Evaluation — three baselines

### 6.1 Temporal (overall FinBERT net by quarter)

| Bank | Softest / notable print |
|---|---|
| Barclays | 2026-q2 net −0.11 |
| HSBC | 2025-interim net −0.13 |

Short series → rolling z-score changepoints are indicative only.

### 6.2 Peer gap

Raw labels mismatched (HSBC `interim` vs Barclays `q2`). After mapping interim↔q2 as H1 (and aligning q1/q3/FY), **6 calendar periods** have both banks (`peer_matched_quarters.csv`). Softest matched gap: **2025-H1** (HSBC − Barclays ≈ −0.13).

### 6.3 Structured vs unstructured

Keyword-tagged narrative vs Excel-reported directions (CET1, income, costs, impairment):

| Metric | Agreement | n |
|---|---|---|
| cet1_ratio | 38% | 8 |
| credit_impairment | **0%** | 7 |
| operating_costs | 25% | 8 |
| total_income | 38% | 8 |

**Overall divergence: 74%** on 31 overlaps. Credit impairment never agrees on this sample — narrative often flat while the reported charge moves. Hypothesis for qualitative review, not an automated alert.

### 6.4 Method comparison

| Method | Strength |
|---|---|
| BERTopic | Interpretable themes |
| LDA | Fast sanity check |
| FinBERT (zero-shot) | Domain sentiment (hedging-limited) |
| FinBERT (domain FT) | Macro-F1 0.43 → 0.64 on held-out Q&A |
| LDSA | Transparent second signal |
| DistilBART | Exploratory summaries |
| Struct vs unstruct | Directly addresses the BoE research question |

---



## 6.5 Supervisory episode (HSBC 2025-H1)

Concrete case study for Assignment 2 pitch (`docs/assignment2/A2_pitch_outline.md`):

- Softest Q&A print: **HSBC 2025-interim** (FinBERT net ≈ **−0.13**); Topic 1 = 5/8 turns (40% negative).
- Matched **2025-H1**: HSBC −0.13 (n=8) vs Barclays **0.00** (n=6, all FinBERT-neutral). Gap equals HSBC’s net → **not A2-eligible** (peer quality gate).
- Claim-vs-source vs **2025-q2** pack: Q&A tone **agrees** with reported directions → **A3 WATCH**.
- Missing Q&A metric hits now score **n/a**, not agreement. Verdicts: `supervisory_episodes.json`.

**Pipelines** (ingest → topics → sentiment → baselines → decision → PRA note): `docs/assignment2/pipelines.md`.

**Stage 9:** Second episode **Barclays 2026-q2** = WATCH (A3); dual PRA notes in `docs/assignment2/pra_notes/`; extractive metric briefs in `metric_briefs_faithful.csv`; re-run checklist `docs/assignment2/rerun_checklist.md`.

## 7. Recommendations

| # | Recommendation | Evidence |
|---|---|---|
| 1 | Monitor Topic 1 + FinBERT negatives each quarter | Clearest negative cluster |
| 2 | Investigate credit-impairment narrative vs reported ECL | 0% agreement on sample |
| 3 | Expand matched-quarter peer coverage | Required for peer baseline |
| 4 | Enlarge human review of silver labels; re-FT | FT worked; labels still partly automatic |
| 5 | Upgrade summariser before Assignment 3 | Current summaries noisy |

---

## 8. Limitations & next steps

**Limitations:** Small corpus (118 turns); FinBERT neutrality (partly mitigated by §4.1 fine-tune); silver-label noise; DistilBART quality; quarter-label mismatch; lexicon LDSA; speaker-segmentation edge cases.

**Next:** Assignment 2 pitch (28 Sep) — Topic 1 / impairment divergence, matched peer gaps, light FT vs zero-shot, PRA readout. Assignment 3 (12 Oct) — Phi-4 (or stronger) summariser, richer metric tagging, event-linked case studies, final report + presentation. Assignment 4 (19 Oct) — individual reflection.

---

## Appendix — Reproducibility

- Repo: https://github.com/susanavenda/boe-earnings-insights  
- Notebook: `notebooks/boe_earnings_insights.ipynb`  
- Kernel: Python 3.12 (BoE Earnings) · `requirements.txt`  
- Fine-tune: `scripts/finetune_sentiment.py` · metrics `data/processed/finetune_metrics.json`  
- Outputs: `data/processed/*.csv` · `docs/hand_validation_sample.csv`  
- Local model weights: `models/finbert-domain-ft/` (gitignored; rebuild via script)

# Pipelines we use (and why)

One page so the team pitches **products**, not a model list.

| Pipeline | Job | Where | Status |
|---|---|---|---|
| **1. Ingest & segment** | PDFs → analyst turns; Excel → reported metrics | Notebook Stage 1 · `corpus_analyst.csv` · `reported_metrics.csv` | Live |
| **2. Topic discovery** | Themes in Q&A (BERTopic + LDA + c_v) | Stages 2 / 2.4 / 5 | Live |
| **3. Sentiment** | Tone per turn / topic (FinBERT + LDSA) | Stage 3 | Live |
| **3b. Light domain adapt** | Adapt FinBERT head (not from-scratch) | Stage 3.4 · `scripts/finetune_sentiment.py` | Live (stretch vs A1) |
| **4. Metric summarisation** | Short briefs by prudential metric | Stage 4 (DistilBART; Phi-4 = A3) | Sample |
| **5. Evaluation baselines** | Temporal · matched peer · struct↔unstruct | Stage 6 | Live |
| **6. Supervisory decision** | Alert / watch / null + episode case study | Stage 8 · `alert_null_protocol.csv` | Live |
| **7. Re-run ops** | Next-quarter cost & checklist | Stage 7.0 | Live |
| **8. PRA one-pager + dual episodes** | Alert/watch/null → printable note | Stage 9 · `pra_notes/` | Live |
| **9. Faithful metric briefs** | Extractive briefs + overlap score | `metric_briefs_faithful.csv` | Live |
| **10. RAG “ask the transcript”** (optional) | Supervisor Q→chunked Q&A evidence | Not built | A3 stretch |

## How they connect

```text
IR PDFs + Excel
    → segment & clean
    → topics + sentiment (+ optional FT)
    → metric tags / summaries
    → three baselines
    → episode + alert/null rules
    → PRA one-pager (+ second episode)
    → pitch / PRA readout
```

## What not to reopen
- Video/webcast processing  
- Training models from scratch  
- Extra banks before the episode story is tight

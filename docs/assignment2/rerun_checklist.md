# Next-quarter re-run checklist

**Goal:** Reproduce the pipeline and PRA note when new IR packs land.  
**Target cost:** ~45–90 minutes (data drop-in assumed).

## 1. Ingest (10–20 min)
- [ ] Download new HSBC / Barclays transcript PDFs → `data/raw/transcripts/{bank}/`
- [ ] Download Excel data packs → `data/structured/{bank}/`
- [ ] Name files consistently (`YYYY-qN-…` / interim / annual)

## 2. Environment (2 min)
```bash
cd Boe_Earnings_Insights_Workspace
source .venv/bin/activate   # or select kernel: Python 3.12 (BoE Earnings)
```

## 3. Notebook (30–50 min)
- [ ] Run Stages **0 → 7** (or Restart & Run All)
- [ ] Confirm `data/processed/corpus_analyst.csv` grew
- [ ] Spot-check Stage 6 matched peer + struct↔unstruct

## 4. Episodes + PRA notes (5–10 min)
```bash
.venv/bin/python scripts/build_supervisory_episode.py
.venv/bin/python scripts/generate_pra_note.py
.venv/bin/python scripts/build_metric_briefs.py
```
- [ ] Open `docs/assignment2/pra_notes/pra_notes_pack.md`
- [ ] File alert / watch / null per protocol

## 5. Human QA (15–30 min)
- [ ] Review 20–40 turns in `docs/hand_validation_sample.csv`
- [ ] If labels grew materially: optional `scripts/finetune_sentiment.py`

## Out of scope each quarter
- Retrain from scratch · video · new banks (unless scope changes)

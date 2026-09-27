# PRA Earnings Desk (this repo)

Output surface for the factory pack. The [A2 slides](https://docs.google.com/presentation/d/1p9LD9KQ2COHz-7NIoFRXdVXlPDQvf7AFsKIBYP0wMTk/edit) make the claims; this desk is the live proof.

```bash
cd /path/to/boe-earnings-insights
source .venv/bin/activate
streamlit run demo/app.py
# → http://localhost:8501
```

First open copies `data/boe.sqlite` → `demo/data/desk.sqlite`.

## After the slides, open this

1. Inbox **WATCH · HSBC 2025-H1** (paired quarter). 2026 is in progress; CS is deferred to A3. **Browse** is a second tab for any scored Q&A pair — not extra protocol cases.
2. **Pack vs Q&A** — four KPIs with PRA codes P03 / P03 / P04 / P01 (taxonomy built before reading transcripts).
3. **How they answered** — directness, coverage, substitution. Avoidance is not a FinBERT class (`scripts/build_a1_evidence.py`).
4. **Protocol A3** — soft + packs agree → WATCH, not a peer ALERT.
5. **Peer** — 2012–2025, `calendar_period()` join, never `fillna(0)`.
6. **Ops** — FT gates, 90 M4 pairs, zero-shot stays, not promoted. Silver-dev lift is circular; human gold is the gate.

Alert / watch / null is protocol, not a firm rating.

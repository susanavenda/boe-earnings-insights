# Synthetic PRA desk log (extra source)

**Not IR. Not a Bank of England record. Not used by Stages 1–9.**

Invented supervisor workflow so the factory can show an audit-trail table without mixing fake numbers into transcripts, Excel packs, FinBERT, BERTopic, or Rafael’s Stage 4 briefs.

| File | What |
|---|---|
| `pra_supervisor_log.csv` | Six desk actions around HSBC 2025-H1 WATCH and the Barclays matched-peer **null** |
| Rebuild | `python scripts/generate_synthetic_pra_log.py` |

Every row has `is_synthetic=1` and a disclaimer column. Do not join this table into peer-gap or four-line Excel logic.

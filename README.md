# BoE earnings insights — Group 9

Cambridge Data Science Career Accelerator — employer project with the Bank of England.

**Sell:** an **automation pipeline** that turns IR PDFs + Excel into a versioned **alert / watch / null** supervisory pack (desk UI = output surface; notebook/scripts = factory).

- [Assignment 1 Google Doc](https://docs.google.com/document/d/10211H1XyqjrHAKa_ikN5uuYuyTPrDPteUXeQl-QJJlY/edit?usp=drive_link)
- [HSBC investor results](https://www.hsbc.com/investors/results-and-announcements)
- [Barclays financial results](https://home.barclays/investor-relations/reports-and-events/financial-results/)

## Overarching question

Do quarterly earnings announcements and analyst Q&A carry a leading signal about
a firm's prudential condition that reported financial metrics alone don't capture?

## How the open tabs fit together

| Piece | Role |
|---|---|
| **Pipeline** (this repo) | Factory — notebook + `scripts/` → `data/boe.sqlite` |
| **Demo** (`../boe-earnings-demo`) | PRA Earnings Desk — presents the frozen pack |
| **A2 pitch** | [`docs/assignment2/A2_pitch_outline.md`](docs/assignment2/A2_pitch_outline.md) — 15‑min Background → Approach → Conclusion |
| **Technical report** | [`docs/assignment1/BoE_Earnings_Insights_Report.md`](docs/assignment1/BoE_Earnings_Insights_Report.md) |
| **A1 scope** | [`docs/assignment1/Group9_CAM_EP_Assignment1.pdf`](docs/assignment1/Group9_CAM_EP_Assignment1.pdf) |

Open both folders via [`Boe_Earnings.code-workspace`](Boe_Earnings.code-workspace).

**Proof episode:** HSBC 2025-interim (H1) → **WATCH (A3)** — soft Q&A, packs agree; peer gap not ALERT (Barclays matched print all-neutral).

## Scope

| | |
|---|---|
| Banks | HSBC and Barclays — UK-incorporated, full PRA oversight, complete public Q&A transcripts |
| Excluded | US banks, Santander — different regulatory regimes, less comparable data |
| Open question | A third US-based bank for geopolitical comparison — undecided, live in group chat |
| In scope | BERTopic topic clustering, FinBERT + LDSA sentiment, summarisation by metric, refined topic modelling on key clusters |
| Out of scope | Video/webcast processing, fine-tuning from scratch, peer benchmarking beyond HSBC/Barclays (stretch goal only) |

## Team

| Name | Role | Belbin |
|---|---|---|
| Taz | Coordinator | Coordinator / Implementer |
| Alfred | Sentiment lead (FinBERT + LDSA) | Specialist / Plant / Shaper |
| Susana Venda | Topic modelling lead (BERTopic) | — |
| Aidan | Pending | — |
| Bupathi | Pending | — |
| Debanjan | Pending | — |
| Rafael | Data Pipeline and Integration Lead| Specialist |

## Where things live

| Job | Place |
|---|---|
| Analysis (factory) | [`notebooks/boe_earnings_insights.ipynb`](notebooks/boe_earnings_insights.ipynb) |
| Product desk (Demo) | Sibling [`boe-earnings-demo`](../boe-earnings-demo) → `streamlit run app.py` |
| A1 submission | [`docs/assignment1/Group9_CAM_EP_Assignment1.pdf`](docs/assignment1/Group9_CAM_EP_Assignment1.pdf) |
| Technical findings | [`docs/assignment1/BoE_Earnings_Insights_Report.md`](docs/assignment1/BoE_Earnings_Insights_Report.md) |
| A2 pitch + checklist | [`docs/assignment2/`](docs/assignment2/) |
| Tasks / roadmap | [GitHub Project](https://github.com/users/susanavenda/projects/3/views/2) |
| Shared write-up | [Assignment 1 Google Doc](https://docs.google.com/document/d/10211H1XyqjrHAKa_ikN5uuYuyTPrDPteUXeQl-QJJlY/edit?usp=sharing) |

**Rule of thumb:** Notebook/scripts = build the pack · Demo = show the pack · A2 PDF+MP4 = sell the pipeline · Google Doc = team comments.

## Repository structure

```
├── README.md
├── requirements.txt
├── notebooks/boe_earnings_insights.ipynb
├── data/
│   ├── raw/transcripts/       # INPUT — Q&A PDFs
│   ├── structured/            # INPUT — Excel packs
│   ├── boe.sqlite             # system of record (gitignored; rebuild via notebook/scripts)
│   └── processed/             # empty placeholder (legacy CSVs removed)
├── docs/
│   ├── assignment1/           # A1 PDF/DOCX + technical report
│   ├── assignment2/           # pitch, PRA notes, re-run guide
│   ├── project/issues.csv
│   ├── assets/
│   └── hand_validation_sample.csv  # INPUT — human labels
└── scripts/                   # store + episode / PRA / FT helpers
```

## Milestones

| Assignment | Due date |
|---|---|
| A1 — Scope & plan | 14 Sep |
| A2 — Solution pitch | 28 Sep |
| A3 — Final report | 12 Oct |
| A4 — Reflection | 19 Oct |

## Roadmap

<img width="2579" height="1099" alt="roadmap" src="docs/assets/roadmap.png" />

Five life-cycle phases: Initiation (7 Sep) → Planning (8–14 Sep) → Execution,
split into Solution dev (15–28 Sep) and Final report (29 Sep–12 Oct) → Closure
(13–19 Oct). Monitoring & control runs throughout via weekly checkpoints against
this roadmap.

## Evaluation approach

No baseline was defined by the Bank, so the team is resolving it directly, three ways:

- **Temporal** — the same firm across successive quarters
- **Peer** — HSBC vs. Barclays, same quarters
- **Structured vs. unstructured** — reported financial metrics against the tone
  and topic mix of the narrative discussing them

Divergence on any axis is a valid finding. A null result — no divergence — is a
valid, reportable outcome, not a failure of the analysis. Model outputs are
hand-validated on a sample rather than trusted on metric alone, and FinBERT's
known weakness on hedged, heavily-lawyered bank language is reported explicitly.

## Setup

```bash
git clone https://github.com/susanavenda/boe-earnings-insights.git
cd boe-earnings-insights
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Open `notebooks/boe_earnings_insights.ipynb` and run from Stage 0.

**Data store:** notebook keeps an **in-memory SQLite** working set that auto-flushes to
**`data/boe.sqlite`** (shared with Pipeline scripts).  
**Inputs** are files only (`data/raw/transcripts/`, `data/structured/`, hand-label CSV).  
Optional CSV/PNG mirrors: `BOE_EXPORT_CSV=1`.  
One-shot import of legacy files: `.venv/bin/python scripts/migrate_to_db.py`.

Next-quarter ops / Demo desk: sibling `boe-earnings-demo` → [`docs/assignment2/README.md`](docs/assignment2/README.md).

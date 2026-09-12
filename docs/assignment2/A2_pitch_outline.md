# Assignment 2 — Pitch: sell the automation pipeline

**Group 9 · BoE employer project · Due Mon 28 Sep 2026 17:00 UK**  
**Submit:** `Group9_CAM_EP_Assignment2_slides.pdf` + `Group9_CAM_EP_Assignment2_presentation.mp4` (15 min ±10%)

### Sell line (memorise)
> We turn messy earnings Q&A into a **versioned alert / watch / null pack** a PRA desk can re-run next quarter in **under two hours** — automation with brakes, not a black-box chatbot.

### What you’re selling
```text
IR PDFs + Excel
  → segment analyst turns
  → topics + sentiment
  → baselines (temporal · peer · struct↔Q&A)
  → rules → episode verdict
  → PRA one-pager + desk UI
```

**Automation** = scripted / notebook chain, re-runnable.  
**Human** = grow labels, promote model, accept or reject the alert.  
**Demo desk** = output surface of the pipeline (not the product story alone).

---

## 15-minute run-of-show (Canvas 3-block structure)

| Block | Time | Job |
|---|---|---|
| **1. Background** | 0:00–3:00 | Client context + business question |
| **2. Approach** | 3:00–12:00 | Pipeline · models · eval · episode · desk/notebook walkthrough |
| **3. Conclusion** | 12:00–15:00 | Findings · workflow fit · obstacles · ask |

---

### BLOCK 1 — Background (~3 min)

#### Slide 1 — Title / hook (30s)
**Title:** Supervisory earnings pipeline — early warning from Q&A  
**Subtitle:** Group 9 · Bank of England employer project  
**On slide:** sell line + KPI strip — 118 analyst turns · HSBC + Barclays · 3 baselines · dual episodes  

**Say:** “We’re not pitching another sentiment model. We’re pitching a **repeatable supervisory pipeline** that ends in alert, watch, or null.”

#### Slide 2 — Client problem (90s)
- PRA already sees **structured returns** clearly  
- Earnings **Q&A is messy, hedged, hard to scan every quarter**  
- **Business question:** Does narrative carry a leading signal metrics alone miss?  
- **Audience:** supervisors / desk analysts who need evidence, not a chatbot  

**Say:** “Our bet: yes — when theme tone and reported direction **diverge**. When they **agree** but tone is soft, that’s **WATCH**, not noise.”

#### Slide 3 — Scope (60s)
| In | Out |
|---|---|
| HSBC + Barclays (UK PRA perimeter) | Video / webcast |
| Public transcripts + Excel packs | Train from scratch |
| Alert / watch / null + PRA pack | Extra banks before the episode story is tight |

---

### BLOCK 2 — Approach (~9 min)

#### Slide 4 — The automation pipeline (90s) ★ centrepiece
One left→right diagram (big boxes, few words):

1. **Ingest** — PDFs + Excel  
2. **Prepare** — clean, segment analyst vs management  
3. **Model** — BERTopic (+ LDA / c_v) · FinBERT + LDSA (+ light domain FT)  
4. **Evaluate** — temporal · matched peer · struct↔Q&A  
5. **Decide** — protocol → episode  
6. **Publish** — PRA note + desk (`desk.sqlite`)

**Footer:** Next-quarter re-run **45–90 min** when new IR files land.

**Say:** “Every arrow is automated enough to re-run. Recalibration is **gated** — we do **not** retrain on every PDF drop-in.”

#### Slide 5 — Data preparation (60s) ← rubric
- **Gather:** IR PDFs under `data/raw/transcripts/`; Excel packs under `data/structured/`  
- **Clean / format:** pdfplumber extract → speaker regex (HSBC / Barclays patterns) → analyst-only corpus  
- **Represent:** `clean_text` for topics; raw text for FinBERT; metrics table from Excel  
- **Store:** intermediates in `data/boe.sqlite` (files = inputs only)  

**Say:** “Preprocessing is justified for **messy transcript text**, not tabular Kaggle defaults.”

#### Slide 6 — Method choice & why (75s) ← rubric
| Choice | Why it fits this domain |
|---|---|
| **BERTopic** | Themes emerge from Q&A; we don’t force a fixed taxonomy day one |
| **LDA + c_v** | Independent sanity check on clusters |
| **FinBERT** | Finance-domain sentiment prior |
| **LDSA** | Lexicon cross-check when transformers over-neutralise hedges |
| **Light FT** | Domain adapt only when human labels grow — promote if hold-out doesn’t regress |
| **Rules protocol** | Supervisors need **reproducible** alert/watch/null, not opaque scores |

#### Slide 7 — Evaluation, fine-tune, verification (90s) ← rubric
- **Baselines:** temporal shift · matched peer gap · structured vs unstructured direction  
- **Hand sample:** 50-row review queue; 20 flagged reviewed — FinBERT ≈ **50%** vs sample gold (honest limit)  
- **FT:** silver + reviewed labels; candidate model, **promote only** if macro-F1 gate passes  
- **Manual verify:** quote cards + struct↔Q&A agree column on the episode  

**Say:** “We treat FinBERT neutrality as a **risk**, not a feature — that’s why peer gap alone cannot fire ALERT when Barclays is all-neutral.”

#### Slide 8 — Episode proof: HSBC H1 2025 (90s)
- Softest print in sample (FinBERT net ≈ **−0.13**); Topic 1 (costs / forward) drives softness  
- Packs **agree** on direction → **WATCH (A3)**  
- Matched peer: Barclays **0.00** (n=6, all FinBERT-neutral) → gap looks scary, **not A2-eligible**  
- **Quote:** one impairment / tariffs analyst turn  

**Say:** “This is the pipeline output: a governed verdict with evidence, not a leaderboard score.”

#### Slide 9 — Live walkthrough (2 min) ← “Notebook + solution”
**Part A — Desk (product):** http://localhost:8501  
Episodes (HSBC) → Evidence → Peer & protocol → PRA download  

**Part B — Notebook (technical):** Stages 1 → 2/3 → 6 → 8/9 — point at cells, don’t scroll-read.

**Say:** “Desk is what the supervisor opens. Notebook + scripts are the factory.”

---

### BLOCK 3 — Conclusion (~3 min)

#### Slide 10 — Findings (60s)
1. Narrative **can** flag soft quarters metrics alone don’t prioritise  
2. Soft + packs agree → **WATCH**; soft + packs disagree → path to **ALERT**  
3. Naive peer gaps are dangerous when one side is model-flat  
4. **Null is allowed** and reportable  

#### Slide 11 — Integration & obstacles (60s) ← rubric
**Fit:** overnight / quarterly job → versioned pack → desk or PRA one-pager  

**Obstacles:**
- Hedged language → transformer over-neutral  
- Small N / flat peers break gap rules  
- Labels are scarce — don’t automate promotion  
- Change management: supervisors must trust **rules + evidence**, not model mystique  

#### Slide 12 — Ask / close (45s)
**For BoE:** Is alert / watch / null the right product shape for the desk?  
**For markers:** Depth on two G-SIBs + a **repeatable pipeline** beats breadth.  
**Next (A3):** more true human labels · promote FT only if gates pass · optional RAG  

**Close with sell line again.**

---

## Role split (example)

| Person | Owns |
|---|---|
| A | Slides 1–3 Background |
| B | Slides 4–7 Pipeline / methods / eval |
| C | Slide 8 episode + desk walkthrough |
| D | Notebook walkthrough + Slide 11–12 close |

Adjust to your group size; everyone must know the sell line.

---

## Speaker card (if time collapses to 90s)
“We sell an automation pipeline: IR files in, supervisory pack out. Softest quarter is HSBC interim 2025 — Topic 1 soft, packs agree → WATCH. We do not fire a peer ALERT off an all-neutral Barclays print. Null is allowed. Recalibration is gated. Re-run under two hours when next PDFs land.”

---

## Pre-record checklist
- [ ] Deck exported PDF, ≥14 pt, filenames per Canvas  
- [ ] Desk open on HSBC H1; notebook Stages bookmarked  
- [ ] One quote + one agree-row on a backup slide  
- [ ] Full dry-run timed to **13:30–16:30** once  

Walkthrough detail: [`A2_checklist.md`](A2_checklist.md)

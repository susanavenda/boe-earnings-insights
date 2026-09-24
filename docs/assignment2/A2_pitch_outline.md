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

| Block | Time | Job | Speaks |
|---|---|---|---|
| **1. Background** | 0:00–3:00 | Client context + business question | **Taz** |
| **2. Approach** | 3:00–12:00 | Pipeline · models · eval · episode · desk/notebook | see slides below |
| **3. Conclusion** | 12:00–15:00 | Findings · workflow fit · obstacles · ask | **Taz** |

---

### BLOCK 1 — Background (~3 min)

#### Slide 1 — Title / hook (30s) · **Taz**
**Title:** Supervisory earnings pipeline — early warning from Q&A  
**Subtitle:** Group 9 · Bank of England employer project  
**On slide:** sell line + KPI strip — **1,002** analyst Q&A pairs · HSBC + Barclays · 3 baselines · dual episodes  

**Say:** “We’re not pitching another sentiment model. We’re pitching a **repeatable supervisory pipeline** that ends in alert, watch, or null.”

#### Slide 2 — Client problem (90s) · **Taz**
- PRA already sees **structured returns** clearly  
- Earnings **Q&A is messy, hedged, hard to scan every quarter**  
- **Business question:** Does narrative carry a leading signal metrics alone miss?  
- **Audience:** supervisors / desk analysts who need evidence, not a chatbot  

**Say:** “Our bet: yes — when theme tone and reported direction **diverge**. When they **agree** but tone is soft, that’s **WATCH**, not noise.”

#### Slide 3 — Scope (60s) · **Taz**
| In | Out |
|---|---|
| HSBC + Barclays (UK PRA perimeter) | Video / webcast |
| Public transcripts + Excel packs | Train from scratch |
| Alert / watch / null + PRA pack | Extra banks before the episode story is tight |

**Say (do not wait to be asked):** “A1 locked **20** transcripts (2×10). Hunter’s extra-year / appear–disappear test is why we ingested **2006–2026** IR. Live: **137** transcripts + **114** packs, **1,002** pairs. Deliberate extension, not unnoticed scope creep. Four metrics and two banks stay locked.”

---

### BLOCK 2 — Approach (~9 min)

#### Slide 4 — The automation pipeline (90s) ★ centrepiece · **Susana**
One left→right diagram (big boxes, few words):

1. **Ingest** — PDFs + Excel · **Susana**
2. **Prepare** — clean, segment analyst vs management · **Susana**
3. **Model** — BERTopic (**Debanjan**) · FinBERT + LDSA (**Alfred**) · M6 behaviour (**Bupathi**) · eight-way (**Aidan**)
4. **Evaluate** — temporal · matched peer · struct↔Q&A · **Susana** (views) · **Aidan** (human dual-code)
5. **Decide** — protocol → episode · **Aidan** (rules) · **Bupathi** (M6 inputs)
6. **Publish** — PRA note (**Rafael**) + desk (`desk.sqlite`) (**Susana**)

**Footer:** Next-quarter re-run **45–90 min** when new IR files land.

**Say:** “Every arrow is automated enough to re-run. Recalibration is **gated** — we do **not** retrain on every PDF drop-in.”

#### Slide 5 — Data preparation (60s) ← rubric · **Susana**
- **Gather:** **137** IR PDFs + **114** Excel packs under `data/raw/transcripts/` and `data/structured/` (A1 plan was 20 transcripts; extra years are Hunter-prompted, 2006–2026)  
- **Clean / format:** pdfplumber extract → speaker regex (HSBC / Barclays patterns) → analyst-only corpus  
- **Pair:** **1,002** Q&A pairs; named analyst 100%. **Disclose, A3 fix:** empty bleed-split answers and blank inherited dates (live counts in notebook 1.5 / 7.0)  
- **Represent:** `clean_text` for topics; raw text for FinBERT; metrics table from Excel  
- **Store:** intermediates in `data/boe.sqlite` (files = inputs only)  

**Say:** “Preprocessing is justified for **messy transcript text**, not tabular Kaggle defaults. We extended the corpus on Hunter’s advice; we did not silently abandon the A1 20-doc plan.”

#### Slide 6 — Method choice & why (75s) ← rubric · **Debanjan** (topics) · **Alfred** (sentiment) · **Bupathi** (M6, 20s)
| Choice | Why it fits this domain | Owner |
|---|---|---|
| **BERTopic** | Themes emerge from Q&A; we don’t force a fixed taxonomy day one | **Debanjan** |
| **LDA + c_v** | Independent sanity check on clusters | **Debanjan** |
| **FinBERT** | Finance-domain sentiment prior | **Alfred (Qianyi)** |
| **LDSA** | Lexicon cross-check when transformers over-neutralise hedges | **Alfred (Qianyi)** |
| **Light FT** | Domain adapt only when human labels grow — promote if hold-out doesn’t regress | **Alfred (Qianyi)** |
| **M6 behaviour** | Directness, coverage, substitution — Avoidance is behaviour, not a FinBERT class | **Bupathi** |
| **Extractive briefs** | Four-metric quotes a supervisor can check | **Rafael** |
| **Rules protocol** | Supervisors need **reproducible** alert/watch/null, not opaque scores | **Aidan** |

#### Slide 7 — Evaluation, fine-tune, verification (90s) ← rubric · **Aidan** (8-way) · **Alfred** (FinBERT / FT)
- **Baselines:** temporal shift · matched peer gap · structured vs unstructured direction  
- **Hand sample (coder 1 = Alfred, 90 pairs · 172 labels, `human_labels/sentiment_agreement.json`):** whole-turn FinBERT **60% raw / κ 0.28 / macro-F1 0.52**; finds only **43%** of human-negatives (24 of 51 called Neutral — the hedged-language gap, measured). Sentence-level FinBERT 46% / κ 0.13; Loughran–McDonald 42% / κ 0.02 (chance). **LLM annotator** (Claude, same coding guide verbatim, blind, all 1,826 texts — `docs/assignment2/llm_sentiment_labels.csv`): questions **65% / κ 0.39**, finds 69% of coder-1 negatives (FinBERT 31%); answers 45% / κ 0.15 — it over-calls management *positive* where coder 1 reads *neutral*; pooled 55% / κ 0.31. Best unit per side: LLM on questions, whole-turn FinBERT on answers. **M4 70% not met by any unit.** Second coder (Aidan) pending → coder-vs-coder κ/α is the human ceiling. Do **not** quote the old "75% / 0.61" — not reproducible, and that queue's gold was FinBERT's own label.  
- **Scoring unit (Alfred):** FinBERT is sentence-trained, so we tested sentence-by-sentence scoring; on human gold it did **not** beat whole-turn (κ 0.13–0.18 vs 0.28 under every threshold tried) — whole-turn stays the scorer, sentence columns kept as a documented negative result. LDSA = Loughran–McDonald dictionary with a hedging index; as a 3-way label it is at chance, so it is a hedging measure, not a classifier.  
- **8-way eval:** machine coder1 vs coder2 **35%** (headline) · human dual-code vs coder1 **50%** (below 70%) — method, not category law  
- **Not on this slide:** Stage 3.1c LLM vs FinBERT is optional extra and **skips without an API key** — do not demo it live unless a key is in the environment that day  
- **Not on this slide:** Stage 10.2 Yahoo press is **filtered** to own-results headlines (bank as subject + earnings/results/profit/quarter). Live n is usually ~0 — that is the finding, not a 0.04 gap on Netflix downgrades. Do not quote an unfiltered press-vs-Q&A number.  
- **FT:** silver labels train; human gold is **held out** and is the only gate (n ≥ 40 and macro-F1 ≥ zero-shot + 0.05). Silver-dev gains are circular (silver is built from FinBERT + LDSA) — `active_model_id` stays null until the human set passes  
- **Manual verify:** quote cards + struct↔Q&A agree column on the episode  

**Say:** “The two keyword coders agree 35%. That is why eight-way is a filing method, not a law — and why we gate peer ALERT when Barclays is all-neutral.”

#### Slide 8 — Episode proof: HSBC H1 2025 (90s) · **Rafael** (briefs / quote) · **Bupathi** (A3 / M6)
- Softest print in sample (FinBERT net ≈ **−0.13**, n=8); four pack lines **agree** → **WATCH (A3)**  
- Do not hang the verdict on BERTopic id 1 (ids move if the model is refit) — use quotes + agree column  
- Matched peer: Barclays **0.00** (n=6, all FinBERT-neutral) → gap looks scary, **not A2-eligible**  
- **Quote:** one impairment / tariffs analyst turn  

**Say:** “This is the pipeline output: a governed verdict with evidence, not a leaderboard score.”

#### Slide 9 — Live walkthrough (2 min) ← “Notebook + solution” · **Susana**
**Part A — Desk (product):** http://localhost:8501 · click **WATCH · HSBC 2025-H1** (Barclays 2026 is also WATCH — skip it)  
Episodes (HSBC) → Evidence → Peer & protocol → PRA download  

**Part B — Notebook (technical):** Stages 1 → 2/3 → 6 → 8/9 — point at cells, don’t scroll-read.

**Say:** “Desk is what the supervisor opens. Notebook + scripts are the factory.”

---

### BLOCK 3 — Conclusion (~3 min)

#### Slide 10 — Findings (60s) · **Rafael** (PRA pack) · **Taz** (if time is tight, Taz reads this)
1. Narrative **can** flag soft quarters metrics alone don’t prioritise  
2. Soft + packs agree → **WATCH**; soft + packs disagree → path to **ALERT**  
3. Naive peer gaps are dangerous when one side is model-flat  
4. **Null is allowed** and reportable  

#### Slide 11 — Integration & obstacles (60s) ← rubric · **Taz**
**Fit:** overnight / quarterly job → versioned pack → desk or PRA one-pager  

**Obstacles:**
- Hedged language → transformer over-neutral  
- Small N / flat peers break gap rules  
- Labels are scarce — don’t automate promotion  
- Change management: supervisors must trust **rules + evidence**, not model mystique  

#### Slide 12 — Ask / close (45s) · **Taz**
**For BoE:** Is alert / watch / null the right product shape for the desk?  
**For markers:** Depth on two G-SIBs + a **repeatable pipeline** beats breadth.  
**Next (A3):** more true human labels · promote FT only if gates pass · optional RAG  

**Close with sell line again.**

---

## Role split (who is responsible)

A1 Appendix D roles. Everyone must know the sell line.

| Person | Owns (factory) | Speaks (15-min MP4) |
|---|---|---|
| **Taz** | Coordinator · editor/QA · A2 deck/PDF | Slides 1–3 Background · 11–12 close |
| **Susana** | Data pipeline · notebook · desk sqlite | Slides 4–5 pipeline/data · Slide 9 desk + notebook |
| **Debanjan** | Topics · BERTopic · LDA · cluster names | Slide 6 topics |
| **Alfred (Qianyi)** | FinBERT · LDSA · FT gate | Slide 6 sentiment · Slide 7 FinBERT/FT numbers |
| **Bupathi** | M6 behavioural (directness, coverage, substitution) | Slide 6 M6 · Slide 8 protocol/A3 |
| **Rafael** | Summarisation · extractive metric briefs · PRA one-pager | Slide 8 quote/briefs · Slide 10 findings |
| **Aidan** | M2a eight-way · human dual-code · alert/watch/null rules | Slide 7 8-way (35% / 50%) |

---

## Speaker card (if time collapses to 90s)
“We sell an automation pipeline: IR files in, supervisory pack out. Softest quarter is HSBC interim 2025 — FinBERT −0.13, packs agree → WATCH. We do not fire a peer ALERT off an all-neutral Barclays print. Null is allowed. Recalibration is gated. Re-run under two hours when next PDFs land.”

---

## Pre-record checklist
- [ ] Deck exported PDF, ≥14 pt, filenames per Canvas  
- [ ] Desk open on HSBC H1; notebook Stages bookmarked  
- [ ] One quote + one agree-row on a backup slide  
- [ ] Full dry-run timed to **13:30–16:30** once  

Walkthrough detail: [`A2_checklist.md`](A2_checklist.md)

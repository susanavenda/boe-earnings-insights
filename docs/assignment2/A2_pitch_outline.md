# Assignment 2 — Preliminary solution pitch (outline)

**Due:** 28 Sep · Group 9 · Bank of England employer project  
**Story spine:** *HSBC H1 Q&A went soft (Topic 1) while packs moved with the narrative — WATCH, not a false peer ALERT. Barclays 2025-q2 exists but is 100% FinBERT-neutral, so gap≈HSBC net is not an A2 fire.*

Use with notebook **Stage 8** and artifacts in `data/processed/supervisory_episode.json`.

---

## Slide 1 — Hook (30s)
**Title:** Early warning from earnings Q&A — HSBC H1 2025 episode  
**One line:** Softest analyst-tone print in sample (FinBERT net ≈ −0.13); packs agree on direction → **WATCH (A3)**, not a peer-gap ALERT.  
**Visual:** KPI strip — 118 turns · 2 banks · 3 baselines · dual episodes

## Slide 2 — Problem (BoE brief)
PRA sees structured returns clearly; Q&A is messy and hedged.  
**Question:** Does narrative carry a leading signal metrics alone miss?  
**Our bet:** Yes, when *theme tone* and *reported direction* diverge.

## Slide 3 — Pipeline (what we built)
Keep this one visual — boxes left→right:

1. **Ingest** PDFs + Excel packs  
2. **Segment** analyst vs management  
3. **Topics** BERTopic (+ LDA / c_v)  
4. **Sentiment** FinBERT + LDSA (+ light domain adapt)  
5. **Summarise** metric briefs (DistilBART → Phi-4 later)  
6. **Evaluate** temporal · matched peer · struct↔unstruct  
7. **Decide** alert / watch / null protocol  

*Repeatable:* ~45–90 min next quarter (Stage 7.0).

## Slide 4 — Episode: HSBC 2025-interim (= 2025-H1)
- Topic **1** (costs / forward questions) dominates the soft print  
- Matched **2025-H1**: HSBC −0.13 (n=8) vs Barclays **0.00** (n=6, **all FinBERT-neutral**) → gap = −0.13 but **not A2-eligible** (trivial peer)  
- Structured pack **2025-q2**: impairment/costs/income directions **agree** with Q&A tone  
**Quote card:** 1–2 analyst turns on impairment / tariffs (from `episode_quotes.csv`)  
**Honest line:** “We have Barclays 2025-q2; it’s flat-neutral under FinBERT — we do not sell that as a strong peer contrast.”

## Slide 5 — Struct vs narrative (the BoE question)
Table from `episode_metric_briefs.csv`: metric · reported direction · Q&A tone · agree?  
**Punchline:** Impairment / cost questions are where disagreement shows up.  
Overall sample still ~74% divergence — episode makes it concrete.

## Slide 6 — Alert vs null (product, not model zoo)
| Signal | Action |
|---|---|
| Topic 1 neg ↑ + impairment disagree | **Alert** → desk review |
| Peer gap < −0.10 on H1/FY | **Alert** → cross-bank compare |
| Soft tone but metrics agree | **Watch** |
| Flat / agree | **Null** — reportable “no edge” |

Show `rules_fired` from episode JSON (**HSBC: A3 only** after peer-quality fix; dual episode Barclays 2026-q2 also WATCH).

## Slide 7 — What we’d ship next (A3)
- Larger human labels; re-run light FT  
- Optional generative polish (`USE_GEN=1`) / Phi-4 later  
- **Done early:** second episode (Barclays 2026-q2) + PRA one-pagers + re-run checklist  
- Optional: RAG “ask the transcript” for supervisors  

## Slide 8 — Ask / close
**For BoE:** Is alert/null the right product shape?  
**For markers:** Depth on two G-SIBs + repeatable pipeline > breadth.

---

## Speaker notes (90s version)
“We locked HSBC and Barclays. Softest quarter is HSBC interim 2025: Topic 1 soft, packs agree → WATCH. Barclays’ matched 2025-q2 print is six all-neutral turns, so we do not fire a peer-gap ALERT just because gap equals HSBC’s net. We alert only when both sides are informative, or theme and pack disagree. Null is allowed. Re-run is under two hours when next PDFs land.”

## Demo checklist
- [ ] Run notebook through Stage 8  
- [ ] Open `supervisory_episode.json` + `episode_metric_briefs.csv`  
- [ ] One slide with peer gap bar (matched periods)  
- [ ] One quote slide (human-readable, not full PDF)

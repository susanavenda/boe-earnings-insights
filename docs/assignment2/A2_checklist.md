# Assignment 2 — checklist (pipeline sell)

**Due:** Mon 28 Sep 2026 17:00 UK · Group 9  
**Sell:** automation pipeline → versioned **alert / watch / null** pack (desk = output surface)

Full run-of-show: [`A2_pitch_outline.md`](A2_pitch_outline.md)

---

## Submit
- [ ] `Group9_CAM_EP_Assignment2_slides.pdf`
- [ ] `Group9_CAM_EP_Assignment2_presentation.mp4` (15 min ±10%)

## 15-min blocks
- [ ] **Background** (3) — **Taz** — client problem + scope  
- [ ] **Approach** (9) — pipeline **Susana** · methods **Debanjan / Alfred / Bupathi / Aidan / Rafael** · eval **Aidan + Alfred** · HSBC episode **Rafael + Bupathi** · desk + notebook **Susana**  
- [ ] **Conclusion** (3) — **Taz** (findings with **Rafael** if time) · integration/obstacles · ask  

## Desk walkthrough (inside Approach) · **Susana**
Open http://localhost:8501

1. **Episodes** — click **WATCH · HSBC 2025-H1** (not Barclays 2026)  
2. **Evidence** — packs agree · one quote  
3. **Peer & protocol** — A2-usable no · A3 only  
4. **PRA note** — download  

**Line:** “Null is allowed. We don’t invent a peer ALERT from a flat-neutral Barclays print.”

## Tech ready · **Susana** (factory/desk) · **Taz** (PDF/MP4)
- [ ] `data/boe.sqlite` + episode scripts + `label_agreement.py`  
- [ ] Demo frozen pack opens offline  
- [ ] Backup slide: quote + agree-row  

## Honest metrics (say once)
Sentiment (Alfred): coder 1 on 90 pairs → whole-turn FinBERT **60% raw / κ 0.28 / macro-F1 0.52**, negative recall 43%; sentence-level and lexicon worse; **M4 70% not met**. Say it plainly and say why it matters (under-called negatives are the alert-relevant class). Quote `human_labels/sentiment_agreement.json`; update when Aidan's file lands. Never the old "75% / 0.61".  
**Headline:** machine coder1 vs coder2 n=60 = **35%**. Aidan vs coder1 = **50%** (below 70%). Eight-way is a method, not a category law. Disagreement clusters on costs↔earnings↔franchise and credit↔IRRBB, not uniform noise. Topics 0 and 3 still dual-code-disagree.

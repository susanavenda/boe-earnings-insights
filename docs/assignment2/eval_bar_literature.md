# Evaluation bar — literature, not an assertion

Hunter’s question: is **70% agreement on 60 pairs** a defensible human-eval bar, or just a number we wrote down?

This note is the check. It does **not** change Aidan’s labels, the 35% machine dual-code, or the promotion gate. Extra-scope for A2; the live numbers stay as scored.

## What we actually use

| Gate | What it is | What it is not |
|---|---|---|
| **70%** on the 60-pair 8-way | Raw percent agreement, Aidan vs machine coder1 (and coder1 vs coder2) | Not Cohen’s κ, not Krippendorff’s α |
| **n = 60** | Stratified sample of parsed Q&A pairs | Not a power calculation for 8 nominal classes |
| **M4/M7 bar unmet** | Aidan vs coder1 **50%**; coder1 vs coder2 **35%** | Not a reason to promote FinBERT or invent a category law |

Live score: `python scripts/score_m2a_human.py` → `docs/assignment2/human_labels/m2a_agreement.json`.

## Chance-corrected reliability (content analysis)

Krippendorff’s rule of thumb for **α**, not raw % ([Krippendorff 2004 / 2019](https://doi.org/10.1093/hcr/30.3.411); summary in [ATLAS.ti ICA manual](https://doc.atlasti.com/ManualWin/ICA/ICASampleSizeAndDecisionRules.html)):

- **α ≥ 0.800** — customary for conclusions you would treat as dependable
- **0.667 ≤ α < 0.800** — only tentative conclusions
- **α < 0.667** — do not treat the coding as reliable enough to support claims

He is explicit that there are **no magical numbers**; the cut-off should track the cost of a wrong conclusion. A PRA-facing method is closer to “wrong alert is costly” than to a classroom coding exercise, so **α ≥ 0.80** is the literature’s default, not 70% raw overlap.

Lombard, Snyder-Duch & Bracken ([2002](https://doi.org/10.1111/j.1468-2958.2002.tb00826.x); [2003 correction](https://doi.org/10.1111/j.1468-2958.2003.tb00850.x)) do **not** publish a single “α ≥ 0.70 or % ≥ 0.90” cutoff of their own. They quote Neuendorf (2002): coefficients **≥ .90** acceptable to all, **≥ .80** in most situations, **.70** only for some exploratory indices. They then require a **higher** bar for liberal percent agreement and a **lower** bar for conservative α/κ/π — or a dual rule: moderate on a conservative index **or** high on a liberal one. Our **70% raw** bar is the liberal index at the exploratory cutoff, the side they warn against using alone. Krippendorff criticised mixing chance-corrected α with a liberal percent floor. It is a **floor for a student dual-code**, not a claim that the 8-way taxonomy is reproducible at Krippendorff’s standard.

Landis & Koch ([1977](https://doi.org/10.2307/2529310), *Biometrics* 33(1) 159–174) κ bands (“substantial” ≈ 0.61–0.80) are **ordinal conventions for two raters**, not a sample-size formula, and they inflate when one class dominates (FinBERT-neutral Q&A).

## Sample size

For **two coders**, equally likely codes, α_min = 0.667 at p = 0.05, ATLAS.ti’s table (Krippendorff / Bloch–Kraemer) wants on the order of:

- **4 codes → ~81 units**
- **α_min = 0.800, 4 codes → ~139 units**

Eight M2a classes are **sparser** than four. n = 60 is **below** that 4-code 0.667 row, and far below an 8-way 0.80 row. The 60-pair sample can **detect that the scheme does not stabilize** (it did: 35% machine–machine). It cannot certify that 70% would have been enough had we hit it.

Rule of thumb in the same manual: enough units that **each code could agree by chance at least five times**. Rare M2a bins (IRRBB, franchise) will not meet that on n = 60.

## Earnings-call NLP (same genre, not the same task)

| Source | Task | Agreement | n (reliability subset) |
|---|---|---|---|
| [FinArg, ACL FinNLP 2022](https://doi.org/10.18653/v1/2022.finnlp-1.22) | Argument components / relations in ECC transcripts | α_U = **0.70** components; α = **0.81** relations | 12 calls (~20% of 136), four annotators pairwise |
| [EvasionBench, 2026](https://arxiv.org/abs/2601.09142) | Managerial evasion in ECC Q&A (3-way) | Cohen’s κ = **0.835** (89% raw) | 100 human gold items (eval set is 1k) |
| [FEVER 2024 numeric claims](https://aclanthology.org/2024.fever-1.21.pdf) | In-claim vs out-of-claim sentences | 95.8% raw on earnings-call sentences | 498 ECC sentences, two finance annotators |
| RANLP 2017 sentiment IAA survey | General sentiment, 3-way | κ often **0.4–0.7**; 6-emotion κ as low as 0.26 | Varies; more classes → lower κ |

Domain papers that look “high agreement” are usually **fewer classes** (binary claim, 3-way evasion) and **larger gold sets** than our 8-way n = 60. FinArg’s 0.70 is **α on argument spans**, not 8-way prudential tags, and they still treat 0.70 as the **lower** Krippendorff band.

## What this means for Group 9

1. **70% raw on 60 pairs was never a literature standard.** It is an A1 working bar. Against Krippendorff it is lenient (raw vs α) and the n is small for 8 nominal classes.
2. **Failing the bar is the honest result.** 50% human–machine and 35% machine–machine are what you say on the pitch. Do not raise the sample in the slide as if 70% were met.
3. **A3, if labels grow:** report **Krippendorff’s α** (or κ with prevalence) on the 8-way, not only %. Size toward **≥80–140 pairs** before treating the taxonomy as dependable; rarer codes need oversampling.
4. **3-way FinBERT gold (n = 20 reviewed)** is a different, coarser task. EvasionBench-scale κ is the kind of number you would need before promoting a model — which is why `active_model_id` stays null at 20 / 40.

## Sources

- Krippendorff, K. (2004). Reliability in content analysis: some common misconceptions and recommendations. *Human Communication Research* 30(3), 411–433. https://doi.org/10.1093/hcr/30.3.411
- Krippendorff, K. (2019). *Content Analysis* (4th ed.), reliability chapters; sample-size table reproduced in ATLAS.ti ICA manual. https://doc.atlasti.com/ManualWin/ICA/ICASampleSizeAndDecisionRules.html
- Lombard, M., Snyder-Duch, J., & Bracken, C. C. (2002). Content analysis in mass communication: assessment and reporting of intercoder reliability. *Human Communication Research* 28(4), 587–604. https://doi.org/10.1111/j.1468-2958.2002.tb00826.x
- Lombard, M., Snyder-Duch, J., & Bracken, C. C. (2003). Correction. *Human Communication Research* 29(3), 469–472. https://doi.org/10.1111/j.1468-2958.2003.tb00850.x
- Landis, J. R., & Koch, G. G. (1977). The measurement of observer agreement for categorical data. *Biometrics* 33(1), 159–174. https://doi.org/10.2307/2529310
- Artstein, R., & Poesio, M. (2008). Inter-coder agreement for computational linguistics. *Computational Linguistics*.
- Accuosto, P., et al. (2022). FinArg: annotating argumentation in earnings calls. ACL FinNLP. https://doi.org/10.18653/v1/2022.finnlp-1.22
- EvasionBench (2026). Managerial evasion in earnings-call Q&A. https://arxiv.org/abs/2601.09142
- Shah, A., et al. (2024). Numerical claim detection in finance. FEVER. https://aclanthology.org/2024.fever-1.21.pdf

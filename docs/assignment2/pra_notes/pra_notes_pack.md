# PRA supervisory note — HSBC 2025-interim (H1)

**Date:** 2026-09-09 · **Group 9** · Bank of England employer project  
**Window:** 2025-H1 (narrative `2025-interim` · pack `2025-q2`)

---

## Verdict

**WATCH — soft Q&A tone but narrative broadly agrees with pack directions**

HSBC 2025-interim (H1): FinBERT net -0.13; Topic 1=5 turns; peer on 2025-H1: HSBC=-0.126 (n=8) vs Barclays=0.000 (n=6); gap=-0.126 — Matched 2025-H1 has both banks, but one side is 100% FinBERT-neutral (HSBC net=-0.126, n=8, non-neut=25%; Barclays net=0.000, n=6, non-neut=0%). Gap -0.126 is not treated as an A2 alert.

| KPI | Value |
|---|---|
| Analyst turns | 8 |
| FinBERT net | -0.126 |
| Topic 1 turns / neg share | 5 / 40% |
| Peer sides (matched) | HSBC -0.126 (n=8, non-neut 25%) · Barclays 0.000 (n=6, non-neut 0%) |
| Peer gap (HSBC − Barclays) | -0.126 · **not used for A2** |
| Rules fired | A3 |

**Peer caveat:** Matched 2025-H1 has both banks, but one side is 100% FinBERT-neutral (HSBC net=-0.126, n=8, non-neut=25%; Barclays net=0.000, n=6, non-neut=0%). Gap -0.126 is not treated as an A2 alert.

---

## Struct vs Q&A (claim check)

| Metric | Reported | Q&A tone | Agree? |
|---|---|---|---|
| credit_impairment | down | down | yes |
| operating_costs | down | down | yes |
| cet1_ratio | flat | flat | yes |
| total_income | down | down | yes |

*Agree? = yes/no only when Q&A tone exists; **n/a** if no metric hits in the episode (absence ≠ agreement).*

---

## Protocol

| Rule | Severity | This note | Condition |
|---|---|---|---|
| A1 | alert | — | Topic 1 negative share rises vs prior print AND credit_impairment narrative disagrees with reported direction |
| A2 | alert | — | Matched peer gap (HSBC−Barclays) < −0.10 on H1/FY, both banks n≥3, and peer side not 100% FinBERT-neutral |
| A3 | watch | FIRED | FinBERT net soft (< −0.08) but structured metrics agree with narrative |
| N1 | null | — | Topics stable, FinBERT net ≈ flat, structured↔unstructured agree |

---

## Suggested action

- If **alert**: desk pulls quoted turns + ECL/cost pack lines; compare peer on same calendar window (only when both sides are informative).
- If **watch**: log softness; no escalation unless A1/A2 fires next print.
- If **null**: file “no early-warning edge from Q&A this quarter.”

## Re-run cost (next quarter)

Assuming new IR PDFs/Excel packs are available: **~45–90 minutes** (drop files → notebook Stages 1–9 → spot-check 20–40 turns → regenerate this note).

---

*Generated from `data/processed/supervisory_episodes.json` via `scripts/generate_pra_note.py`.*


---

# PRA supervisory note — Barclays 2026-q2 (H1)

**Date:** 2026-09-09 · **Group 9** · Bank of England employer project  
**Window:** 2026-H1 (narrative `2026-q2` · pack `2026-q2`)

---

## Verdict

**WATCH — soft Q&A tone but narrative broadly agrees with pack directions**

Barclays 2026-q2 (H1): FinBERT net -0.11; Topic 1=1 turns; peer on 2026-H1: HSBC=-0.029 (n=19) vs Barclays=-0.107 (n=7); gap=0.079

| KPI | Value |
|---|---|
| Analyst turns | 7 |
| FinBERT net | -0.107 |
| Topic 1 turns / neg share | 1 / 0% |
| Peer sides (matched) | HSBC -0.029 (n=19, non-neut 5%) · Barclays -0.107 (n=7, non-neut 14%) |
| Peer gap (HSBC − Barclays) | 0.079 |
| Rules fired | A3 |



---

## Struct vs Q&A (claim check)

| Metric | Reported | Q&A tone | Agree? |
|---|---|---|---|
| credit_impairment | down | n/a | n/a |
| operating_costs | down | flat | no |
| cet1_ratio | flat | n/a | n/a |
| total_income | up | down | no |

*Agree? = yes/no only when Q&A tone exists; **n/a** if no metric hits in the episode (absence ≠ agreement).*

---

## Protocol

| Rule | Severity | This note | Condition |
|---|---|---|---|
| A1 | alert | — | Topic 1 negative share rises vs prior print AND credit_impairment narrative disagrees with reported direction |
| A2 | alert | — | Matched peer gap (HSBC−Barclays) < −0.10 on H1/FY, both banks n≥3, and peer side not 100% FinBERT-neutral |
| A3 | watch | FIRED | FinBERT net soft (< −0.08) but structured metrics agree with narrative |
| N1 | null | — | Topics stable, FinBERT net ≈ flat, structured↔unstructured agree |

---

## Suggested action

- If **alert**: desk pulls quoted turns + ECL/cost pack lines; compare peer on same calendar window (only when both sides are informative).
- If **watch**: log softness; no escalation unless A1/A2 fires next print.
- If **null**: file “no early-warning edge from Q&A this quarter.”

## Re-run cost (next quarter)

Assuming new IR PDFs/Excel packs are available: **~45–90 minutes** (drop files → notebook Stages 1–9 → spot-check 20–40 turns → regenerate this note).

---

*Generated from `data/processed/supervisory_episodes.json` via `scripts/generate_pra_note.py`.*

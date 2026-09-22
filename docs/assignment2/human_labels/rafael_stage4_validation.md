# Rafael — Stage 4 manual spot check and pitch evidence

Snapshot: `docs/assignment2/human_labels/_raw/qa_pairs_export.csv` (181 parsed Q&A pairs). Reproduced notebook cells 4.1–4.3 against this checked-in export; these are saved execution outputs, not a new PDF extraction. Every classification below concerns the **captured pair**, not the full earnings call. `faithfulness_support=1` on extractive output only measures source overlap; it is not a human accuracy score.

## Manual review sample

`F` = the source supports the selected quote/status; `C` = enough metric context for a short brief. This is a targeted eight-row diagnostic sample across both banks, including failure cases; it does not estimate full-corpus precision.

| pair_id | metric | human F | human C | Source check / action |
| --- | --- | --- | --- | --- |
| `barclays_2026-q2_005` | operating_costs | yes | no | Question asks about BUK costs; captured answer is empty. Mark `unanswered` **in this export** and do not attribute silence to Barclays. |
| `barclays_2025-q2_001` | cet1_ratio | yes | no | Question mentions 13.7% capital position; captured answer pivots to IB. Mark `answer_off_metric`, not a CET1 management answer. |
| `hsbc_2026-q1_002` | operating_costs | yes | yes | Answer says 3% gross cost growth less 2% savings gives about 1% net. Former regex missed plain “costs”. |
| `hsbc_2025-interim_003` | cet1_ratio | yes | yes | Answer says BoCom impairment has no CET 1 ratio impact. Former regex missed the space in “CET 1”. Keep separate from the credit impairment brief for the same pair. |
| `hsbc_2024-annual_006` | operating_costs | yes | yes | Answer discusses cost guidance beyond FY25. Sentence splitter formerly cut at “i.e.”; the saved output now retains the complete sentence. |
| `barclays_2024-annual_003` | operating_costs | yes | no | Answer gives forward costs above £17bn; automatic two-sentence selection still favours a Tesco cost/income sentence as well. Review the full answer before using on a slide. |
| `hsbc_2025-interim_003` | credit_impairment | yes | no | Management discusses office CRE oversupply and ECL. The automatic brief omits some surrounding CRE context; use the source pair for the episode quote. |
| `hsbc_2025-interim_008` | cet1_ratio | yes | no | Answer includes $14bn threshold-deduction headroom and $13bn market value, plus a conditional no-material-CET1-impact statement. Corrected the older hand brief, which had mistakenly claimed the answer lacked capital figures. |

## Slide-ready HSBC episode

- Source: `hsbc_2025-interim_003`, analyst Kunpeng Ma, HSBC interim 2025 analyst Q&A; source PDF identified in the Q&A export (`source` column). Management distinguishes stabilised residential development from continuing office CRE pressure: “specifically around the office CRE space in Hong Kong, we’re still struggling because of some oversupply in this space.”
- Interpretation: office CRE pressure persists despite a more stable residential segment. This supports **watch / investigate**, not an automated conclusion about HSBC's prudential condition.
- Quantitative cross-check: the team's existing `docs/assignment2/pra_notes/pra_notes.md` records the HSBC 2025-interim credit impairment pack direction as down and the Q&A direction as down, while its `Agree` field says `n/a`. Do not present this as a validated numeric agreement until the corresponding structured Excel row and rule are checked.
- Suggested slide caption: “HSBC 2025 interim: office CRE remains under pressure even as residential development stabilises (`hsbc_2025-interim_003`). Human review of the Q&A supports a WATCH interpretation; check the underlying pack before claiming a numeric match.”

## Changes and limits

The Stage 4 matcher now recognises plain operating “cost(s)”, “CET 1” with a space, and “capital position”; “credit cost” and “cost of risk” remain excluded from operating-cost matches. Sentence splitting preserves `i.e.` / `e.g.`. Re-running against the 181-pair export yields 724 pair × metric audit rows, 255 keyword-matched briefs, and a 69-row review queue. Increased keyword coverage may add incidental mentions, so the 69 queue rows still need human review and `human_faithful` / `human_complete` fields in SQLite remain unfilled. The eight reviews above are documented here; they are not entered as a complete queue validation.

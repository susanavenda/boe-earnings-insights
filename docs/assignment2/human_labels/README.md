# Human labels (M2a / M7 / Stage 4)

Independent of the machine dual-code. Stage 7 scores whether keyword tagging holds up.

| File | Owner | What it is |
|---|---|---|
| [`m2a_aidan_labels.csv`](m2a_aidan_labels.csv) | Aidan | 60-pair 8-way labels from reading Q&A. `aidan_pair` is the filing. `aidan_q` / `aidan_a` are the two sides. Machine columns were **not** visible while coding. |
| [`sample_60_for_coding.md`](sample_60_for_coding.md) | — | The pack Aidan coded (no machine categories). |
| [`sample_60_machine_key.csv`](sample_60_machine_key.csv) | machine | Hidden key for agreement only. |
| [`topic_interpretation.md`](topic_interpretation.md) | Debanjan, Alfred, Dan | BERTopic clusters named from real turns; two independent 8-way maps; disagreements on Topics 0 and 3 recorded. |
| [`rafael_metric_briefs.md`](rafael_metric_briefs.md) | Rafael | Extractive four-metric briefs. Replaces DistilBART prompt-echo as the A2 quote surface. |
| [`topic_examples.md`](topic_examples.md) | — | Four raw turns per topic. |
| `_raw/` | export | Full sqlite dump used to build the sample. Not a deliverable. |

## How Aidan coded (so the check stays independent)

1. Read **Q first**. File the pair on the first substantive question.
2. Courtesy-only or truncated Q → `untagged`. Do not back-fill from a long A (that would copy management, not test the machine).
3. Two-question turns: lead ask is `aidan_pair`; the other limb stays in `aidan_note`.
4. Structural hedge → `profitability_earnings` when the ask is NII/guidance; `market_traded_risk` when the ask is IRRBB/long-rate sensitivity.
5. Tax has no M2a home; `hsbc_2026-interim_008` is filed on the variable-pay/opex limb.

## Score it

```bash
python scripts/score_m2a_human.py
```

Writes `docs/assignment2/human_labels/m2a_agreement.json` and prints machine `coder1` vs `aidan_pair`. That is the Stage 7 number. It is **not** a PRA rating of either bank.

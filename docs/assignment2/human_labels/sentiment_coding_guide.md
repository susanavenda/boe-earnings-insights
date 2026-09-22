# Sentiment coding guide (M4 — 3 labels, question and answer separately)

Code each pair **independently** and **without** opening any machine label file
(`sentiment_60_machine_key.csv` is the hidden key). Fill `sentiment_60_labels_template.csv`
— one row per pair, save as `sentiment_60_labels_<yourname>.csv`.

## What you are labelling

The **stance toward the bank's prudential condition or outlook** that the text carries —
not politeness, not whether the speaker is friendly, not whether the number is big.

| Label | Question (analyst) | Answer (management) |
|---|---|---|
| **negative** | Probes a concern: deterioration, pressure, risk, miss, capital/credit/cost worry, scepticism about guidance | Concedes weakness, guides down, flags headwinds, impairment/cost pressure, uncertainty that is clearly adverse |
| **positive** | Frames improvement or strength (rarely — analysts mostly probe) | Asserts strength, improvement, confidence, guides up, beat, resilience |
| **neutral** | Asks for detail, mechanics, clarification, breakdown, timing; no stance | Explains mechanics, restates facts, mixed with no net direction, declines to comment |

## Rules for hedged bank language

1. **Hedged is not automatically neutral.** "We are cautious about the second half given
   what we're seeing in impairments" is **negative** even though it is polite and qualified.
   Label the direction the hedge points.
2. **Mixed with a net direction → that direction.** "Costs are up but income more than
   covers it" → positive. Balanced with no net → neutral.
3. **Courtesy is ignored.** "Thanks for taking my question, good morning" carries nothing.
4. **Questions:** label the *concern the analyst expresses*, not the topic. "Can you walk us
   through the NII bridge?" → neutral. "Why is the NII guide so much weaker than peers?" → negative.
5. **Answers:** label the *message about the metric / outlook*. "We don't guide on that" → neutral.
   "We expect impairments to normalise higher" → negative. "We're very confident in the 12% RoTE" → positive.
6. **Truncated or bleed text:** label what is there. If fewer than ~2 sentences of usable
   content, set `confidence=low` and still give your best label.
7. **Two questions in one turn:** label the *lead* ask; note the other in `note`.
8. Do not use a fourth class. Do not label "avoidance" — that is M6 (behaviour), not sentiment.

## Columns

| column | values |
|---|---|
| `pair_id` | as given |
| `q_label` | negative / neutral / positive |
| `a_label` | negative / neutral / positive (leave blank only if the answer is empty) |
| `confidence` | high / medium / low |
| `note` | free text, optional |

Aim for one sitting (~45–60 min). Two coders → we report raw %, Cohen's κ and Krippendorff's α
(`python scripts/score_sentiment_human.py`).

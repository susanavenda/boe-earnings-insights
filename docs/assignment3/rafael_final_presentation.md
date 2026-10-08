# Rafael — final presentation contribution

Issue #23 is due 11 October 2026. This file provides slide-ready content and a technical walkthrough for Rafael's assigned areas. The team-editable draft is [Group9_CAM_EP_Assignment3_presentation_draft](https://docs.google.com/presentation/d/1SZuuFdGVh7FNOh7-VSI5IvHuMdE0PlaXJIo8NV7NaV0/edit); the final deck still requires team review and PDF export.

## General-audience slide 1 — Traceable metric briefs

**Headline:** Long Q&A transcripts become evidence that a supervisor can inspect.

**Suggested visual flow:**

`1,307 Q&A pairs → 5,228 pair × metric checks → 1,362 relevant briefs → 366 review candidates`

**Supporting figures:**

- 1,020 briefs were classified as `answered_on_metric`.
- 318 were `answer_off_metric` and sent to review.
- 24 were `unanswered` and retained as limitations rather than silently dropped.

**Takeaway:** The pipeline prioritises evidence; it does not make a prudential judgement. Every brief keeps the source `pair_id`, metric and evidence quote.

**Speaker notes — approximately 35 seconds:**

> My part of the pipeline converts the full analyst Q&A corpus into evidence-grounded briefs for four supervisory metrics: income, operating costs, credit impairment and CET1. We process 1,307 Q&A pairs and retain 1,362 relevant briefs. Most are answered on metric, while 318 off-metric answers and 24 unanswered cases are explicitly preserved for review. The important point is traceability: each brief keeps its source identifier and quotation, so a supervisor can inspect the evidence instead of trusting generated text.

## General-audience slide 2 — What human checking changed

**Headline:** Human review supports directness triage, but topic substitution remains difficult.

**Recommended table:**

| Human label | Raw coder agreement | Cohen's κ |
|---|---:|---:|
| Answer addressed the question | 68.9% | 0.404 |
| Answer changed topic | 85.6% | 0.534 |
| Requested metric was supplied | 68.9% | 0.464 |
| Extracted answer was clean | 86.7% | 0.720 |

**Machine comparison:** on the 57 agreed yes/no directness cases, the original directness score achieved AUC 0.839. Topic-substitution agreement on the 31 measurable consensus cases was only 48.4% with κ 0.078.

**Interpretation:** Directness is useful for prioritisation. Topic substitution should not be presented as a reliable automated finding without human confirmation.

**Sample limitation:** the 90-pair validation sample deliberately oversampled substitution candidates, so its label shares are not corpus prevalence estimates.

**Speaker notes — approximately 40 seconds:**

> I also second-coded 90 Q&A pairs independently. Agreement was strongest for whether the extracted answer was clean, with 87 percent agreement and kappa of 0.72. The directness score separated agreed yes and no cases reasonably well, with an AUC of 0.84, so it can support review prioritisation. Topic substitution was much weaker, with near-zero kappa against the consensus subset. We therefore recommend using directness as a triage signal and keeping substitution human-reviewed rather than presenting it as an automated supervisory conclusion.

## Technical notebook walkthrough — Stage 4

### Cell 4.1 — Metric brief helpers and guardrails

- Four deliberately narrow metric dictionaries prevent broad keyword leakage.
- Candidate sentences must contain the selected metric.
- The default output is extractive.
- Optional generative compression is disabled in the submission run and fails closed to the extractive brief.
- Numeric and token-support gates reject some hallucinations, but they do not prove semantic correctness.

### Cell 4.2 — Full-corpus construction

- Applies the helper to every Q&A pair × four metrics.
- Produces the complete 5,228-row audit matrix and the 1,362 discussed-metric briefs.
- Preserves `source_pair_id` and disambiguates nine reused HSBC identifiers using the source filename.
- Retains `answered_on_metric`, `answer_off_metric`, `unanswered` and abstention states.

### Cell 4.3 — Quality and review queue

- Reports coverage and review rate by bank × metric.
- Sends all off-metric, unanswered and guardrail-failure cases to the priority queue.
- Adds deterministic routine cases for every bank × metric group.
- Leaves human fields blank; automatic diagnostics are not presented as human truth.

**Walkthrough closing line:**

> The technical design separates extraction, automatic guardrails and human judgement. That separation is the main control against unsupported supervisory claims.

## Suggested demonstration

1. Show the Stage 4 KPI cards in cell 4.2.
2. Open one `answered_on_metric` row and point to its `pair_id` and evidence quote.
3. Show one `answer_off_metric` row in the cell 4.3 review queue.
4. Explain that the automatic status prioritises review but does not decide whether management was evasive.
5. Finish on the bank × metric quality table and the human-validation limitation.

## Evidence references

- Notebook cells 4.1–4.3: `notebooks/boe_earnings_insights.ipynb`
- Human behaviour results: `docs/assignment2/human_labels/behaviour_agreement.json`
- Rafael's labels: `docs/assignment2/human_labels/behaviour_90_labels_rafael.csv`
- Stage 4 validation method: `docs/assignment3/rafael_summarisation_contribution.md`

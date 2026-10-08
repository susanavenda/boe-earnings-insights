# Rafael — team retrospective contribution

Issue #25 is due 16 October 2026. These notes are Rafael's evidence-based contribution to the group retrospective.

## What worked

- Clear technical ownership helped the project progress: data integration, topic modelling, sentiment, behavioural signals and summarisation had named leads.
- Pull requests and automated tests caught genuine defects before submission, including nullable-answer failures, lost review provenance and unsafe number handling in optional summaries.
- The team retained source identifiers and evidence quotes. This made results auditable and made disagreements discussable at row level.
- Human review materially improved the interpretation of behavioural signals. The two-coder exercise showed which measures were suitable for triage and which still required judgement.
- Treating a well-supported null as a valid result reduced pressure to overclaim a prudential signal.

## What was difficult

- Notebook execution was slow, so feedback sometimes arrived before current outputs were available.
- Different notebook copies and similarly named presentation files created avoidable uncertainty about the authoritative version.
- Some task descriptions were broader than the acceptance criteria, which made it hard to know when work was complete.
- Late integration concentrated presentation and validation work near the deadline.
- Team availability changed from week to week. Earlier notice of each person's realistic capacity would have improved sequencing and reduced urgent hand-offs.

## Start, stop, continue

### Start

- Define one canonical notebook, one canonical deck and one owner for each before development begins.
- Add acceptance criteria, required evidence and review owner when an issue is created.
- Schedule clean-environment and end-to-end runs before the final week.
- Reserve time for independent human coding and disagreement resolution.
- Record decisions that change definitions or denominators in the repository, not only in chat.

### Stop

- Uploading renamed duplicate notebooks instead of modifying the canonical file.
- Treating automatic overlap or keyword metrics as factual accuracy.
- Waiting for presentation week to decide which results are defensible.
- Using a machine status as evidence of management behaviour without checking the Q&A.

### Continue

- Small, focused pull requests with tests and explicit limitations.
- Evidence-first outputs with source IDs, quotations and preserved abstentions.
- Cross-functional review between model owners and business/domain reviewers.
- Reporting limitations and null results alongside positive findings.

## Rafael's contribution and learning

Rafael owned the evidence-grounded summarisation stage and supported behavioural validation as the second independent coder. The summarisation work changed from a broad LLM concept into deterministic metric briefs with explicit abstention, source evidence and optional generation gates. Regression tests were added after reproducing failures involving missing answers, dropped provenance and unsupported figures.

The main learning was that technical safeguards and human review solve different problems. Metric matching and number-preservation checks improve traceability, but they cannot establish whether an answer preserves meaning, addresses the question or changes topic. The final design therefore uses automation to prioritise evidence and human judgement to confirm supervisory interpretation.

## Suggested final retrospective statement

> The team delivered a reproducible evidence pipeline rather than a black-box risk score. Our strongest practice was traceability from every finding back to source text and reported metrics. Our main improvement would be earlier integration: one canonical notebook, earlier clean-environment testing and protected time for independent validation. Those changes would reduce deadline pressure while preserving the multidisciplinary review that made the final conclusions more credible.

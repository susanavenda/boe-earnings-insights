# Rafael — Assignment 3 summarisation contribution

**Working base:** `main` commit `91cb1d6`, 8 October 2026.

**Owner:** Rafael Navas, Stage 4 evidence-grounded metric briefs.

**Current state:** the full notebook and tests pass in GitHub Actions. Rafael's independent M6 behaviour labels have been merged and scored with Bupathi's labels. Stage 4 human validation is prepared but must be completed by Rafael before its results are reported.

## Scope boundary

Stage 4 creates traceable metric briefs for total income, operating costs, credit impairment and CET1. Bupathi owns the separate answering-behaviour measures. A metric mention does not establish answer directness or factual adequacy, so the report must not use Stage 4 labels as behavioural ground truth.

## Changes and rationale

- Require a metric match in every selected evidence sentence.
- Reject optional generative compression when it removes a figure from selected evidence or imports a figure from elsewhere in the Q&A.
- Compare generated text with selected evidence rather than the entire exchange.
- Treat a missing answer as an explicit unanswered case instead of evaluating a pandas missing value as a Boolean.
- Preserve bank and metric fields in the deterministic review sample.
- Store diagnostics as missing when the pipeline abstains. Absence of evidence must not inflate mean quality.
- Describe source-token overlap as a diagnostic rather than factual accuracy.
- Exercise the real notebook helper cell in regression tests without downloading a summarisation model.

## Full-corpus execution evidence

GitHub Actions run `37339787866` completed successfully on commit `63eb56f` in 2 h 29 min 11 s. The executed Stage 4 output contains:

| Measure | Result |
|---|---:|
| Q&A pairs | 1,307 |
| Pair × metric audit rows | 5,228 |
| Relevant metric briefs | 1,362 |
| Answered on metric | 1,020 |
| Answer off metric | 318 |
| Unanswered | 24 |
| Automatic review queue | 366 |

The 366 rows are a triage queue, not a human accuracy score. Human fields remain blank until a reviewer inspects the full question and answer.

## Human validation design

The prepared file `stage4_human_review_rafael.csv` contains 48 deterministic rows: four observations for each of the 12 bank × metric strata. It includes two routine on-metric cases and up to two priority off-metric cases per stratum. One Credit Suisse impairment stratum required a deterministic top-up because only one priority case was available. The sample contains 25 `answered_on_metric` and 23 `answer_off_metric` rows.

Rafael must code the following fields independently from the machine status:

| Field | Coding rule |
|---|---|
| `human_faithful` | `yes` if the brief is supported by the Q&A; `no` if it adds or changes a claim; `n/a` if no brief is present. |
| `human_complete` | `yes` if selected evidence captures the material metric answer; `no` if an important point is omitted; `n/a` if unanswered. |
| `number_or_qualifier_error` | `yes` if a number, unit, direction, horizon or qualifier is wrong or missing; `no` if preserved; `n/a` if none appears. |
| `human_status_correct` | `yes` if the machine status is correct; otherwise `no`. |
| `human_note` | Brief reason for every `no` and any ambiguity. |
| `reviewer` | `Rafael` after the row has been reviewed. |

## Report-ready method text

We summarised analyst Q&A using deterministic extractive briefs for four scoped metrics: total income, operating costs, credit impairment and CET1. Each brief retains the Q&A identifier and source evidence, allowing reviewers to inspect the underlying exchange. Extraction was selected as the primary method because it preserves source wording and limits opportunities to invent financial claims. Optional generative compression is secondary and is rejected when lexical support or number-preservation gates fail.

During refinement, we made the metric-match requirement explicit before ranking sentences. We strengthened the optional compression check to reject omitted figures and numbers imported from unselected parts of the exchange. We also represented diagnostics as missing when no evidence was extracted, handled missing answers safely and retained bank and metric identifiers in sampled review records. Integration tests exercise the notebook cells and verify persistence to SQLite.

Source-token overlap measures lexical support; it does not establish whether a brief preserves meaning, qualifications or completeness. Human validation therefore assesses faithfulness, completeness, number and qualifier preservation, and machine status separately. Missing answers must be checked against the transcript and parser before they are interpreted as management behaviour. The recommended use is evidence triage with human confirmation before supervisory use.

## Results paragraph — complete after Stage 4 human coding

The current full-corpus run produced 1,362 relevant metric briefs from 1,307 Q&A pairs. Of these, 1,020 were classified as answered on metric, 318 as answer off metric and 24 as unanswered. In the deterministic 48-row human sample, **[x/48; x%]** were faithful, **[x/48; x%]** were complete, **[x/48; x%]** contained a number or qualifier error and **[x/48; x%]** had the correct machine status. The most common reviewed error was **[insert coded theme]**. These figures describe the sample only and should not be presented as population accuracy.

## Completed M6 second-coder contribution

Rafael independently coded 90 Q&A pairs before viewing the machine key or Bupathi's labels. Human agreement was 68.9% for addressed, 85.6% for changed topic, 68.9% for metric given and 86.7% for answer cleanliness. Cohen's κ ranged from 0.404 to 0.720. On the 57 agreed yes/no directness cases, the original machine score achieved AUC 0.839. Topic-substitution agreement remained weak, so it should remain human-reviewed. Because the sample oversampled substitution candidates, sample label proportions are not corpus prevalence estimates.

## Remaining Rafael actions

1. Complete all 48 rows in `stage4_human_review_rafael.xlsx` or the equivalent CSV.
2. Calculate the four validation rates and replace the bracketed placeholders above.
3. Run the final clean Colab check and complete `colab_reproducibility.md`.
4. Add the approved slide content from `rafael_final_presentation.md` to the shared deck.
5. Participate in the team retrospective using `rafael_team_retrospective.md`.

## Assignment 3 submission reminder

The group submits a report PDF, presentation-slides PDF, reproducible IPYNB notebook and required CSV files. The 15-minute live presentation must include both a general-audience summary and a technical notebook walkthrough. One designated team member submits for the group.

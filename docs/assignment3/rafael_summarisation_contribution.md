Rafael/Assignment 3 summarisation contribution
Working base: main commit 3ef202e, 3 October 2026. Local branch:
rafael/a3-summary-validation. Proposed changes for review; full Colab execution and human validation remain pending.
Rafael owns Stage 4 evidence-grounded metric briefs. Bupathi owns Stage 3.5
behavioural measures. Summaries can explain behavioural findings, but metric
mention does not establish answer directness or factual adequacy. Confirm the
report-section boundary when Taz shares the outline.
Changes and reasons
- Require a metric match explicitly in each selected evidence sentence. This is
  a clarity improvement: the previous bonuses totalled at most 0.95, below the
  1.0 threshold, so they could not admit a sentence without a metric match.
- Reject optional generative polish if it removes a figure present in the
  extracted evidence, as well as if it introduces an unsupported figure.
  This remains a lexical guard, not a guarantee of factual correctness.
- Compare optional generated text with selected evidence, not the entire Q&A,
  so it cannot borrow an unselected figure belonging to another topic.
- Handle pandas missing text values without evaluating their truth value.
  A missing answer remains an explicit unanswered case.
- Preserve bank and metric fields when sampling the routine review queue.
  The former groupby/apply call removed those fields from sampled rows.
- Store missing support and number-check values for abstentions. The legacy
  script also returns missing overlap for absent metrics. Absence must not raise
  a mean quality score.
- Describe the legacy script's printed score as source-token overlap rather
  than factual accuracy. Retain existing column names for compatibility.
- Add tests that execute the actual notebook helper cell without model downloads.
- Clear old outputs in cells 4.1–4.3 because they predate the changes.
Draft report text — method and refinement
We summarised analyst Q&A using deterministic extractive briefs for four scoped
metrics: income, operating costs, credit impairment and CET1. Each brief retains
the Q&A identifier and source evidence, allowing a reviewer to inspect the
underlying exchange. We selected extraction as the primary method because it
preserves source wording and reduces opportunities to invent financial claims.
Optional generative compression remains secondary and subject to rejection.
During refinement, we made the metric-match requirement explicit before ranking
sentences. We strengthened the optional compression check to reject omitted
figures and numbers imported from unselected parts of the exchange. We also
represented quality diagnostics as missing when no evidence was extracted,
handled missing answer values safely, and retained bank and metric identifiers
in sampled review records. Integration tests exercise the notebook cells and
verify that these records survive persistence to SQLite.
Source-token overlap measures lexical support; it does not establish whether a
brief preserves the meaning, qualifications or complete answer. Consequently,
human validation must assess faithfulness and completeness separately. Missing
answers require inspection of the transcript and parser before being interpreted
as management behaviour. The business recommendation is to use these briefs to
prioritise evidence review, with human confirmation before supervisory use.
Remaining evidence before final submission
Post-review local verification: the repository's non-slow CI command passed with
146 tests, five skipped, three deselected and 85.04% script coverage (80% required).
There was one warning about the existing regex fallback when NLTK punkt is
unavailable. This verifies code behaviour; it is not a fresh full-corpus Colab
execution or a measure of summary accuracy.
Review reproduced three failures before correction: pandas nullable answers
raised an exception; routine review rows lost bank/metric fields; optional
generation accepted a number from outside the selected evidence. Regression
checks now cover all three. Numeric and lexical checks still cannot detect all
changes in meaning, attribution, negation or units. Human review remains required.
1. Run the current full notebook in a fresh Google Colab runtime. Save outputs
   and record the code version, inputs and optional model settings.
2. Review a reproducible sample across banks, periods, metrics and brief statuses.
   Rafael must inspect the original Q&A and record his own assessments. Any
   independent second reviewer should be identified separately.
3. Record faithfulness, completeness, number/qualifier errors, sample size and
   selection procedure. Targeted error cases are not representative accuracy.
4. Select at least three traceable Q&A IDs for each headline finding. Reconcile
   coverage claims with Bupathi's behavioural definitions and denominators.
5. Add verified results to Taz's report outline and prepare a findings slide
   plus a short technical demonstration of cells 4.1–4.3.
Submission requirements from the provided brief
The group report has a suggested 1,500-word structure (200 background, 1,100
development, 200 results). The live presentation is 15 minutes and includes both
a general-audience deck and a technical notebook walkthrough. Deliver report
and slides as PDF, a reproducible Google Colab notebook as IPYNB, and data files
as CSV. The group's SQLite working store does not replace the required CSV
submission files. One designated member submits for the group.

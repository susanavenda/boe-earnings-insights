# M6 coding guide — answering behaviour (4 questions)

Code each pair **on your own** and **without** opening `behaviour_90_machine_key.csv`
(the hidden machine key). Copy `behaviour_90_labels_template.csv` to
`behaviour_90_labels_<yourname>.csv` and fill one row per pair. Do not discuss pairs with
the other coder until you have both finished.

You are judging **how management answered**, not whether the news was good or bad
(that is sentiment, M4). Judge only the text shown. No looking things up.

## The four questions

### 1. `addressed` — did the answer address what was asked?
| value | use when |
|---|---|
| `yes` | answers the main question directly |
| `partly` | answers some of it (e.g. one of two questions), or only vaguely |
| `no` | does not answer it: deflects, general commentary, "we don't guide on that" |

Two questions in one turn: judge the **lead** question; mention the other in `note`.

### 2. `changed_topic` — did the answer move to a different subject?
| value | use when |
|---|---|
| `yes` | talks mainly about something else (asked about CET1, answered about revenue) |
| `no` | stays on the subject, even if it does not fully answer |

### 3. `metric_given` — if a specific metric was asked about, was it given?
Metrics in scope: **total income / revenue / NII, operating costs, credit impairment / ECL, CET1 / capital ratio / RWAs.**
| value | use when |
|---|---|
| `yes` | the answer gives a number, a direction or guidance for that metric |
| `no` | the metric was asked about but the answer does not provide it |
| `na` | the question did not ask about one of these metrics |

### 4. `answer_clean` — is the answer text only management's reply to this question?
| value | use when |
|---|---|
| `yes` | the A: text is management answering this question |
| `no` | the A: text also contains another analyst's question, an operator line, or is garbled |

If `answer_clean = no`, still code questions 1–3 on the part that is management's
reply to this question.

## Worked example
> **Q:** "Can you give us an update on the CET1 ratio and whether buybacks continue in H2?"
> **A:** "Revenue momentum was strong across all divisions, with fee income up 8%..."

| addressed | changed_topic | metric_given | answer_clean | note |
|---|---|---|---|---|
| no | yes | no | yes | |

## Rules
- When unsure, pick the closest value and add a `note`. Do not leave label cells blank.
- Courtesy ("thanks for the question") carries nothing; ignore it.
- Allow about 4.9–5.6 hours for 90 pairs (roughly 46,000 words to read). Three sittings is fine.

Scoring: `python scripts/score_behaviour_human.py` (human-vs-human κ and machine-vs-human).

> **Canonical submission:** `Group9_CAM_EP_Assignment1.pdf` / `.docx`  
> This markdown mirrors that document so repo copies stay aligned. Do not treat the old placeholder draft as live.

# Assignment 1: Project Scope and Plan

**Employer project with the Bank of England (Group 9).** Defines the overarching research question, bank scope, team operating model, milestone plan, and NLP approach for extracting prudential signal from G-SIB earnings announcements and analyst Q&A.

Cambridge Data Science Career Accelerator · Susana Venda (Topic modelling lead) · Group 9 · 2026

| | |
|---|---|
| Banks | HSBC · Barclays |
| Milestones | A1–A4 |
| Tracking | GitHub project with 26 dated issues |
| Methods | BERTopic · FinBERT+LDSA · LLM summarisation |

---

## Executive summary

*Not counted toward the 1,000-word limit — front matter only.*

**Business context.** The Bank of England's Prudential Regulation Authority needs earlier warning of prudential stress than structured regulatory returns alone provide. The BoE brief leaves bank count, topics, metrics, and success criteria open; Group 9 closes that gap with one explicit research question.

**Scope.** HSBC and Barclays, analysed via BERTopic, FinBERT+LDSA sentiment, and metric-grouped LLM summarisation, evaluated against three self-defined baselines.

**Recommendation.** Execute against the GitHub roadmap with named owners per issue and weekly monitoring checkpoints, treating the deliverable as a repeatable pipeline rather than a one-off read.

---

## 1. Background, context and problem statement

The Bank of England's Prudential Regulation Authority (PRA) supervises around 1,500 firms. Its most accessible data is structured — regulatory returns, financial statements. Its least accessible is unstructured: quarterly earnings calls and the analyst Q&A that follows them, hard to use because they are text and video, not tables, and because they require financial domain knowledge to interpret correctly. The Bank's brief leaves bank count, topics, metrics and success criteria open.

**Problem statement:** can NLP and generative AI extract topic-level, sentiment-level and summary-level signal from G-SIB earnings call transcripts that the PRA can use for early risk assessment?

**Overarching question:** do quarterly earnings announcements and analyst Q&A carry a leading signal about a firm's prudential condition that reported financial metrics alone don't capture?

Scope is locked to **HSBC and Barclays** — UK-incorporated, under full PRA oversight, with complete public Q&A transcripts across enough quarters. US banks and Santander are excluded on regulatory-regime and comparability grounds; a third, US-based bank for geopolitical comparison remains a live, undecided discussion. In scope: BERTopic clustering of Q&A themes, FinBERT combined with LDSA sentiment per theme, summarisation grouped by metric, and refined topic modelling on the clusters that matter. Out of scope: video/webcast processing, **fine-tuning models from scratch**, and peer benchmarking beyond the two named banks (stretch only).

| Item | Decision |
|---|---|
| Banks | HSBC and Barclays — UK-incorporated, full PRA oversight, complete public Q&A transcripts |
| Excluded | US banks and Santander — different regulatory regimes, less comparable data |
| Open question | Third, US-based bank for geopolitical comparison — undecided, live in group chat |
| In scope | BERTopic clustering; FinBERT+LDSA sentiment; summarisation by metric; refined topic modelling |
| Out of scope | Video/webcast processing; fine-tuning from scratch; peer benchmarking beyond HSBC/Barclays (stretch) |

*Table 1. Scope decisions agreed at kick-off.*

**Observations:** This targets the Bank's own stated interest directly — early warning signals not visible in structured reporting alone — and its mission of monetary and financial stability.

---

## 2. Team roles and ways of working

**Seven of us:** Aidan, Alfred, Bupathi, Debanjan, Rafael, Susana Venda, Taz — one above the programme's suggested four to six, workable only if every person owns something named. Roles are assigned by strength: Alfred leads sentiment (FinBERT+LDSA); Susana Venda leads topic modelling (BERTopic); Taz coordinates cadence, agendas, minutes and the roadmap (rotates if needed). Data/pipeline, summarisation, business & regulatory research, and editor/QA ownership remain pending confirmation alongside Belbin profiles.

Channels: WhatsApp (day-to-day) · video calls (decisions) · Google Drive (files) · GitHub (code, Alfred) · Miro (roadmap) · email (tutor contact). Cadence: two calls a week plus async updates; **24-hour response norm** on weekdays; meetings in the UK/CET/US overlap.

Decisions: WhatsApp poll → 5–10 min timebox → component owner decides → full team if scope/deadline affected. Feedback at each milestone (SBI). Contribution: one named owner and date per deliverable on the shared board. Escalation: direct SBI → full team → Cambridge success team.

| Role | Owner | Belbin | Responsibility |
|---|---|---|---|
| Coordinator | Taz | Coordinator/Implementer | Cadence, agendas, minutes, roadmap; rotates if needed |
| Sentiment lead | Alfred | Specialist/Plant/Shaper | FinBERT + LDSA |
| Topic modelling lead | Susana Venda | — | BERTopic |
| Data/pipeline | Pending | — | Sourcing and preprocessing transcripts |
| Summarisation lead | Pending | — | LLM summarisation pipeline |
| Business & regulatory research | Pending | — | BoE/PRA context, Porter's Five Forces |
| Editor / QA | Pending | — | Shared document, word count, PDF export, submission |

*Table 2. Role allocation and Belbin behavioural mapping.*

| Working agreement | Detail |
|---|---|
| Channels | WhatsApp · video · Google Drive · GitHub · Miro · email (tutor) |
| Cadence | Two calls/week + async; 24-hour weekday response; UK/CET/US overlap |
| Decisions | Poll → timebox → owner decides → escalate if scope/deadline |
| Feedback | At milestones; Situation–Behaviour–Impact |
| Contribution | Named owner + date per deliverable |
| Escalation | SBI → full team → Cambridge success team |

*Table 3. PREACH working agreements.*

---

## 3. Project plan

Five life-cycle phases against fixed dates and a live GitHub project (four milestones, twenty-six dated issues).

| Phase | Dates | Key activities | Milestone |
|---|---|---|---|
| Initiation | 7 Sep | Kick-off: banks/questions, PREACH, roles, actions logged | Kick-off complete |
| Planning | 8–14 Sep | Roadmap, Porter's Five Forces, draft sections, consolidate to ~1,000 words, review vs marking guide | **A1 by midday 14 Sep** |
| Execution | 15 Sep–12 Oct | Topic modelling + sentiment → preliminary pitch; summarisation + evaluation → final report | **A2: 28 Sep · A3: 12 Oct** |
| Monitoring & control | Ongoing | Weekly GitHub roadmap checkpoints; same-day blockers | — |
| Closure | 13–19 Oct | Retrospective; individual reflections | **A4: 19 Oct** |

*Table 4. Project life-cycle phases mapped to fixed dates.*

| Risk | Mitigation |
|---|---|
| No BoE-defined success criterion or baseline | Self-defined baselines: **temporal**, **peer**, **structured-vs-unstructured**. Divergence or null is a valid finding |
| Transcript availability unverified | Checked before scope finalised |
| Member jury service from 14 Sep | Named ownership so absence doesn't block a single-owner task |
| Uneven early engagement | Named ownership + escalation path in §2 |

*Table 5. Risk register and mitigation.*

**Observations:** The most consequential risk — no defined baseline — is resolved by the team, converting a gap in the brief into a methodological strength (§4).

---

## 4. Approach

| Stage | Method | Output |
|---|---|---|
| 1. Topic modelling | BERTopic on analyst Q&A (data-driven themes) | Theme clusters |
| 2. Sentiment | FinBERT + LDSA, per topic cluster | Sentiment per theme |
| 3. Summarisation | LLM pipeline, grouped by metric | Metric-level summaries |
| 4. Refinement | Repeat topic modelling on clusters that matter | Focused theme set |

*Table 6. Four-stage analytical pipeline.*

Evaluation uses the three baselines in §3, not a single accuracy figure. Hand-validate a sample of topic and sentiment labels; report FinBERT's known weakness on hedged bank language explicitly. Tooling: VS Code / Cursor with Jupyter locally (not Colab); code on GitHub; report in one shared Google Doc, mirrored in the repo.

**Key finding:** The deliverable is a **repeatable pipeline**, not a one-off read: the final report states what re-running it next quarter costs and what a PRA supervisor would see — covering both a positive and a null result.

---

## Appendix: Project roadmap

Live GitHub Projects Roadmap (issues, labels, milestones) maps onto Table 4. See `docs/project/GitHub_Project_Setup.md` and `docs/project/issues.csv`.

**Word count:** ~1,000 words (prose across numbered sections, excluding tables, captions and executive summary, per the brief).

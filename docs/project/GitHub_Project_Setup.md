# GitHub setup — Bank of England employer project

## 1. Repository

Create one shared repo for the team, e.g. `boe-earnings-insights`.

Suggested structure (matches this repo):
```
/notebooks                 — Jupyter analysis (boe_earnings_insights.ipynb)
/data/raw/transcripts      — HSBC / Barclays Q&A PDFs
/data/structured           — Excel packs / financial tables
/data/processed            — pipeline CSV / chart outputs
/docs/assignment1          — Assignment Word/PDF deliverables
/docs/project              — issues.csv, GitHub setup notes
/docs/assets               — roadmap images
/scripts                   — label / milestone / issue helpers
README.md                  — problem statement, team, how to run
```

Add all teammates as collaborators (Settings → Collaborators), or create a GitHub org/team if you want tighter permissions.

## 2. Milestones (map 1:1 to the graded assignments)

Go to **Issues → Milestones → New milestone** and create four, using the real due dates:

| Milestone | Due date |
|---|---|
| A1 — Scope & plan | 14 Sep |
| A2 — Solution pitch | 28 Sep |
| A3 — Final report | 12 Oct |
| A4 — Reflection | 19 Oct |

## 3. Labels

Beyond GitHub's defaults, add:
- `phase:initiation` (gray)
- `phase:execution` (teal)
- `phase:closure` (purple)
- `milestone` (amber) — for the deadline-marker issues themselves
- `data`, `modelling`, `writing`, `presentation` — by workstream type

## 4. Issues to create, grouped by milestone

Create one issue per row. Assign each to the matching milestone above, and to whichever teammate owns it once roles are decided.

**Milestone: A1 — Scope & plan (due 14 Sep)**
- [ ] Kick-off meeting — review BoE brief, share availability/skills
- [ ] Agree team roles, communication plan, meeting cadence
- [ ] Complete Porter's Five Forces activity (1.3.4)
- [ ] Draft problem statement and project scope
- [ ] Build project roadmap (this doc's companion visual)
- [ ] Write and submit Assignment 1 PDF

**Milestone: A2 — Solution pitch (due 28 Sep)**
- [ ] Source transcripts/reports from chosen bank(s)' investor relations pages
- [ ] Clean and preprocess transcript text (speaker segmentation)
- [ ] Build topic modelling pipeline (BERTopic, baseline vs. Gensim LDA)
- [ ] Build sentiment/emotion analysis pipeline (FinBERT)
- [ ] Draft preliminary findings
- [ ] Build and record presentation deck (15 min)

**Milestone: A3 — Final report (due 12 Oct)**
- [ ] Build LLM summarisation pipeline (by topic/metric/speaker)
- [ ] Evaluate models (metrics + qualitative accuracy check)
- [ ] Refine based on Assignment 2 feedback
- [ ] Write final report (1,500 words)
- [ ] Prepare final live presentation deck

**Milestone: A4 — Reflection (due 19 Oct)**
- [ ] Team retrospective
- [ ] Each member writes individual reflection (500 words)

## 5. Turning this into a visual Roadmap

1. Go to your repo → **Projects** tab → **New project** → choose the **Board** template, then add a new view.
2. On the new view, click **View → Layout → Roadmap**.
3. Add two custom fields: **Start date** and **Target date** (Date type). Set Target date = the milestone due date for each issue.
4. Group by **Milestone** or **Label (phase)** so the four phases show as swimlanes.
5. Turn on milestone markers (vertical lines) in the Roadmap settings so 14 Sep / 28 Sep / 12 Oct / 19 Oct show up as visible deadlines on the timeline.

This gives you a live, draggable version of the roadmap graphic already built for Assignment 1 — and it doubles as your actual task tracker for the rest of the project.

## 6. For the Assignment 1 Appendix

Once the board is populated, switch to Roadmap view, take a screenshot, and drop it into the Appendix of your Assignment 1 document in place of the static image.

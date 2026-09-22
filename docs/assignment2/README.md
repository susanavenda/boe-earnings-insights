# Assignment 2

**Sell:** repeatable supervisory **automation pipeline** (IR → alert/watch/null pack).  
Desk UI = output surface · Notebook/scripts = factory.

| File | Use |
|---|---|
| [`A2_pitch_outline.md`](A2_pitch_outline.md) | **15-min run-of-show** with named speakers (Taz · Susana · Debanjan · Alfred · Bupathi · Rafael · Aidan). |
| [`A2_checklist.md`](A2_checklist.md) | Submit + dry-run checklist |
| [`label_agreement.json`](label_agreement.json) | FinBERT vs hand-sample gold (sentiment) |
| [`human_labels/`](human_labels/) | **Aidan M2a dual-code** · Debanjan/Alfred topics · Rafael metric briefs. Headline: machine vs machine **35%**. |
| [`eval_bar_literature.md`](eval_bar_literature.md) | Hunter: is 70% / n=60 defensible? Literature vs the live 35%/50% scores (no code). |
| [`pra_notes/pra_notes.md`](pra_notes/pra_notes.md) | PRA one-pagers |
| Notebook Stages 7–9 | Technical walkthrough + machine vs Aidan score |
| Notebook Stage 10.2 | Yahoo press, **filtered** to own-results headlines (bank as subject + earnings/results/profit/quarter). Small n / zero kept is expected. |

**Canvas submit:** PDF slides + MP4 recording only.

---

## Pipeline (what you sell)

```text
IR PDFs + Excel → segment → topics + sentiment → baselines → alert/watch/null → PRA + desk
```

Re-run next quarter: ~45–90 min. Recalibration gated (not continuous).

## Config (env vars, not a yaml)

There is no `config.yaml`. Roots and the database are resolved at run time:

| Var | Role |
|---|---|
| `BOE_ROOT` / `COLAB_ROOT` | Factory root if cwd is not already the repo |
| `BOE_DB` | SQLite path (default `data/boe.sqlite`) |
| `BOE_EXPORT_CSV` | `1` to also write CSV mirrors |
| `BOE_GEMINI_MODEL` / `BOE_LLM_PROVIDER` | Optional Stage 3.1c |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` | Process env or gitignored `.env` — never commit |

Printed `INPUT raw= /Users/...` lines are captured stdout from one machine, not hardcoded source.

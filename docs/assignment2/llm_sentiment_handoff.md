# Handoff — two LLM sentiment pipelines (Stage 3.8 / 3.9)

**Owner:** Alfred (Qianyi) · sentiment lane · branch `alfred/sentiment-pipeline`
**For:** whichever agent/LLM implements this next. Read this whole file, then `scripts/sentiment.py` and `scripts/finetune_sentiment.py`, before writing code.
**Status (23 Sep):** a first pass of Pipeline B exists — Claude labelled all 1,826 texts in-session (batches of 40, guide verbatim, K=0, blind) → `docs/assignment2/llm_sentiment_labels.csv`, and `score_sentiment_human.py` already reports it as the `llm` unit. The script in §2 should reproduce that via an API so it is re-runnable next quarter; Pipeline C can train on the existing CSV now.

**Deadline context:** A2 pitch due Mon 28 Sep 17:00 UK. Both pipelines are **optional extras** — they must skip cleanly without an API key and must not change any number the deck already quotes.

---

## 0. What you are building, in one paragraph each

**Pipeline B — `llm_score`: LLM as annotator.** An LLM reads every Q&A pair (question and answer separately), applies the *same* coding guide the human coders use, and returns negative / neutral / positive with a confidence and a one-line rationale. Results land in `qa_pairs` and `corpus_analyst` as `llm_*` columns with the same shape as the FinBERT columns, are cached in SQLite so re-runs are free, and are scored against the human gold by the existing scorer next to FinBERT-turn, FinBERT-sentence and Loughran–McDonald. This supersedes the 20-row Stage 3.1c comparison (leave 3.1c alone; it is Susana's and the deck references it).

**Pipeline C — `llm_distill`: LLM as teacher, FinBERT as student.** Take the LLM labels from B on the whole corpus, fine-tune FinBERT on them (same light recipe as Stage 3.4: head, then last two layers), hold the human gold out, and run it through the same promotion gate. This is "learn": the transformer learns the LLM's judgement so the pipeline can re-run next quarter without an API call. A1 scope allows light adaptation of an existing model; it does not allow training from scratch — so the student is FinBERT, not a new model.

Both are **candidates**. Nothing is promoted unless it beats zero-shot FinBERT on human gold by the existing gate (n ≥ 40, macro-F1 + 0.05). The pitch line, if it exists at all, is "LLM annotator agrees X% with human gold vs FinBERT Y%" — a comparison, not a replacement claim.

---

## 1. Repo conventions you must follow

| Convention | Where to look | Rule |
|---|---|---|
| State lives in SQLite, files are inputs | `scripts/store.py` | `from store import configure, load_df, save_df, save_json, has_df`. Call `configure(memory=False)` — **never** pass a hard-coded path; `BOE_DB` env var selects the DB. |
| One text normaliser | `scripts/sentiment.py` → `normalise_for_sentiment`, `build_vocab`, `management_names_from_turns` | Score the *normalised* text, never rewrite the stored `text` / `question_text` / `answer_text`. |
| Column contract | `sentiment.py` docstring | Turn-level FinBERT columns (`finbert_sentiment / _score / _net`, `question_sentiment`, `answer_sentiment` …) are read by Stage 6/8 and the demo desk. **Do not rename, reorder or overwrite them.** Add new columns only. |
| Human gold is sacred | `docs/assignment2/human_labels/sentiment_60_labels_*.csv` | Read-only. Never write, regenerate or "correct" them. Never feed the LLM the machine key. |
| Keys | `scripts/compare_llm_sentiment.py` → `load_dotenv`, `_provider` | Reuse these. Keys come from process env or gitignored repo-root `.env`. `GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`; `BOE_LLM_PROVIDER` overrides. Never print a key, never commit `.env`. |
| Scripts are the factory, notebook calls them | `scripts/score_qa_sentiment.py` is the pattern | Script with `main()` + argparse; notebook cell imports and calls it, or `subprocess.run([sys.executable, script])` then `_hydrate()`. |
| Notebook helpers | Stage 0 cell of `notebooks/boe_earnings_insights.ipynb` | `section_header`, `kpi_row`, `insight(kind='key'|'info'|'warn')`, `display_table`, `_df`, `_save`, `_load`, `_has`, `_has_json`, `_load_json`, `_flush`, `_hydrate`, `ROOT`, `DOCS_ROOT`. Edit the notebook at JSON level (see `nbformat`), clear outputs only on cells you touch, run `nbformat.validate`. |
| Commits | git log | Author = Alfred; message body explains *why*; end with the `Co-Authored-By` trailer used on the branch. Never commit `data/*.sqlite`, `models/`, `.env`. |
| Honesty | `docs/assignment2/eval_bar_literature.md`, `A2_pitch_outline.md` Slide 7 | Silver ≠ gold. Report agreement *with human gold* or say "no human gold yet". Never quote LLM-vs-FinBERT agreement as accuracy. |

---

## 2. Pipeline B — `scripts/llm_score_sentiment.py`

### 2.1 Interface

```
python scripts/llm_score_sentiment.py [--provider gemini|openai|anthropic] [--model NAME]
                                      [--n N] [--side question|answer|both] [--rerun]
                                      [--exemplars K] [--dry-run]
```

- Default provider/model: whatever `compare_llm_sentiment._provider()` resolves; default models `gemini-3.6-flash`, `gpt-4o-mini`, `claude-haiku-4-5` (env overrides `BOE_GEMINI_MODEL`, `BOE_OPENAI_MODEL`, `BOE_ANTHROPIC_MODEL`).
- No key → print one line and `sys.exit(0)`. The notebook cell must show `insight(..., kind='info')` and continue.
- `--n` scores a prefix (for smoke tests); default = all 1,002 pairs.
- `--dry-run` builds prompts, prints token/cost estimate, calls nothing.

### 2.2 Prompt — same rubric as the humans

System prompt = the **verbatim** body of `docs/assignment2/human_labels/sentiment_coding_guide.md` from "## What you are labelling" through rule 8. Load it from the file at run time; do not paste a paraphrase (the point is that machine and humans use one rubric).

User turn, per text:

```
SIDE: question | answer
BANK: hsbc | barclays   QUARTER: 2025-interim
TEXT:
<normalised text, clipped to 4,000 chars>

Reply with JSON only: {"label": "negative|neutral|positive", "confidence": "high|medium|low", "rationale": "<one sentence>"}
```

Temperature 0. `max_tokens` ~120. Parse with `json.loads` after stripping code fences; on parse failure fall back to `compare_llm_sentiment._parse_label` on the raw text and set `llm_parse_ok=0`.

**Few-shot exemplars (`--exemplars K`, default 0 for A2):** only from rows that have a human label, and those `pair_id`s must be **excluded from evaluation** (write them to `docs/assignment2/human_labels/llm_exemplar_ids.json`; `score_sentiment_human.py` must drop them for the `llm` unit). If no coder file exists, K is forced to 0. Never use the machine key as exemplars.

Score question and answer as **separate calls** (M4 wants separate fields; also avoids the answer contaminating the question label). Skip empty answers (label `""`).

### 2.3 Cache

Table `llm_sentiment_cache` via `save_df` — but append-only semantics: load existing, concat new rows, drop duplicates on `(provider, model, prompt_hash, text_hash)`, save. `prompt_hash` = sha1 of system prompt + exemplar ids; `text_hash` = sha1 of the normalised text. A re-run with the same prompt and text makes zero API calls. `--rerun` ignores the cache.

Rate limiting: batch requests with a small thread pool (≤4), exponential backoff on 429/5xx, at most 3 retries, then record `llm_error` and move on. Print a progress line every 100 texts.

### 2.4 Output columns (added to `qa_pairs`; mapped onto `corpus_analyst` via the question side)

```
question_llm_label, question_llm_confidence, question_llm_rationale, question_llm_net
answer_llm_label,   answer_llm_confidence,   answer_llm_rationale,   answer_llm_net
llm_provider, llm_model, llm_parse_ok, llm_error
```

`*_llm_net` = +1 / 0 / −1 × {high: 1.0, medium: 0.67, low: 0.33} so it averages like the FinBERT nets. On `corpus_analyst`, add `llm_sentiment`, `llm_net`, `llm_confidence`, `llm_rationale` (from the question side, joined on normalised text[:120] like `finetune_sentiment._key`).

Also `save_json("llm_sentiment_run", {...})` with provider, model, n scored, n cached, n errors, wall time, estimated cost, exemplar ids.

### 2.5 Cost / time (say this in the docstring)

≈ 1,900 non-empty texts × ~600 input tokens ≈ 1.2 M input tokens + ~0.2 M output. Gemini Flash / GPT-4o-mini / Haiku: well under $1. With 4 threads ≈ 10–15 min. Colab/laptop friendly.

---

## 3. Pipeline C — `scripts/distill_sentiment.py`

### 3.1 What it does

1. Requires B to have run (`question_llm_label` on `qa_pairs`; `llm_sentiment` on `corpus_analyst`). Otherwise exit 0 with a one-line message.
2. Training set = analyst turns with an LLM label **and no human label**. Human-labelled rows are held out exactly as `finetune_sentiment.py` does — **refactor** the training/eval machinery out of `finetune_sentiment.py` into functions (`build_datasets`, `train_light`, `evaluate`) and import them; do not copy-paste 200 lines.
3. Same recipe: `ProsusAI/finbert`, head-only 8 epochs lr 5e-4, then layers 10–11 + head 4 epochs lr 2e-5, class-weighted CE, seed 42, `max_length 256`, text = `normalise_for_sentiment`.
4. Evaluate on (a) a 25 % stratified split of the LLM-labelled set (audit — "does the student reproduce the teacher") and (b) human gold (the gate). Report zero-shot FinBERT, the LLM teacher itself, and the student on the same human rows.
5. Save weights to `models/finbert-llm-distilled/` (gitignored). Score the whole corpus → `distill_sentiment`, `distill_score` on `corpus_analyst`; `question_distill_label` / `answer_distill_label` on `qa_pairs` (score answers too — the student can, FinBERT-style).
6. `save_json("distill_metrics", {...})` mirroring `finetune_metrics`, and update `model_registry`: add candidate `finbert-llm-distilled`; set `active_model_id` **only** via the same gate (`MIN_HUMAN=40`, `MARGIN=0.05`, vs zero-shot on human gold). If two candidates pass, pick the higher human macro-F1 and record both.

### 3.2 Interface

```
python scripts/distill_sentiment.py [--device cpu|cuda] [--epochs-head 8] [--epochs-top 4]
```

---

## 4. Evaluation wiring (small, mandatory)

- `scripts/score_sentiment_human.py`: extend `MACHINE_UNITS` with
  `"llm": ("question_llm_label", "answer_llm_label")` and
  `"distilled": ("question_distill_label", "answer_distill_label")`.
  Units whose columns are absent are already skipped. For `llm`, drop `llm_exemplar_ids.json` pairs before scoring. Add both to the `headline` block and the pitch line.
- `scripts/build_sentiment_gold_pack.py`: include the `*_llm_*` and `*_distill_*` columns in the hidden key **if present** — the key is agreement-only; coders never see it.
- `scripts/label_agreement.py`: nothing to change — it already calls the scorer and exports `finetune_metrics`; add `distill_metrics` and `llm_sentiment_run` to the export loop (three-line change).

---

## 5. Notebook cells (after Stage 3.7)

**3.8 — LLM annotator (optional).** Markdown: what it is, that it uses the human coding guide verbatim, skips without a key, and is a candidate not a replacement. Code: import the script, run with the notebook's DB, `kpi_row` with n scored / n cached / n errors / provider, `display_table` of 8 rows (`pair_id, question_llm_label, question_sentiment, question_sent_label, question_llm_rationale`), `insight` that agreement with FinBERT is *not* accuracy. If `sentiment_agreement.json` has coders, show the `llm` row from `machine_vs_human`.

**3.9 — Distilled FinBERT (optional).** Same shape as the 3.4 cell: KPI row (teacher n, student train/dev, human held-out, zero-shot vs teacher vs student macro-F1 on human gold, `active_model_id`), confusion matrices, promotion reason. Runs the script via `subprocess` with `_flush()` before and `_hydrate()` after, like 3.4 does.

Both cells: `FORCE_LLM = False` / `FORCE_DISTILL = False` guards; use cached results when the JSON docs exist.

---

## 6. Acceptance checklist (run these, paste the output in the PR)

```bash
# 0. environment
pip install -r requirements.txt          # add google-generativeai / openai / anthropic as OPTIONAL extras with a comment
python -m py_compile scripts/llm_score_sentiment.py scripts/distill_sentiment.py scripts/finetune_sentiment.py scripts/score_sentiment_human.py

# 1. no key → clean skip
env -u GEMINI_API_KEY -u OPENAI_API_KEY -u ANTHROPIC_API_KEY python scripts/llm_score_sentiment.py   # exits 0, one line
python scripts/distill_sentiment.py                                                                  # exits 0, one line

# 2. dry run and smoke
python scripts/llm_score_sentiment.py --dry-run                     # prints n texts, token + cost estimate, no calls
python scripts/llm_score_sentiment.py --n 20                        # 40 calls, cache populated
python scripts/llm_score_sentiment.py --n 20                        # 0 API calls (cache hit) — assert in output

# 3. full run + scoring
python scripts/llm_score_sentiment.py
python scripts/score_sentiment_human.py                             # 'llm' unit appears (or 'awaiting labels')
python scripts/distill_sentiment.py --device cpu
python scripts/label_agreement.py                                   # exports distill_metrics + llm run

# 4. nothing existing moved
python - <<'EOF'
import sys; sys.path.insert(0,'scripts'); from store import configure, load_df; configure(memory=False)
c = load_df('corpus_analyst'); print(c['finbert_sentiment'].value_counts().to_dict())   # must equal the pre-run counts
EOF
git status --short                                                  # no data/*.sqlite, models/, .env staged
```

Expected shape of a good result: LLM agrees with human gold at least as well as FinBERT-sentence on the pooled set; the student lands between zero-shot and the teacher. If the LLM is *worse* than FinBERT on human gold, report it — that is a finding, not a failure.

---

## 7. Things not to do

- Do not touch Stage 3.1c (`compare_llm_sentiment.py`, notebook cell 3.1c) beyond importing `load_dotenv` / `_provider` / `_parse_label`.
- Do not change the FinBERT turn-level columns, `DEAD_ZONE`, or the gold pack sampling.
- Do not let the LLM see any machine label, the machine key, or another coder's labels.
- Do not use human-labelled pairs as few-shot exemplars and then evaluate on them (leakage). Exclude or K=0.
- Do not write the pitch numbers into `A2_pitch_outline.md` yourself — leave a line in the PR description with the `sentiment_agreement.json` headline and let Alfred/Taz place it.
- Do not add the API SDKs as hard requirements; guard imports inside the provider functions.

---

## 8. Definition of done

- [ ] `scripts/llm_score_sentiment.py`, `scripts/distill_sentiment.py` exist, documented, `py_compile` clean.
- [ ] `finetune_sentiment.py` refactored into importable functions; its own behaviour and outputs unchanged (re-run gives the same `finetune_metrics` shape).
- [ ] `score_sentiment_human.py` reports `llm` and `distilled` units when present.
- [ ] Notebook has 3.8 and 3.9 cells, validated with `nbformat`, other cells' outputs untouched.
- [ ] Acceptance checklist output pasted in the PR.
- [ ] PR description states: provider/model used, cost, n scored, human-gold agreement per unit (or "awaiting labels"), and `active_model_id` after the gate.

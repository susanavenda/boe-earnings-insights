#!/usr/bin/env python3
"""M6 — build the 90-pair human coding pack for the behavioural signals.

Why this exists: sentiment (M4), topics and the eight-way map (M7) each have human
labels. M6 (directness, metric coverage, topic substitution) was only *computed*.
This pack lets two coders judge the same pairs by hand, with machine scores hidden,
so scripts/score_behaviour_human.py can report human-vs-human and machine-vs-human agreement.

The sample is stratified on the machine M6 values so every signal gets enough cases:
substitution "yes" is rare (about 1 in 5 measurable pairs) and would be starved by a
random draw. Rates in the scorer therefore describe the sample, not the corpus.

Writes (docs/assignment2/human_labels/):
  behaviour_coding_guide.md          how to code (four questions, worked example)
  behaviour_90_for_coding.md         Q + A per pair, no machine values
  behaviour_90_labels_template.csv   one row per pair for a coder to fill
  behaviour_90_machine_key.csv       hidden key: pair text + machine values at build time
  behaviour_90_sample_meta.json      strata, seed, exclusions

Usage:
  python scripts/build_behaviour_gold_pack.py                       # qa_pairs from data/boe.sqlite
  python scripts/build_behaviour_gold_pack.py --rebuild-from-pdfs   # re-parse PDFs in memory (stale sqlite)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_a1_evidence import behavioural_signals, event_type_from_source, pair_qa  # noqa: E402
from periods import period_sort_key  # noqa: E402

OUT = ROOT / "docs" / "assignment2" / "human_labels"
RAW = ROOT / "data" / "raw" / "transcripts"
BANKS = ("hsbc", "barclays")  # A1 scope; Credit Suisse is out-of-sample
MIN_WORDS = 12
# Longest ~10% of pairs (Q + A words); almost all are several answer turns merged,
# and they would push one coding pass past four hours. Keeps every subst_yes pair.
MAX_WORDS = 1200

# 90 pairs, agreed with Taz (was 60): matches the M4 sentiment pack size.
N_PAIRS = 90
PACK = f"behaviour_{N_PAIRS}"
# Words a coder reads per hour, from the 60-pair pilot (about 32,000 words in 3–3.5 hours).
WORDS_PER_HOUR = 9500

# Primary stratum targets for n=90 (scaled for other n). Assigned in this order, so a
# pair counts once: substitution first (scarcest), then coverage, then directness.
STRATA = {
    "subst_yes": 22,
    "subst_no": 14,
    "coverage_no": 15,
    "coverage_yes": 12,
    "directness_low": 14,
    "directness_high": 13,
}

GUIDE = """# M6 coding guide — answering behaviour (4 questions)

Code each pair **on your own** and **without** opening `{pack}_machine_key.csv`
(the hidden machine key). Copy `{pack}_labels_template.csv` to
`{pack}_labels_<yourname>.csv` and fill one row per pair. Do not discuss pairs with
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
- Allow about {hours} hours for {n} pairs (roughly {words:,} words to read). Three sittings is fine.

Scoring: `python scripts/score_behaviour_human.py` (human-vs-human κ and machine-vs-human).
"""


def rebuild_pairs_from_pdfs(raw: Path = RAW) -> pd.DataFrame:
    """Stage 1.2–1.5 in memory: PDFs → turns → Q&A pairs → M6. Writes nothing."""
    import pdfplumber
    from segment_transcripts import infer_bank, infer_quarter, segment_transcript

    turns = []
    for path in sorted(raw.rglob("*.pdf")):
        with pdfplumber.open(path) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        bank = infer_bank(path)
        df = segment_transcript(text, bank)
        if df.empty:
            continue
        df["bank"] = bank
        df["quarter"] = infer_quarter(path)
        df["source"] = path.name
        df["event_type"] = event_type_from_source(path.name)
        turns.append(df)
    qa = pair_qa(pd.concat(turns, ignore_index=True))
    qa["event_type"] = qa["source"].map(event_type_from_source)
    return behavioural_signals(qa)


def load_pairs_from_store() -> pd.DataFrame:
    from store import configure, load_df

    configure(memory=False)
    qa = load_df("qa_pairs")
    # Recompute M6 with the current code so strata match what the scorer will see.
    return behavioural_signals(qa)


def eligible_pool(qa: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = qa.copy()
    df["question_text"] = df["question_text"].fillna("").astype(str)
    df["answer_text"] = df["answer_text"].fillna("").astype(str)
    dup = df["pair_id"].duplicated(keep=False)
    q_words = df["question_text"].str.split().str.len()
    a_words = df["answer_text"].str.split().str.len()
    event = df["event_type"] if "event_type" in df.columns else df["source"].map(event_type_from_source)
    mode = df["pair_mode"] if "pair_mode" in df.columns else pd.Series("consecutive", index=df.index)
    rules = {
        "out_of_scope_bank": ~df["bank"].isin(BANKS),
        "not_results_call": event != "results_call",
        "duplicate_pair_id": dup,
        "empty_answer": df["answer_text"].str.strip() == "",
        "bleed_split": mode == "bleed_split",
        "short_question": q_words < MIN_WORDS,
        "short_answer": a_words < MIN_WORDS,
        "too_long": (q_words + a_words) > MAX_WORDS,
    }
    keep = pd.Series(True, index=df.index)
    excluded = {}
    for name, mask in rules.items():
        excluded[name] = int((keep & mask).sum())  # counted in order, so no double counting
        keep &= ~mask
    return df[keep].copy(), excluded


def assign_stratum(pool: pd.DataFrame) -> pd.Series:
    meas = pool["substitution_measurable"].fillna(False).astype(bool)
    sub = pd.to_numeric(pool["topic_substitution"], errors="coerce")
    cov = pd.to_numeric(pool["metric_coverage"], errors="coerce")
    rest = ~meas & cov.isna()
    d = pd.to_numeric(pool["directness"], errors="coerce")
    lo, hi = d[rest].quantile([1 / 3, 2 / 3]) if rest.any() else (np.nan, np.nan)
    s = pd.Series("directness_mid", index=pool.index)
    s[rest & (d <= lo)] = "directness_low"
    s[rest & (d >= hi)] = "directness_high"
    s[~meas & (cov == 1)] = "coverage_yes"
    s[~meas & (cov == 0)] = "coverage_no"
    s[meas & (sub == 0)] = "subst_no"
    s[meas & (sub == 1)] = "subst_yes"
    return s


def sample_pairs(qa: pd.DataFrame, n: int = N_PAIRS, seed: int = 2026) -> tuple[pd.DataFrame, dict]:
    pool, excluded = eligible_pool(qa)
    pool["stratum"] = assign_stratum(pool)
    scale = n / sum(STRATA.values())
    targets = {k: int(round(v * scale)) for k, v in STRATA.items()}
    targets["directness_high"] += n - sum(targets.values())  # rounding remainder
    rng = np.random.default_rng(seed)

    picked = []
    for stratum, k in targets.items():
        s = pool[pool["stratum"] == stratum]
        got = []
        for bank, kb in ((BANKS[0], k // 2), (BANKS[1], k - k // 2)):
            b = s[s["bank"] == bank]
            take = min(kb, len(b))
            if take:
                got.append(b.loc[rng.choice(b.index.to_numpy(), size=take, replace=False)])
        got = pd.concat(got) if got else s.iloc[0:0]
        short = k - len(got)
        if short > 0:  # one bank ran out: fill from the other bank in the same stratum
            rest = s.drop(got.index)
            if len(rest):
                got = pd.concat([got, rest.loc[rng.choice(rest.index.to_numpy(), size=min(short, len(rest)), replace=False)]])
        picked.append(got)
    out = pd.concat(picked)
    if len(out) < n:  # a whole stratum was short: top up from anything left
        rest = pool.drop(out.index)
        out = pd.concat([out, rest.loc[rng.choice(rest.index.to_numpy(), size=min(n - len(out), len(rest)), replace=False)]])

    # Coders see pairs in time order per bank, so the stratum cannot be inferred.
    out["_ord"] = out["quarter"].map(period_sort_key)
    out = out.sort_values(["bank", "_ord", "pair_id"]).drop(columns="_ord")
    meta = {
        "n": int(len(out)),
        "seed": seed,
        "banks": list(BANKS),
        "pool_size": int(len(pool)),
        "excluded_in_order": excluded,
        "strata_target": targets,
        "strata_actual": {k: int(v) for k, v in out["stratum"].value_counts().items()},
        "strata_available": {k: int(v) for k, v in pool["stratum"].value_counts().items()},
        "by_bank": {k: int(v) for k, v in out["bank"].value_counts().items()},
        "note": (
            "Stratified on machine M6 values (substitution first, then coverage, then directness "
            "terciles), balanced by bank. Substitution 'yes' is oversampled, so agreement rates "
            "describe this sample, not corpus prevalence. Excludes Credit Suisse, non-results-call "
            "events, duplicate pair_ids, empty or bleed-split answers, turns under "
            f"{MIN_WORDS} words and pairs over {MAX_WORDS} words (mostly merged answer turns). "
            "Coders see Q and A only."
        ),
    }
    return out, meta


def write_pack(sample: pd.DataFrame, meta: dict, out_dir: Path = OUT) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    pack = f"behaviour_{len(sample)}"
    words = int((sample["question_text"].str.split().str.len() + sample["answer_text"].str.split().str.len()).sum())
    lo = words / WORDS_PER_HOUR
    hours = f"{lo:.1f}–{lo * 1.15:.1f}"
    guide = GUIDE.format(pack=pack, n=len(sample), words=round(words, -3), hours=hours)
    (out_dir / "behaviour_coding_guide.md").write_text(guide, encoding="utf-8")

    lines = [
        f"# M6 answering-behaviour coding pack (n={len(sample)})",
        "",
        f"Code each pair on your own using `behaviour_coding_guide.md`. Do not open `{pack}_machine_key.csv`.",
        f"Fill a copy of `{pack}_labels_template.csv` saved as `{pack}_labels_<yourname>.csv`.",
        "",
    ]
    for r in sample.to_dict("records"):
        lines += [
            f"### PAIR {r['pair_id']}",
            f"bank={r['bank']} quarter={r['quarter']} analyst={r.get('analyst') or ''}",
            f"Q: {str(r['question_text']).strip()}",
            f"A: {str(r['answer_text']).strip()}",
            "",
        ]
    (out_dir / f"{pack}_for_coding.md").write_text("\n".join(lines), encoding="utf-8")

    pd.DataFrame(
        {
            "pair_id": sample["pair_id"].to_numpy(),
            "addressed": "",
            "changed_topic": "",
            "metric_given": "",
            "answer_clean": "",
            "note": "",
        }
    ).to_csv(out_dir / f"{pack}_labels_template.csv", index=False)

    # Text is in the key so the scorer can recompute M6 with whatever code is current.
    key = sample[["pair_id", "source", "bank", "quarter", "stratum", "question_text", "answer_text"]].copy()
    for col in ("directness", "metric_coverage", "topic_substitution", "substitution_measurable"):
        key[f"built_{col}"] = sample[col].to_numpy()
    key.to_csv(out_dir / f"{pack}_machine_key.csv", index=False)
    (out_dir / f"{pack}_sample_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=N_PAIRS)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--rebuild-from-pdfs", action="store_true", help="re-parse PDFs in memory instead of reading sqlite")
    ap.add_argument("--dry-run", action="store_true", help="print the sample meta, write nothing")
    args = ap.parse_args()
    qa = rebuild_pairs_from_pdfs() if args.rebuild_from_pdfs else load_pairs_from_store()
    sample, meta = sample_pairs(qa, n=args.n, seed=args.seed)
    meta["source"] = "pdfs (in-memory rebuild)" if args.rebuild_from_pdfs else "data/boe.sqlite qa_pairs"
    meta["corpus_pairs"] = int(len(qa))
    print(json.dumps(meta, indent=2))
    if not args.dry_run:
        write_pack(sample, meta)
        print(f"wrote {OUT / f'behaviour_{len(sample)}_for_coding.md'}")


if __name__ == "__main__":
    main()

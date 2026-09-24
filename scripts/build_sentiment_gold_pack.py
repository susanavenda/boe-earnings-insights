#!/usr/bin/env python3
"""M4 — build the 60-pair human sentiment coding pack (machine labels hidden).

Why this exists: Aidan's 60-pair dual-code is the 8-way *category* test. Nobody has
hand-labelled *sentiment*, and ``docs/hand_validation_sample.csv`` seeded its gold
from FinBERT itself (100% "agreement"). M4 says ≥70% agreement with humans on a
60-pair stratified sample, with separate question and answer sentiment — so the
pack has both, and the coder never sees the machine columns.

Writes (docs/assignment2/human_labels/):
  sentiment_coding_guide.md         how to code (3 labels; hedging rules)
  sentiment_60_for_coding.md        Q + A per pair, no machine labels
  sentiment_60_labels_template.csv  one row per pair for a coder to fill
  sentiment_60_machine_key.csv      hidden key (FinBERT turn + sentence, LM)
  sentiment_60_sample_meta.json     strata, seed, exclusions

Usage:
  python scripts/build_sentiment_gold_pack.py                       # 60 stratified
  python scripts/build_sentiment_gold_pack.py --reuse-m2a --topup 30  # Aidan's 60 + 30 non-neutral (default for A2)
Requires qa_pairs scored by scripts/sentiment.py --qa (turn + sentence columns).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from periods import calendar_period, period_sort_key  # noqa: E402
from store import configure, load_df  # noqa: E402

OUT = ROOT / "docs" / "assignment2" / "human_labels"
LABELS = ("negative", "neutral", "positive")
EPISODE_QUARTERS = {("hsbc", "2025-interim"), ("barclays", "2026-q2"), ("hsbc", "2024-interim"), ("hsbc", "2026-interim")}

GUIDE = """# Sentiment coding guide (M4 — 3 labels, question and answer separately)

Code each pair **independently** and **without** opening any machine label file
(`sentiment_60_machine_key.csv` is the hidden key). Fill `sentiment_60_labels_template.csv`
— one row per pair, save as `sentiment_60_labels_<yourname>.csv`.

## What you are labelling

The **stance toward the bank's prudential condition or outlook** that the text carries —
not politeness, not whether the speaker is friendly, not whether the number is big.

| Label | Question (analyst) | Answer (management) |
|---|---|---|
| **negative** | Probes a concern: deterioration, pressure, risk, miss, capital/credit/cost worry, scepticism about guidance | Concedes weakness, guides down, flags headwinds, impairment/cost pressure, uncertainty that is clearly adverse |
| **positive** | Frames improvement or strength (rarely — analysts mostly probe) | Asserts strength, improvement, confidence, guides up, beat, resilience |
| **neutral** | Asks for detail, mechanics, clarification, breakdown, timing; no stance | Explains mechanics, restates facts, mixed with no net direction, declines to comment |

## Rules for hedged bank language

1. **Hedged is not automatically neutral.** "We are cautious about the second half given
   what we're seeing in impairments" is **negative** even though it is polite and qualified.
   Label the direction the hedge points.
2. **Mixed with a net direction → that direction.** "Costs are up but income more than
   covers it" → positive. Balanced with no net → neutral.
3. **Courtesy is ignored.** "Thanks for taking my question, good morning" carries nothing.
4. **Questions:** label the *concern the analyst expresses*, not the topic. "Can you walk us
   through the NII bridge?" → neutral. "Why is the NII guide so much weaker than peers?" → negative.
5. **Answers:** label the *message about the metric / outlook*. "We don't guide on that" → neutral.
   "We expect impairments to normalise higher" → negative. "We're very confident in the 12% RoTE" → positive.
6. **Truncated or bleed text:** label what is there. If fewer than ~2 sentences of usable
   content, set `confidence=low` and still give your best label.
7. **Two questions in one turn:** label the *lead* ask; note the other in `note`.
8. Do not use a fourth class. Do not label "avoidance" — that is M6 (behaviour), not sentiment.

## Columns

| column | values |
|---|---|
| `pair_id` | as given |
| `q_label` | negative / neutral / positive |
| `a_label` | negative / neutral / positive (leave blank only if the answer is empty) |
| `confidence` | high / medium / low |
| `note` | free text, optional |

Aim for one sitting (~45–60 min). Two coders → we report raw %, Cohen's κ and Krippendorff's α
(`python scripts/score_sentiment_human.py`).
"""


def _period_bucket(q: str) -> str:
    y = int(str(q)[:4]) if str(q)[:4].isdigit() else 0
    if y >= 2024:
        return "2024+"
    if y >= 2020:
        return "2020-23"
    return "pre-2020"


def _machine_stance(row: pd.Series) -> str:
    """Stratum label for the answer side: union of turn + sentence machine labels.

    Anything either unit calls non-neutral goes into that class (so the sample carries
    the cases where the two units disagree, which is exactly what the gold must settle).
    """
    t = str(row.get("answer_sentiment") or "neutral")
    s = str(row.get("answer_sent_label") or t)
    if t == "negative" or s == "negative":
        return "negative"
    if t == "positive" or s == "positive":
        return "positive"
    return "neutral"


def sample_pairs(
    qa: pd.DataFrame,
    n: int = 60,
    seed: int = 42,
    *,
    reuse_ids: Sequence[str] | None = None,
    topup: int = 0,
) -> tuple[pd.DataFrame, dict]:
    """Draw the coding sample.

    Default: ``n`` pairs stratified on the machine answer stance (thirds), balanced by bank.
    With ``reuse_ids`` (e.g. Aidan's M2a 60): those pairs form the core — same units for
    category and sentiment, so coder-vs-coder κ is comparable across both tasks — and
    ``topup`` extra pairs are drawn from the machine-negative/positive strata only, because
    a category-stratified sample carries almost no negatives (3 of Aidan's 60).
    """
    df = qa.copy().drop_duplicates("pair_id")
    df["answer_text"] = df["answer_text"].fillna("")
    df["question_text"] = df["question_text"].fillna("")
    excl = {
        "empty_answer": int((df["answer_text"].str.strip() == "").sum()),
        "bleed_split": int((df.get("pair_mode", "") == "bleed_split").sum()),
        "short_question": int((df["question_text"].str.split().str.len() < 12).sum()),
    }
    df["stratum_label"] = df.apply(_machine_stance, axis=1)
    df["period_bucket"] = df["quarter"].map(_period_bucket)
    df["is_episode"] = [(b, q) in EPISODE_QUARTERS for b, q in zip(df["bank"], df["quarter"])]
    df["sample_role"] = ""
    pool = df[
        (df["answer_text"].str.strip() != "")
        & (df.get("pair_mode", "consecutive") != "bleed_split")
        & (df["question_text"].str.split().str.len() >= 12)
        & (df["answer_text"].str.split().str.len() >= 12)
    ].copy()

    rng = np.random.default_rng(seed)
    picks = []
    core = pd.DataFrame()
    if reuse_ids:
        core = df[df["pair_id"].isin(set(map(str, reuse_ids)))].copy()
        core["sample_role"] = "reused_m2a"
        pool = pool[~pool["pair_id"].isin(core["pair_id"])]
        # top-up goes to the non-neutral class the core is short of, in proportion
        c_neg = int((core["stratum_label"] == "negative").sum())
        c_pos = int((core["stratum_label"] == "positive").sum())
        k_neg = int(round(topup * (c_pos / (c_pos + c_neg)))) if (c_pos + c_neg) else topup // 2
        per_label = {"negative": k_neg, "positive": topup - k_neg}
    else:
        # target: equal thirds by machine stance, balanced across banks; recent + episode quarters first
        per_label = {"negative": n // 3, "positive": n // 3, "neutral": n - 2 * (n // 3)}
    for lab, k in per_label.items():
        if k <= 0:
            continue
        sub = pool[pool["stratum_label"] == lab]
        for bank, kb in (("hsbc", k // 2), ("barclays", k - k // 2)):
            s = sub[sub["bank"] == bank].copy()
            if s.empty:
                continue
            # weight: episode quarters ×3, 2024+ ×2, 2020-23 ×1.5, else 1
            w = np.where(s["is_episode"], 3.0, 1.0) * s["period_bucket"].map({"2024+": 2.0, "2020-23": 1.5, "pre-2020": 1.0}).to_numpy()
            take = min(kb, len(s))
            idx = rng.choice(s.index.to_numpy(), size=take, replace=False, p=w / w.sum())
            picked = s.loc[idx].copy()
            picked["sample_role"] = "stratified_topup" if reuse_ids else "stratified"
            picks.append(picked)
    out = pd.concat([core, *picks]) if len(core) else pd.concat(picks)
    # top up if a stratum was short (default mode only)
    if not reuse_ids and len(out) < n:
        rest = pool.drop(out.index)
        extra = rest.sample(n=min(n - len(out), len(rest)), random_state=seed)
        extra["sample_role"] = "stratified"
        out = pd.concat([out, extra])
    out = out.sample(frac=1.0, random_state=seed)  # shuffle so coder can't infer strata
    out["_ord"] = out["quarter"].map(period_sort_key)
    out = out.sort_values(["bank", "_ord", "pair_id"]).drop(columns="_ord")
    meta = {
        "n": int(len(out)),
        "seed": seed,
        "mode": "reuse_m2a_plus_topup" if reuse_ids else "stratified",
        "n_reused": int((out["sample_role"] == "reused_m2a").sum()),
        "n_topup": int((out["sample_role"] == "stratified_topup").sum()),
        "pool_size": int(len(pool)),
        "excluded": excl,
        "strata_target": per_label,
        "strata_actual": {k: int(v) for k, v in out["stratum_label"].value_counts().items()},
        "strata_actual_core": {k: int(v) for k, v in core["stratum_label"].value_counts().items()} if len(core) else None,
        "by_bank": {k: int(v) for k, v in out["bank"].value_counts().items()},
        "by_period_bucket": {k: int(v) for k, v in out["period_bucket"].value_counts().items()},
        "episode_pairs": int(out["is_episode"].sum()),
        "core_empty_answers": int((core["answer_text"].str.strip() == "").sum()) if len(core) else 0,
        "note": (
            "Core = Aidan's M2a pair_ids (same units for category and sentiment; coder-vs-coder κ comparable), "
            "plus a machine-negative/positive top-up so negative recall is measurable. Coder sees Q and A only; "
            "leave a_label blank where the answer is empty."
            if reuse_ids
            else "Stratified on the machine answer stance (union of FinBERT turn + sentence labels) so "
            "negatives/positives are not starved; excludes empty answers, bleed_split pairs and "
            "very short turns. Coder sees Q and A only."
        ),
    }
    return out, meta


def write_pack(sample: pd.DataFrame, meta: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sentiment_coding_guide.md").write_text(GUIDE, encoding="utf-8")

    lines = [
        "# Human sentiment labelling pack (n=%d)" % len(sample),
        "",
        "Code each pair independently — question **and** answer — using `sentiment_coding_guide.md`.",
        "Do not open `sentiment_60_machine_key.csv`. Fill `sentiment_60_labels_template.csv`.",
        "Where `A: (empty)` — the parser found no answer — leave `a_label` blank and code the question only.",
        "",
    ]
    for r in sample.to_dict("records"):
        lines += [
            f"### PAIR {r['pair_id']}",
            f"bank={r['bank']} quarter={r['quarter']} analyst={r.get('analyst') or ''}",
            f"Q: {str(r['question_text']).strip()}",
            f"A: {str(r['answer_text']).strip() or '(empty)'}",
            "",
        ]
    (OUT / "sentiment_60_for_coding.md").write_text("\n".join(lines), encoding="utf-8")

    pd.DataFrame(
        {"pair_id": sample["pair_id"], "q_label": "", "a_label": "", "confidence": "", "note": ""}
    ).to_csv(OUT / "sentiment_60_labels_template.csv", index=False)

    key_cols = [
        "pair_id", "bank", "quarter", "sample_role", "stratum_label", "period_bucket", "is_episode",
        "question_sentiment", "question_net", "question_net_prob", "question_sent_label", "question_sent_net",
        "question_ldsa_sentiment", "question_ldsa_net", "question_lm_hedge",
        "answer_sentiment", "answer_net", "answer_net_prob", "answer_sent_label", "answer_sent_net",
        "answer_ldsa_sentiment", "answer_ldsa_net", "answer_lm_hedge",
    ]
    key_cols = [c for c in key_cols if c in sample.columns]
    sample[key_cols].to_csv(OUT / "sentiment_60_machine_key.csv", index=False)
    (OUT / "sentiment_60_sample_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--reuse-m2a", action="store_true", help="core = pair_ids in human_labels/m2a_aidan_labels.csv")
    ap.add_argument("--topup", type=int, default=30, help="extra machine-negative/positive pairs when --reuse-m2a")
    args = ap.parse_args()
    configure(memory=False)
    qa = load_df("qa_pairs")
    need = {"question_sentiment", "answer_sentiment"}
    if not need.issubset(qa.columns):
        raise SystemExit("qa_pairs has no machine sentiment — run: python scripts/sentiment.py --qa")
    reuse = None
    if args.reuse_m2a:
        m2a = OUT / "m2a_aidan_labels.csv"
        if not m2a.is_file():
            raise SystemExit(f"{m2a} missing — cannot reuse the M2a pair_ids")
        reuse = pd.read_csv(m2a)["pair_id"].astype(str).tolist()
    sample, meta = sample_pairs(qa, n=args.n, seed=args.seed, reuse_ids=reuse, topup=args.topup if reuse else 0)
    write_pack(sample, meta)
    print(json.dumps(meta, indent=2))
    print(f"wrote {OUT / 'sentiment_60_for_coding.md'} and friends")


if __name__ == "__main__":
    main()

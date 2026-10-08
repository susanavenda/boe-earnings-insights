"""Round-2 human sentiment pack: new pairs neither coder has seen (M4, second kappa).

Round 1 (sentiment_90_*) was coded before the answer-side rule was tightened (4 Oct).
Re-coding only the round-1 disagreements cannot give a fair kappa (the agreed pairs
cannot move), so round 2 draws fresh pairs, coded blind by both coders under the
current ``sentiment_coding_guide.md``.

Same pool rules and stratification as round 1 (``build_sentiment_gold_pack.sample_pairs``):
non-empty answers, no bleed-split pairs, thirds by machine answer stance, balanced by bank.
Excludes every round-1 pair and any pair_id that appears more than once in ``qa_pairs``.

Writes (docs/assignment2/human_labels/):
  sentiment_r2_for_coding.md        Q + A per pair, no machine or human labels
  sentiment_r2_labels_template.csv  one row per pair; save as sentiment_r2_labels_<name>.csv
  sentiment_r2_machine_key.csv      hidden key - coders do not open
  sentiment_r2_sample_meta.json     strata, seed, exclusions
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_sentiment_gold_pack import OUT, sample_pairs  # noqa: E402
from store import configure, load_df  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=43)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    configure(memory=False)
    qa = load_df("qa_pairs")
    qa = qa[qa["bank"].isin(["barclays", "hsbc"])]
    used: set[str] = set()
    for name in ("sentiment_90_machine_key.csv", "sentiment_60_machine_key.csv"):
        p = OUT / name
        if p.is_file():
            used |= set(pd.read_csv(p, dtype=str)["pair_id"])
    dup = set(qa.loc[qa["pair_id"].duplicated(keep=False), "pair_id"])
    pool = qa[~qa["pair_id"].isin(used | dup)]
    sample, meta = sample_pairs(pool, n=args.n, seed=args.seed)
    assert not set(sample["pair_id"]) & used
    meta.update({"round": 2, "excluded_round1_pairs": len(used), "excluded_duplicate_pair_ids": len(dup)})

    lines = [
        "# Human sentiment labelling pack - round 2 (n=%d, new pairs)" % len(sample),
        "",
        "Code each pair independently and blind - question **and** answer - using the current",
        "`sentiment_coding_guide.md`, including the section **Answer-side rule** at the end",
        "(score what is new in the answer, not how confident it sounds).",
        "Do not open `sentiment_r2_machine_key.csv`, any `llm_sentiment_labels*.csv`, or another coder's file.",
        "Fill `sentiment_r2_labels_template.csv` and save as `sentiment_r2_labels_<name>.csv`.",
        "If the answer text is garbled (another analyst's question, boilerplate), label the management",
        "content that is there and set `confidence=low`.",
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
    (OUT / "sentiment_r2_for_coding.md").write_text("\n".join(lines), encoding="utf-8")
    pd.DataFrame(
        {"pair_id": sample["pair_id"], "q_label": "", "a_label": "", "confidence": "", "note": ""}
    ).to_csv(OUT / "sentiment_r2_labels_template.csv", index=False)
    key_cols = [c for c in sample.columns if c in {
        "pair_id", "bank", "quarter", "sample_role", "stratum_label", "period_bucket", "is_episode",
    } or c.startswith(("question_sent", "question_net", "question_ldsa", "question_lm",
                       "answer_sent", "answer_net", "answer_ldsa", "answer_lm"))]
    sample[key_cols].to_csv(OUT / "sentiment_r2_machine_key.csv", index=False)
    (OUT / "sentiment_r2_sample_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(json.dumps(meta, indent=2, default=str))


if __name__ == "__main__":
    main()

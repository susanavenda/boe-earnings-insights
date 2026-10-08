#!/usr/bin/env python3
"""M4 - human-vs-human and FinBERT-vs-human kappa on one basis, plus the #85 sensitivity check.

Answers two report questions with the published label files only (no re-labelling):
  * Is FinBERT's agreement with a human (published: 90 pairs, question + answer pooled, whole-turn
    FinBERT vs coder 1, kappa 0.28) close to how well the two humans agree with each other?
  * Does it hold without the nine round-1 pairs whose answer text got shorter after coding
    (issue #85: a follow-up question was split out into its own pair)?

Basis: blind first-pass labels (sentiment_90_labels_<coder>.csv; round 2 as first coded, i.e. before
any review change in sentiment_r2_review_changes_<coder>.csv), FinBERT whole-turn label from each
pack's machine key, Cohen's kappa over the three classes. "pooled" stacks question and answer labels.
Bootstrap intervals resample pairs (question and answer stay together).

Writes docs/assignment2/human_labels/sentiment_kappa_summary.json and store doc ``sentiment_kappa_summary``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from store import configure, save_json  # noqa: E402

HL = ROOT / "docs" / "assignment2" / "human_labels"
OUT = HL / "sentiment_kappa_summary.json"
LABELS = ["negative", "neutral", "positive"]
CODERS = ("alfred", "taz")
# Issue #85: round-1 gold pairs whose answer_text is shorter than when they were coded.
ISSUE_85 = [
    "hsbc_2020-annual_004", "hsbc_2020-interim_007", "hsbc_2021-interim_005", "hsbc_2021-q1_001",
    "hsbc_2022-q3_001", "hsbc_2023-q3_002", "hsbc_2024-interim_006", "hsbc_2024-interim_007",
    "hsbc_2025-q1_009",
]


def _norm(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().str.lower()


def coder(pack: str, name: str) -> pd.DataFrame:
    df = pd.read_csv(HL / f"sentiment_{pack}_labels_{name}.csv", dtype=str).fillna("").set_index("pair_id")
    df = df[["q_label", "a_label"]].apply(_norm)
    rc = HL / f"sentiment_{pack}_review_changes_{name}.csv"
    if rc.is_file():  # undo post-review edits: the blind first pass is the comparable basis
        for r in pd.read_csv(rc, dtype=str).fillna("").to_dict("records"):
            df.at[r["pair_id"], r["field"]] = r["blind"].strip().lower()
    return df


def finbert(pack: str) -> pd.DataFrame:
    k = pd.read_csv(HL / f"sentiment_{pack}_machine_key.csv", dtype=str).fillna("").drop_duplicates("pair_id").set_index("pair_id")
    return pd.DataFrame({"q_label": _norm(k["question_sentiment"]), "a_label": _norm(k["answer_sentiment"])})


def stack(df: pd.DataFrame, ids, side: str) -> np.ndarray:
    if side == "question":
        return df["q_label"].reindex(ids).fillna("").values
    if side == "answer":
        return df["a_label"].reindex(ids).fillna("").values
    return np.concatenate([stack(df, ids, "question"), stack(df, ids, "answer")])


def kappa(a: pd.DataFrame, b: pd.DataFrame, ids, side: str) -> dict:
    x, y = stack(a, ids, side), stack(b, ids, side)
    m = np.isin(x, LABELS) & np.isin(y, LABELS)
    return {"n": int(m.sum()), "raw": round(float((x[m] == y[m]).mean()), 3),
            "kappa": round(float(cohen_kappa_score(x[m], y[m], labels=LABELS)), 3)}


def main() -> None:
    configure(memory=False)
    packs = {p: {"alfred": coder(p, "alfred"), "taz": coder(p, "taz"), "finbert": finbert(p)} for p in ("90", "r2")}
    ids = {p: list(packs[p]["alfred"].index) for p in packs}
    both = {who: pd.concat([packs["90"][who], packs["r2"][who]]) for who in ("alfred", "taz", "finbert")}
    sets = {
        "round1_90": (packs["90"], ids["90"]),
        "round1_minus_issue85": (packs["90"], [p for p in ids["90"] if p not in ISSUE_85]),
        "round2_43_blind": (packs["r2"], ids["r2"]),
        "both_rounds_blind": (both, ids["90"] + ids["r2"]),
    }
    res: dict = {"basis": "blind first-pass labels; FinBERT whole-turn; Cohen's kappa, 3 classes", "issue_85_pairs": ISSUE_85, "sets": {}}
    for name, (lab, pids) in sets.items():
        res["sets"][name] = {
            side: {
                "alfred_vs_taz": kappa(lab["alfred"], lab["taz"], pids, side),
                "finbert_vs_alfred": kappa(lab["finbert"], lab["alfred"], pids, side),
                "finbert_vs_taz": kappa(lab["finbert"], lab["taz"], pids, side),
            }
            for side in ("pooled", "question", "answer")
        }
    # bootstrap (by pair) on the published round-1 pooled basis
    rng = np.random.default_rng(0)
    lab, pids = sets["round1_90"]
    pids = np.array(pids)
    draws = {"alfred_vs_taz": [], "finbert_vs_alfred": [], "finbert_vs_taz": [], "humans_minus_finbert_alfred": []}
    for _ in range(2000):
        s = rng.choice(pids, len(pids), replace=True)
        hh = kappa(lab["alfred"], lab["taz"], s, "pooled")["kappa"]
        fa = kappa(lab["finbert"], lab["alfred"], s, "pooled")["kappa"]
        draws["alfred_vs_taz"].append(hh)
        draws["finbert_vs_alfred"].append(fa)
        draws["finbert_vs_taz"].append(kappa(lab["finbert"], lab["taz"], s, "pooled")["kappa"])
        draws["humans_minus_finbert_alfred"].append(hh - fa)
    res["round1_pooled_bootstrap_95ci"] = {k: [round(float(q), 2) for q in np.percentile(v, [2.5, 97.5])] for k, v in draws.items()}
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    save_json("sentiment_kappa_summary", res)
    for name, block in res["sets"].items():
        for side, d in block.items():
            print(f"{name:22s} {side:8s} " + "  ".join(f"{k} {v['raw']:.0%}/k{v['kappa']:.2f} (n={v['n']})" for k, v in d.items()))
    print("round-1 pooled 95% CI:", res["round1_pooled_bootstrap_95ci"])
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""M4 — score human sentiment labels against FinBERT (turn + sentence) and LM.

Reads docs/assignment2/human_labels/sentiment_60_labels_*.csv (one file per coder,
columns pair_id, q_label, a_label, confidence, note) and the hidden machine key.

Reports, per side (question / answer) and pooled:
  * raw % agreement, Cohen's κ, macro-F1, per-class recall, confusion — machine vs human
    for each machine unit (FinBERT turn, FinBERT sentence, LM lexicon)
  * coder-vs-coder raw %, κ, Krippendorff's α (nominal) when ≥2 coders
  * Krippendorff's α across all coders + each machine unit (is the machine "another coder"?)

Human gold = majority across coders when ≥2 (ties → first-listed coder); single coder otherwise.

Writes docs/assignment2/human_labels/sentiment_agreement.json and store table
``sentiment_agreement``. Nothing here retrains or promotes a model — it produces the
number the promotion gate reads.
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix, f1_score, recall_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from store import configure, save_df, save_json  # noqa: E402

HL = ROOT / "docs" / "assignment2" / "human_labels"
KEY = HL / "sentiment_60_machine_key.csv"
OUT_JSON = HL / "sentiment_agreement.json"
LABELS = ["negative", "neutral", "positive"]
M4_BAR = 0.70

MACHINE_UNITS = {
    "finbert_turn": ("question_sentiment", "answer_sentiment"),
    "finbert_sentence": ("question_sent_label", "answer_sent_label"),
    "lm_lexicon": ("question_ldsa_sentiment", "answer_ldsa_sentiment"),
}


def _norm(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().str.lower().replace({"nan": "", "none": ""})


def krippendorff_alpha_nominal(rows: list[list[str | None]]) -> float | None:
    """Krippendorff's α (nominal) for units × coders with missing values allowed."""
    coincidence: Counter = Counter()
    n_total = 0.0
    for unit in rows:
        vals = [v for v in unit if isinstance(v, str) and v]
        m = len(vals)
        if m < 2:
            continue
        # coincidence matrix: each ordered pair (i≠j) within a unit contributes 1/(m-1)
        for i, a in enumerate(vals):
            for j, b in enumerate(vals):
                if i != j:
                    coincidence[(a, b)] += 1.0 / (m - 1)
        n_total += m
    if n_total < 2:
        return None
    cats = sorted({c for pair in coincidence for c in pair})
    n_c = {c: sum(v for (a, _), v in coincidence.items() if a == c) for c in cats}
    Do = sum(v for (a, b), v in coincidence.items() if a != b)
    De = sum(n_c[a] * n_c[b] for a in cats for b in cats if a != b) / (n_total - 1)
    if De == 0:
        return None
    return float(1.0 - Do / De)


def load_coders() -> dict[str, pd.DataFrame]:
    coders = {}
    for f in sorted(glob.glob(str(HL / "sentiment_60_labels_*.csv"))):
        name = Path(f).stem.replace("sentiment_60_labels_", "")
        if name == "template":
            continue
        df = pd.read_csv(f, dtype=str).fillna("")
        if not {"pair_id", "q_label", "a_label"}.issubset(df.columns):
            print(f"skip {f}: needs pair_id, q_label, a_label")
            continue
        df["q_label"] = _norm(df["q_label"])
        df["a_label"] = _norm(df["a_label"])
        filled = int(((df["q_label"] != "") | (df["a_label"] != "")).sum())
        if filled == 0:
            print(f"skip {f}: no labels filled in")
            continue
        coders[name] = df.set_index("pair_id")
    return coders


def majority(labels: list[str]) -> str:
    labels = [l for l in labels if l in LABELS]
    if not labels:
        return ""
    c = Counter(labels).most_common()
    if len(c) > 1 and c[0][1] == c[1][1]:
        return labels[0]  # tie → first-listed coder
    return c[0][0]


def block(y_true: pd.Series, y_pred: pd.Series, name: str) -> dict:
    m = (y_true.isin(LABELS)) & (y_pred.isin(LABELS))
    yt, yp = y_true[m].tolist(), y_pred[m].tolist()
    if not yt:
        return {"name": name, "n": 0}
    return {
        "name": name,
        "n": len(yt),
        "raw_agreement": float(accuracy_score(yt, yp)),
        "cohen_kappa": float(cohen_kappa_score(yt, yp, labels=LABELS)) if len(set(yt) | set(yp)) > 1 else None,
        "macro_f1": float(f1_score(yt, yp, average="macro", labels=LABELS, zero_division=0)),
        "recall_by_class": dict(zip(LABELS, [float(x) for x in recall_score(yt, yp, average=None, labels=LABELS, zero_division=0)])),
        "confusion_true_rows_pred_cols": confusion_matrix(yt, yp, labels=LABELS).tolist(),
        "meets_m4_bar": bool(accuracy_score(yt, yp) >= M4_BAR),
    }


def main() -> None:
    configure(memory=False)
    if not KEY.is_file():
        raise SystemExit("machine key missing — run scripts/build_sentiment_gold_pack.py first")
    key = pd.read_csv(KEY, dtype={"pair_id": str}).set_index("pair_id")
    for c in key.columns:
        if c.endswith(("_sentiment", "_label")):
            key[c] = _norm(key[c])
    coders = load_coders()
    if not coders:
        print(
            "No filled coder files yet (docs/assignment2/human_labels/sentiment_60_labels_<name>.csv). "
            "Machine key is ready; nothing scored."
        )
        summary = {"n_coders": 0, "status": "awaiting human labels", "m4_bar": M4_BAR, "n_pairs": int(len(key))}
        OUT_JSON.write_text(json.dumps(summary, indent=2))
        save_json("sentiment_agreement", summary)
        return

    names = list(coders)
    pairs = key.index
    gold = pd.DataFrame(index=pairs)
    for side, col in (("question", "q_label"), ("answer", "a_label")):
        gold[side] = [majority([coders[n][col].get(p, "") for n in names]) for p in pairs]

    results: dict = {
        "n_coders": len(names),
        "coders": names,
        "n_pairs": int(len(pairs)),
        "m4_bar": M4_BAR,
        "gold_rule": "majority across coders; tie → first-listed coder" if len(names) > 1 else "single coder",
        "human_label_dist": {
            side: {k: int(v) for k, v in gold[side].value_counts().items()} for side in ("question", "answer")
        },
        "machine_vs_human": {},
        "coder_vs_coder": {},
        "krippendorff_alpha": {},
    }

    # machine vs human, per unit, per side + pooled
    for unit, (qcol, acol) in MACHINE_UNITS.items():
        if qcol not in key.columns or acol not in key.columns:
            continue
        r = {
            "question": block(gold["question"], key[qcol], f"{unit}_question"),
            "answer": block(gold["answer"], key[acol], f"{unit}_answer"),
            "pooled": block(
                pd.concat([gold["question"], gold["answer"]], ignore_index=True),
                pd.concat([key[qcol], key[acol]], ignore_index=True),
                f"{unit}_pooled",
            ),
        }
        results["machine_vs_human"][unit] = r

    # coder vs coder
    if len(names) > 1:
        for a, b in combinations(names, 2):
            for side, col in (("question", "q_label"), ("answer", "a_label")):
                results["coder_vs_coder"][f"{a}_vs_{b}_{side}"] = block(
                    coders[a][col].reindex(pairs), coders[b][col].reindex(pairs), f"{a}_vs_{b}_{side}"
                )

    # Krippendorff α: humans only, and humans + each machine unit
    for side, col in (("question", "q_label"), ("answer", "a_label")):
        human_rows = [[coders[n][col].get(p, "") or None for n in names] for p in pairs]
        results["krippendorff_alpha"][f"humans_{side}"] = krippendorff_alpha_nominal(human_rows) if len(names) > 1 else None
        for unit, (qcol, acol) in MACHINE_UNITS.items():
            mcol = qcol if side == "question" else acol
            if mcol not in key.columns:
                continue
            rows = [h + [key[mcol].get(p, "") or None] for h, p in zip(human_rows, pairs)]
            results["krippendorff_alpha"][f"humans+{unit}_{side}"] = krippendorff_alpha_nominal(rows)

    # headline + recommendation
    best_unit, best = None, -1.0
    for unit, r in results["machine_vs_human"].items():
        f = r["pooled"].get("macro_f1") or -1
        if f > best:
            best_unit, best = unit, f
    ft = results["machine_vs_human"].get("finbert_turn", {}).get("pooled", {})
    fs = results["machine_vs_human"].get("finbert_sentence", {}).get("pooled", {})
    results["headline"] = {
        "finbert_turn_raw": ft.get("raw_agreement"),
        "finbert_turn_macro_f1": ft.get("macro_f1"),
        "finbert_sentence_raw": fs.get("raw_agreement"),
        "finbert_sentence_macro_f1": fs.get("macro_f1"),
        "best_unit_by_macro_f1": best_unit,
        "m4_met_by_turn": ft.get("meets_m4_bar"),
        "m4_met_by_sentence": fs.get("meets_m4_bar"),
    }
    n_h = ft.get("n") or 0
    results["pitch_line"] = (
        f"Human gold n={n_h} labels ({len(names)} coder{'s' if len(names) > 1 else ''}): FinBERT turn-level "
        f"{(ft.get('raw_agreement') or 0):.0%} raw / macro-F1 {(ft.get('macro_f1') or 0):.2f}; "
        f"sentence-level {(fs.get('raw_agreement') or 0):.0%} / {(fs.get('macro_f1') or 0):.2f}. "
        f"M4 bar 70% {'met' if (ft.get('meets_m4_bar') or fs.get('meets_m4_bar')) else 'not met'}."
    )

    OUT_JSON.write_text(json.dumps(results, indent=2))
    save_json("sentiment_agreement", results)
    rows = []
    for unit, r in results["machine_vs_human"].items():
        for side, b in r.items():
            rows.append({"unit": unit, "side": side, "n": b.get("n"), "raw": b.get("raw_agreement"), "kappa": b.get("cohen_kappa"), "macro_f1": b.get("macro_f1")})
    save_df("sentiment_agreement", pd.DataFrame(rows))
    print(json.dumps(results["headline"], indent=2))
    print(results["pitch_line"])
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()

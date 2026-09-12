"""Compute FinBERT / FT agreement vs hand + silver labels; expand review sample.

Writes:
  - docs/hand_validation_sample.csv  (expanded review queue)
  - docs/assignment2/label_agreement.json
  - store table ``label_agreement`` (one-row summary + optional detail)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from store import configure, has_df, load_df, save_df, save_json  # noqa: E402

DOCS = ROOT / "docs"
HAND = DOCS / "hand_validation_sample.csv"
OUT_JSON = DOCS / "assignment2" / "label_agreement.json"
TARGET_N = 50


def _norm(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower()


def _key(text: pd.Series) -> pd.Series:
    return text.astype(str).str.slice(0, 120)


def expand_hand_sample(labels: pd.DataFrame) -> pd.DataFrame:
    """Grow hand CSV to TARGET_N, prioritizing soft quarters + model disagreement."""
    if HAND.exists():
        hand = pd.read_csv(HAND)
    else:
        hand = pd.DataFrame()

    cols = [
        "bank",
        "quarter",
        "speaker",
        "firm",
        "topic",
        "finbert_sentiment",
        "finbert_score",
        "ldsa_sentiment",
        "text",
        "gold_label",
        "human_reviewed",
        "label_note",
    ]

    # Seed from existing hand rows
    rows = []
    hand_keys = set()
    if len(hand):
        lab_by_key = {
            k: r
            for k, r in zip(_key(labels["text"]), labels.to_dict("records"))
        }
        for _, r in hand.iterrows():
            k = str(r["text"])[:120]
            hand_keys.add(k)
            silver = lab_by_key.get(k, {})
            gold = silver.get("gold_label") or r.get("gold_label") or r.get("finbert_sentiment")
            rows.append(
                {
                    "bank": r.get("bank"),
                    "quarter": r.get("quarter"),
                    "speaker": r.get("speaker"),
                    "firm": r.get("firm"),
                    "topic": r.get("topic"),
                    "finbert_sentiment": r.get("finbert_sentiment"),
                    "finbert_score": r.get("finbert_score"),
                    "ldsa_sentiment": r.get("ldsa_sentiment"),
                    "text": r.get("text"),
                    "gold_label": gold,
                    "human_reviewed": 1,
                    "label_note": "in_hand_sample",
                }
            )

    pool = labels.copy()
    pool["key"] = _key(pool["text"])
    pool = pool[~pool["key"].isin(hand_keys)].copy()
    pool["disagree"] = _norm(pool["finbert_sentiment"]) != _norm(pool["ldsa_sentiment"])

    def prio(r: pd.Series) -> int:
        s = 0
        if r["quarter"] in {"2025-interim", "2025-q2", "2026-q2"}:
            s += 3
        if bool(r["disagree"]):
            s += 2
        if r["bank"] == "hsbc" and r["quarter"] == "2025-interim":
            s += 2
        if r["finbert_sentiment"] == "neutral" and r["ldsa_sentiment"] != "neutral":
            s += 1
        return s

    pool["prio"] = pool.apply(prio, axis=1)
    pool = pool.sort_values("prio", ascending=False)

    need = max(0, TARGET_N - len(rows))
    for _, r in pool.head(need).iterrows():
        rows.append(
            {
                "bank": r["bank"],
                "quarter": r["quarter"],
                "speaker": r.get("speaker"),
                "firm": r.get("firm"),
                "topic": r.get("topic"),
                "finbert_sentiment": r["finbert_sentiment"],
                "finbert_score": r.get("finbert_score"),
                "ldsa_sentiment": r["ldsa_sentiment"],
                "text": r["text"],
                # Provisional: silver gold for queue continuity — team should override
                "gold_label": r["gold_label"],
                "human_reviewed": 0,
                "label_note": "provisional_silver_priority_queue",
            }
        )

    out = pd.DataFrame(rows)[cols]
    HAND.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(HAND, index=False)
    return out


def agreement_block(y_true, y_pred, name: str) -> dict:
    y_true = list(y_true)
    y_pred = list(y_pred)
    if not y_true:
        return {"name": name, "n": 0}
    return {
        "name": name,
        "n": len(y_true),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
    }


def main() -> None:
    configure(memory=False, path=ROOT / "data" / "boe.sqlite", auto_flush=True)
    if not has_df("sentiment_labels"):
        raise SystemExit("Run finetune/label build first — sentiment_labels missing")

    labels = load_df("sentiment_labels")
    hand = expand_hand_sample(labels)

    # Metrics on full silver gold
    fb = _norm(labels["finbert_sentiment"])
    gold = _norm(labels["gold_label"])
    ld = _norm(labels["ldsa_sentiment"])
    blocks = [
        agreement_block(gold, fb, "finbert_vs_silver_gold"),
        agreement_block(gold, ld, "ldsa_vs_silver_gold"),
        agreement_block(fb, ld, "finbert_vs_ldsa"),
    ]

    # Hand-reviewed subset (original sample)
    reviewed = hand[hand["human_reviewed"].astype(int) == 1]
    if len(reviewed):
        blocks.append(
            agreement_block(
                _norm(reviewed["gold_label"]),
                _norm(reviewed["finbert_sentiment"]),
                "finbert_vs_hand_sample_gold",
            )
        )

    # Fine-tuned head if present
    if has_df("sentiment_finetuned"):
        ft = load_df("sentiment_finetuned")
        if {"text", "ft_sentiment"}.issubset(ft.columns):
            m = labels[["text", "gold_label"]].merge(
                ft[["text", "ft_sentiment"]], on="text", how="inner"
            )
            if len(m):
                blocks.append(
                    agreement_block(
                        _norm(m["gold_label"]),
                        _norm(m["ft_sentiment"]),
                        "finetuned_vs_silver_gold",
                    )
                )

    summary = {
        "n_hand_sample": int(len(hand)),
        "n_human_reviewed_flag": int((hand["human_reviewed"].astype(int) == 1).sum()),
        "n_provisional_queue": int((hand["human_reviewed"].astype(int) == 0).sum()),
        "n_corpus_labels": int(len(labels)),
        "metrics": blocks,
        "pitch_line": None,
    }
    fb_hand = next((b for b in blocks if b["name"] == "finbert_vs_hand_sample_gold"), None)
    fb_sil = next((b for b in blocks if b["name"] == "finbert_vs_silver_gold"), None)
    if fb_hand and fb_hand.get("n"):
        summary["pitch_line"] = (
            f"Hand sample n={fb_hand['n']}: FinBERT accuracy "
            f"{fb_hand['accuracy']:.0%} vs sample gold "
            f"(macro-F1 {fb_hand['macro_f1']:.2f})."
        )
    elif fb_sil:
        summary["pitch_line"] = (
            f"Silver labels n={fb_sil['n']}: FinBERT accuracy "
            f"{fb_sil['accuracy']:.0%} (macro-F1 {fb_sil['macro_f1']:.2f})."
        )

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, indent=2))
    save_json("label_agreement", summary)
    save_df(
        "label_agreement",
        pd.DataFrame(
            [
                {
                    "metric": b["name"],
                    "n": b.get("n", 0),
                    "accuracy": b.get("accuracy"),
                    "macro_f1": b.get("macro_f1"),
                }
                for b in blocks
            ]
        ),
    )

    print(json.dumps(summary, indent=2))
    print(f"wrote {HAND} ({len(hand)} rows)")
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()

"""Compute FinBERT / FT agreement vs silver labels; maintain the review queue.

Honesty notes (Alfred, Stage 3):
  * ``gold_label`` in the hand CSV is **silver** (FinBERT∩LDSA∩keyword protocol) unless the
    ``human_label`` column is filled. Earlier versions seeded ``gold_label`` from
    ``finbert_sentiment`` and then reported FinBERT at 100% against it — that is gone.
  * ``human_reviewed`` is 1 only when ``human_label`` is non-empty.
  * The M4 human number comes from ``scripts/score_sentiment_human.py``
    (docs/assignment2/human_labels/sentiment_agreement.json). If that file has no
    coders yet, the pitch line says so instead of quoting a silver figure as human.

Writes:
  - docs/hand_validation_sample.csv  (review queue, 50 rows)
  - docs/assignment2/label_agreement.json
  - store table ``label_agreement``
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
M4_JSON = DOCS / "assignment2" / "human_labels" / "sentiment_agreement.json"
TARGET_N = 50
LABELS = {"negative", "neutral", "positive"}


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
        "human_label",
        "human_reviewed",
        "label_note",
    ]

    # Seed from existing hand rows. gold_label = silver unless a human_label is filled.
    rows = []
    hand_keys = set()
    if len(hand):
        if "human_label" not in hand.columns:
            hand["human_label"] = ""
        lab_by_key = {
            k: r
            for k, r in zip(_key(labels["text"]), labels.to_dict("records"))
        }
        for _, r in hand.iterrows():
            k = str(r["text"])[:120]
            hand_keys.add(k)
            silver = lab_by_key.get(k, {})
            human = str(r.get("human_label") or "").strip().lower()
            human = human if human in LABELS else ""
            silver_gold = silver.get("gold_label") or ""
            rows.append(
                {
                    "bank": r.get("bank"),
                    "quarter": r.get("quarter"),
                    "speaker": r.get("speaker"),
                    "firm": r.get("firm"),
                    "topic": r.get("topic"),
                    "finbert_sentiment": silver.get("finbert_sentiment", r.get("finbert_sentiment")),
                    "finbert_score": silver.get("finbert_score", r.get("finbert_score")),
                    "ldsa_sentiment": silver.get("ldsa_sentiment", r.get("ldsa_sentiment")),
                    "text": r.get("text"),
                    "gold_label": human or silver_gold,
                    "human_label": human,
                    "human_reviewed": 1 if human else 0,
                    "label_note": "human_label" if human else "provisional_silver_priority_queue",
                }
            )

    pool = labels.copy()
    pool["key"] = _key(pool["text"])
    pool = pool[~pool["key"].isin(hand_keys)].copy()
    pool["disagree"] = _norm(pool["finbert_sentiment"]) != _norm(pool["ldsa_sentiment"])

    def prio(r: pd.Series) -> int:
        s = 0
        if r["quarter"] in {
            "2024-interim",
            "2024-q2",
            "2024-annual",
            "2025-interim",
            "2025-q2",
            "2026-q2",
        }:
            s += 3
        if bool(r["disagree"]):
            s += 2
        if r["bank"] == "hsbc" and r["quarter"] in {"2024-interim", "2025-interim"}:
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
                # Provisional: silver gold for queue continuity — a coder fills human_label
                "gold_label": r["gold_label"],
                "human_label": "",
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
    configure(memory=False)  # honours BOE_DB (default data/boe.sqlite)
    if not has_df("sentiment_labels"):
        raise SystemExit("Run finetune/label build first — sentiment_labels missing")

    labels = load_df("sentiment_labels")
    hand = expand_hand_sample(labels)

    # Metrics on full silver gold. These are NOT evaluations — silver is built from
    # FinBERT and LDSA, so agreement with either is partly circular. Kept for the
    # label-protocol audit only.
    fb = _norm(labels["finbert_sentiment"])
    gold = _norm(labels["gold_label"])
    ld = _norm(labels["ldsa_sentiment"])
    blocks = [
        agreement_block(gold, fb, "finbert_vs_silver_gold (circular — audit only)"),
        agreement_block(gold, ld, "ldsa_vs_silver_gold (circular — audit only)"),
        agreement_block(fb, ld, "finbert_vs_ldsa"),
    ]
    if "finbert_sent_label" in labels.columns:
        blocks.append(agreement_block(fb, _norm(labels["finbert_sent_label"]), "finbert_turn_vs_sentence"))

    # Human-labelled rows in the queue (human_label filled by a coder)
    reviewed = hand[hand["human_reviewed"].astype(int) == 1]
    if len(reviewed):
        blocks.append(
            agreement_block(
                _norm(reviewed["human_label"]),
                _norm(reviewed["finbert_sentiment"]),
                "finbert_vs_hand_sample_human",
            )
        )

    # M4 human gold (sentiment pack) — the number that matters. Refresh it here so
    # this script is the single entry point: coder-vs-coder κ / Krippendorff α and
    # machine-vs-human per unit all come from score_sentiment_human.
    m4 = None
    try:
        import score_sentiment_human as _ssh

        _ssh.main()
    except SystemExit as e:  # e.g. machine key missing
        print(f"score_sentiment_human skipped: {e}")
    except Exception as e:  # noqa: BLE001
        print(f"score_sentiment_human failed: {type(e).__name__}: {e}")
    if M4_JSON.is_file():
        try:
            m4 = json.loads(M4_JSON.read_text())
        except Exception:
            m4 = None

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
        "silver_is_circular": True,
        "metrics": blocks,
        "m4_human_gold": (m4 or {}).get("headline"),
        "m4_status": (m4 or {}).get("status") or ("scored" if m4 and m4.get("n_coders") else "awaiting human labels"),
        "pitch_line": None,
    }
    if m4 and m4.get("n_coders"):
        summary["pitch_line"] = m4.get("pitch_line")
    else:
        fb_hand = next((b for b in blocks if b["name"] == "finbert_vs_hand_sample_human"), None)
        if fb_hand and fb_hand.get("n"):
            summary["pitch_line"] = (
                f"Hand queue n={fb_hand['n']} human-labelled rows: FinBERT accuracy "
                f"{fb_hand['accuracy']:.0%} (macro-F1 {fb_hand['macro_f1']:.2f}). "
                "M4 60-pair gold not yet coded."
            )
        else:
            summary["pitch_line"] = (
                "No human sentiment gold yet — silver agreement is circular and is not an accuracy claim. "
                "Code docs/assignment2/human_labels/sentiment_60_for_coding.md, then run "
                "scripts/score_sentiment_human.py."
            )

    # Export the fine-tune run + promotion decision to a tracked file (sqlite is gitignored)
    from store import has_json, load_json

    ft_export = {}
    for key in ("finetune_metrics", "model_registry"):
        if has_json(key):
            ft_export[key] = load_json(key)
    if ft_export:
        ft_path = DOCS / "assignment2" / "finetune_metrics.json"
        ft_path.write_text(json.dumps(ft_export, indent=2))
        summary["finetune_export"] = str(ft_path.relative_to(ROOT))
        fm = ft_export.get("finetune_metrics", {})
        summary["finetune_headline"] = {
            "silver_dev_n": fm.get("n_test"),
            "zero_shot_macro_f1": (fm.get("zero_shot") or {}).get("macro_f1"),
            "finetuned_macro_f1": (fm.get("finetuned") or {}).get("macro_f1"),
            "human_heldout_n": fm.get("n_human_heldout"),
            "active_model_id": fm.get("active_model_id"),
            "promotion": (fm.get("promotion") or {}).get("reason"),
        }

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

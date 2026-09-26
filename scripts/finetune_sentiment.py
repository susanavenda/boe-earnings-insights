#!/usr/bin/env python3
"""Stage 3.4 — Build silver labels and lightly fine-tune FinBERT for earnings Q&A.

A1 scope: *light* domain adaptation of ProsusAI/finbert (head, then last two encoder
layers) — not training from scratch. Promote only if evaluation justifies it.

Label sets
----------
* **silver** — protocol on every analyst turn: FinBERT confident non-neutral →
  FinBERT∩LDSA agree → keyword override → LDSA signal → else neutral. Silver is built
  *from* FinBERT and LDSA, so agreement with silver is partly circular. It is the
  training signal and an audit, never the promotion gate.
* **human gold** — the M4 60-pair pack (docs/assignment2/human_labels/
  sentiment_60_labels_<coder>.csv, question side) plus any ``human_label`` filled in
  docs/hand_validation_sample.csv. Human rows are **held out of training entirely**
  and are the only set the promotion gate reads.

Promotion gate (writes ``model_registry``)
------------------------------------------
    active_model_id = "finbert-domain-ft"  iff  n_human ≥ MIN_HUMAN
                                            and  ft_macro_f1(human) ≥ zs_macro_f1(human) + MARGIN
    else active_model_id = None            (zero-shot FinBERT stays the pipeline scorer)

Writes into data/boe.sqlite: sentiment_labels, sentiment_finetuned, finetune_metrics,
model_registry (JSON docs) and refreshes corpus_analyst (ft_sentiment, ft_score,
gold_label). Weights → models/finbert-domain-ft/.

Usage (repo root):  python scripts/finetune_sentiment.py [--device cpu] [--epochs-head 8]
"""
from __future__ import annotations

import argparse
import glob
import json
import random
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    set_seed,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sentiment import LABELS as _LABELS  # noqa: E402
from sentiment import build_vocab, management_names_from_turns, normalise_for_sentiment  # noqa: E402
from store import configure, has_df, load_df, save_df, save_json  # noqa: E402

DOCS = ROOT / "docs"
HL = DOCS / "assignment2" / "human_labels"
MODEL_DIR = ROOT / "models" / "finbert-domain-ft"
BASE = "ProsusAI/finbert"
LABELS = list(_LABELS)  # negative, neutral, positive
LAB2ID = {l: i for i, l in enumerate(LABELS)}
ID2LAB = {i: l for l, i in LAB2ID.items()}
MIN_HUMAN = 40
MARGIN = 0.05

NEG_KW = [
    "impairment", "headwind", "headwinds", "risk", "risks", "loss", "losses",
    "downgrade", "deteriorat", "uncertain", "pressure", "npl", "default",
    "weak", "decline", "stress", "charge",
]
POS_KW = [
    "growth", "strong", "resilient", "robust", "improve", "upside", "momentum",
    "beat", "record", "healthy", "solid", "confident", "progress", "outperform",
]


def keyword_vote(text: str):
    t = str(text).lower()
    neg = sum(1 for k in NEG_KW if k in t)
    pos = sum(1 for k in POS_KW if k in t)
    if neg >= pos + 2 and neg >= 2:
        return "negative"
    if pos >= neg + 2 and pos >= 2:
        return "positive"
    return None


def assign_label(row) -> tuple[str, str]:
    fb, sc, ld = row["finbert_sentiment"], float(row["finbert_score"]), row["ldsa_sentiment"]
    kw = keyword_vote(row["text"])
    if fb in ("positive", "negative") and sc >= 0.55:
        return fb, "finbert_confident"
    if fb == ld:
        return fb, "finbert_ldsa_agree"
    if kw is not None:
        return kw, "keyword_override"
    if fb == "neutral" and ld in ("positive", "negative") and abs(float(row["ldsa_net"])) >= 0.015:
        return ld, "ldsa_signal"
    return "neutral", "default_neutral"


def _key(s: pd.Series) -> pd.Series:
    return s.astype(str).str.replace(r"\s+", " ", regex=True).str.strip().str.lower().str.slice(0, 120)


def load_human_gold() -> pd.DataFrame:
    """pair_id/text → human question label. Majority across coders; tie → first coder."""
    files = sorted(glob.glob(str(HL / "sentiment_60_labels_*.csv")))
    files = [f for f in files if not f.endswith("template.csv")]
    votes: dict[str, list[str]] = {}
    for f in files:
        df = pd.read_csv(f)
        if not {"pair_id", "q_label"}.issubset(df.columns):
            continue
        for pid, lab in zip(df["pair_id"], df["q_label"]):
            lab = str(lab).strip().lower()
            if lab in LABELS:
                votes.setdefault(str(pid), []).append(lab)
    rows = []
    if votes and has_df("qa_pairs"):
        qa = load_df("qa_pairs")[["pair_id", "question_text"]]
        qmap = dict(zip(qa["pair_id"].astype(str), qa["question_text"]))
        for pid, labs in votes.items():
            c = pd.Series(labs).value_counts()
            lab = labs[0] if len(c) > 1 and c.iloc[0] == c.iloc[1] else c.index[0]
            if pid in qmap:
                rows.append({"key": _key(pd.Series([qmap[pid]]))[0], "human_label": lab, "source": "m4_pack"})
    hand = DOCS / "hand_validation_sample.csv"
    if hand.is_file():
        h = pd.read_csv(hand)
        if "human_label" in h.columns:
            for t, lab in zip(h["text"], h["human_label"]):
                lab = str(lab).strip().lower()
                if lab in LABELS:
                    rows.append({"key": _key(pd.Series([t]))[0], "human_label": lab, "source": "hand_queue"})
    out = pd.DataFrame(rows, columns=["key", "human_label", "source"])
    return out.drop_duplicates("key", keep="first")


def build_labels(corpus: pd.DataFrame) -> pd.DataFrame:
    labs, methods = zip(*(assign_label(r) for _, r in corpus.iterrows()))
    out = corpus.copy()
    out["gold_label"] = list(labs)
    out["label_method"] = list(methods)
    out["key"] = _key(out["text"])
    human = load_human_gold()
    out = out.merge(human, on="key", how="left")
    out["human_label"] = out["human_label"].fillna("")
    out["human_reviewed"] = out["human_label"].ne("")
    # human label overrides silver where present
    out.loc[out["human_reviewed"], "gold_label"] = out.loc[out["human_reviewed"], "human_label"]
    out.loc[out["human_reviewed"], "label_method"] = "human"
    return out.drop(columns=["key", "source"], errors="ignore")


class SentDS(Dataset):
    def __init__(self, frame: pd.DataFrame, tokenizer):
        self.texts = frame["train_text"].astype(str).tolist()
        self.labels = frame["y"].astype(int).tolist()
        self.tok = tokenizer

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, i):
        enc = self.tok(
            self.texts[i], truncation=True, padding="max_length", max_length=256, return_tensors="pt"
        )
        item = {k: v.squeeze(0) for k, v in enc.items()}
        item["labels"] = torch.tensor(self.labels[i], dtype=torch.long)
        return item


def _predict(model, tok, texts: list[str], device, batch: int = 8) -> list[int]:
    preds = []
    model.eval()
    with torch.no_grad():
        for i in range(0, len(texts), batch):
            enc = tok(texts[i: i + batch], truncation=True, padding=True, max_length=256, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            preds.extend(int(x) for x in torch.softmax(model(**enc).logits, dim=-1).argmax(-1).cpu())
    return preds


def _metrics(y_true, y_pred) -> dict:
    if not len(y_true):
        return {"n": 0}
    return {
        "n": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", labels=list(range(3)), zero_division=0)),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted", labels=list(range(3)), zero_division=0)),
        "confusion": confusion_matrix(y_true, y_pred, labels=list(range(3))).tolist(),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default=None)
    ap.add_argument("--epochs-head", type=int, default=8)
    ap.add_argument("--epochs-top", type=int, default=4)
    args = ap.parse_args(argv)

    set_seed(42)
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)
    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    use_cpu = device.type == "cpu"
    configure(memory=False)  # honours BOE_DB (default data/boe.sqlite)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    if not has_df("corpus_analyst"):
        raise SystemExit("corpus_analyst missing — run notebook Stages 1–3 (or scripts/sentiment.py --corpus) first.")
    corpus = load_df("corpus_analyst")
    need = ["text", "finbert_sentiment", "finbert_score", "ldsa_sentiment", "ldsa_net"]
    missing = [c for c in need if c not in corpus.columns]
    if missing:
        raise SystemExit(f"corpus_analyst missing {missing} — run: python scripts/sentiment.py --corpus")
    for c in ("ft_sentiment", "ft_score", "gold_label", "human_label", "human_reviewed", "label_method"):
        if c in corpus.columns:
            corpus = corpus.drop(columns=[c])

    labeled = build_labels(corpus)
    labeled["y"] = labeled["gold_label"].map(LAB2ID)
    all_turns = load_df("all_turns") if has_df("all_turns") else None
    vocab = build_vocab(labeled["text"].tolist())
    names = management_names_from_turns(all_turns)
    labeled["train_text"] = [normalise_for_sentiment(t, vocab=vocab, mgmt_names=names) for t in labeled["text"]]

    keep = [
        "bank", "quarter", "speaker", "firm", "topic", "text", "clean_text",
        "finbert_sentiment", "finbert_score", "ldsa_sentiment", "ldsa_net",
        "gold_label", "label_method", "human_label", "human_reviewed",
    ]
    keep = [c for c in keep if c in labeled.columns]
    save_df("sentiment_labels", labeled[keep])

    human = labeled[labeled["human_reviewed"]].copy()
    silver = labeled[~labeled["human_reviewed"]].copy()
    n_human = int(len(human))
    strat = silver["y"] if silver["y"].value_counts().min() >= 2 else None
    train_df, dev_df = train_test_split(silver, test_size=0.25, random_state=42, stratify=strat)
    print(f"labels: silver train {len(train_df)} / silver dev {len(dev_df)} / human held-out {n_human}")

    tok = AutoTokenizer.from_pretrained(BASE)
    train_ds, dev_ds = SentDS(train_df, tok), SentDS(dev_df, tok)

    counts = train_df["y"].value_counts().reindex(range(3)).fillna(1).values.astype(float)
    weights = torch.tensor(counts.sum() / (len(counts) * counts), dtype=torch.float)

    class WeightedTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            labels = inputs.pop("labels")
            outputs = model(**inputs)
            loss = torch.nn.functional.cross_entropy(
                outputs.logits, labels, weight=weights.to(outputs.logits.device)
            )
            return (loss, outputs) if return_outputs else loss

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)
        return {
            "accuracy": accuracy_score(labels, preds),
            "macro_f1": f1_score(labels, preds, average="macro", zero_division=0),
        }

    # --- zero-shot baseline (base label order → ours) -------------------------------
    zs = AutoModelForSequenceClassification.from_pretrained(BASE).to(device).eval()
    base_id2lab = {int(k): v.lower() for k, v in zs.config.id2label.items()}

    def zs_pred(texts):
        return [LAB2ID[base_id2lab[p]] for p in _predict(zs, tok, texts, device)]

    zs_dev = _metrics(dev_df["y"].tolist(), zs_pred(dev_df["train_text"].tolist()))
    zs_hum = _metrics(human["y"].tolist(), zs_pred(human["train_text"].tolist())) if n_human else {"n": 0}
    print("=== Zero-shot (silver dev) ===")
    if len(dev_df):
        print(classification_report(dev_df["y"], zs_pred(dev_df["train_text"].tolist()), target_names=LABELS, digits=3, zero_division=0))
    del zs

    def make_args(out, epochs, lr):
        kwargs = dict(
            output_dir=str(out),
            num_train_epochs=epochs,
            per_device_train_batch_size=8,
            per_device_eval_batch_size=8,
            learning_rate=lr,
            weight_decay=0.01,
            save_strategy="epoch",
            save_total_limit=1,
            load_best_model_at_end=True,
            metric_for_best_model="macro_f1",
            greater_is_better=True,
            logging_steps=20,
            report_to=[],
            seed=42,
            eval_strategy="epoch",
        )
        try:
            return TrainingArguments(use_cpu=use_cpu, **kwargs)
        except TypeError:
            kwargs.pop("eval_strategy", None)
            kwargs["evaluation_strategy"] = "epoch"
            try:
                return TrainingArguments(use_cpu=use_cpu, **kwargs)
            except TypeError:
                return TrainingArguments(**kwargs)

    ft = AutoModelForSequenceClassification.from_pretrained(
        BASE, num_labels=3, id2label=ID2LAB, label2id=LAB2ID, ignore_mismatched_sizes=True
    )
    for name, param in ft.named_parameters():
        if "classifier" not in name:
            param.requires_grad = False
    trainer = WeightedTrainer(model=ft, args=make_args(MODEL_DIR / "runs", args.epochs_head, 5e-4), train_dataset=train_ds, eval_dataset=dev_ds, compute_metrics=compute_metrics)
    trainer.train()

    for name, param in ft.named_parameters():
        if "encoder.layer.10" in name or "encoder.layer.11" in name or "classifier" in name:
            param.requires_grad = True
    trainer2 = WeightedTrainer(model=ft, args=make_args(MODEL_DIR / "runs2", args.epochs_top, 2e-5), train_dataset=train_ds, eval_dataset=dev_ds, compute_metrics=compute_metrics)
    trainer2.train()

    model = trainer2.model.to(device).eval()
    ft_dev = _metrics(dev_df["y"].tolist(), _predict(model, tok, dev_df["train_text"].tolist(), device))
    ft_hum = _metrics(human["y"].tolist(), _predict(model, tok, human["train_text"].tolist(), device)) if n_human else {"n": 0}
    print("=== Fine-tuned (silver dev) ===")
    if len(dev_df):
        print(classification_report(dev_df["y"], _predict(model, tok, dev_df["train_text"].tolist(), device), target_names=LABELS, digits=3, zero_division=0))

    model.save_pretrained(MODEL_DIR)
    tok.save_pretrained(MODEL_DIR)

    # --- score full corpus with the candidate ---------------------------------------
    ft_all = []
    texts = labeled["train_text"].astype(str).tolist()
    with torch.no_grad():
        for i in range(0, len(texts), 8):
            enc = tok(texts[i: i + 8], truncation=True, padding=True, max_length=256, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            probs = torch.softmax(model(**enc).logits, dim=-1)
            for j in range(probs.size(0)):
                idx = int(probs[j].argmax())
                ft_all.append({"ft_sentiment": ID2LAB[idx], "ft_score": float(probs[j][idx])})
    out_full = pd.concat([labeled[keep].reset_index(drop=True), pd.DataFrame(ft_all)], axis=1)
    save_df("sentiment_finetuned", out_full)

    corp = load_df("corpus_analyst")
    for c in ("ft_sentiment", "ft_score", "gold_label"):
        if c in corp.columns:
            corp = corp.drop(columns=[c])
    corp = corp.merge(out_full[["text", "ft_sentiment", "ft_score", "gold_label"]].drop_duplicates("text"), on="text", how="left")
    save_df("corpus_analyst", corp)

    # --- promotion gate ---------------------------------------------------------------
    gate_ok = bool(
        n_human >= MIN_HUMAN
        and ft_hum.get("macro_f1") is not None
        and ft_hum["macro_f1"] >= zs_hum["macro_f1"] + MARGIN
    )
    if n_human < MIN_HUMAN:
        gate_reason = f"blocked — human gold n={n_human} < {MIN_HUMAN}; silver-only results are not a promotion basis"
    elif gate_ok:
        gate_reason = f"passed — FT macro-F1 {ft_hum['macro_f1']:.3f} ≥ zero-shot {zs_hum['macro_f1']:.3f} + {MARGIN} on human gold"
    else:
        gate_reason = f"failed — FT macro-F1 {ft_hum['macro_f1']:.3f} < zero-shot {zs_hum['macro_f1']:.3f} + {MARGIN} on human gold"
    registry = {
        "active_model_id": "finbert-domain-ft" if gate_ok else None,
        "candidate_model_id": "finbert-domain-ft",
        "base_model": BASE,
        "gate": {"min_human": MIN_HUMAN, "margin": MARGIN, "passed": gate_ok, "reason": gate_reason},
        "human_gold": {"n": n_human, "zero_shot": zs_hum, "finetuned": ft_hum},
    }
    save_json("model_registry", registry)

    summary = {
        "n_labeled": int(len(labeled)),
        "n_train": int(len(train_df)),
        "n_test": int(len(dev_df)),
        "n_human_heldout": n_human,
        "label_dist": {k: int(v) for k, v in labeled["gold_label"].value_counts().items()},
        "label_method_dist": {k: int(v) for k, v in labeled["label_method"].value_counts().items()},
        "label_protocol": (
            "silver: FinBERT confident non-neutral → FinBERT∩LDSA agree → keyword override → LDSA signal → neutral; "
            "human: M4 60-pair pack (question side) + hand_validation_sample.human_label, held out of training"
        ),
        "training": (
            f"{BASE}; stage1 classifier-head-only {args.epochs_head} epochs lr=5e-4; "
            f"stage2 unfreeze encoder layers 10-11 + head {args.epochs_top} epochs lr=2e-5; "
            f"class-weighted CE; silver stratified 75/25; text normalised via sentiment.py; {device.type}"
        ),
        # silver dev (audit — circular with the label protocol)
        "zero_shot": {k: v for k, v in zs_dev.items() if k != "confusion"},
        "finetuned": {k: v for k, v in ft_dev.items() if k != "confusion"},
        "confusion_zero_shot": zs_dev.get("confusion"),
        "confusion_finetuned": ft_dev.get("confusion"),
        # human gold (the gate)
        "human_zero_shot": zs_hum,
        "human_finetuned": ft_hum,
        "promotion": registry["gate"],
        "active_model_id": registry["active_model_id"],
        "model_path": str(MODEL_DIR.relative_to(ROOT)),
    }
    save_json("finetune_metrics", summary)
    print(json.dumps({k: summary[k] for k in ("n_labeled", "n_human_heldout", "zero_shot", "finetuned", "human_zero_shot", "human_finetuned", "promotion")}, indent=2))
    print("wrote FT artifacts → data/boe.sqlite")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)

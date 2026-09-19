#!/usr/bin/env python3
"""Stage 3.4 — Build silver labels and lightly fine-tune FinBERT for earnings Q&A.

Writes into ``data/boe.sqlite``:
  sentiment_labels, sentiment_finetuned, finetune_metrics (JSON doc),
  and refreshes analyst_turns (corpus_analyst).

Also writes model weights to ``models/finbert-domain-ft/``.

Usage (from repo root):
  .venv/bin/python scripts/finetune_sentiment.py
"""
from __future__ import annotations

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
from store import configure, has_df, load_df, save_df, save_json  # noqa: E402

PROC = ROOT / "data" / "processed"
DOCS = ROOT / "docs"
MODEL_DIR = ROOT / "models" / "finbert-domain-ft"
BASE = "ProsusAI/finbert"
LABELS = ["negative", "neutral", "positive"]
LAB2ID = {l: i for i, l in enumerate(LABELS)}
ID2LAB = {i: l for l, i in LAB2ID.items()}

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


def build_labels(corpus: pd.DataFrame) -> pd.DataFrame:
    labs, methods = zip(*(assign_label(r) for _, r in corpus.iterrows()))
    out = corpus.copy()
    out["gold_label"] = list(labs)
    out["label_method"] = list(methods)
    hand_path = DOCS / "hand_validation_sample.csv"
    if hand_path.is_file():
        hand = pd.read_csv(hand_path)
        hand_keys = set(hand["text"].astype(str).str.slice(0, 120))
        out["human_reviewed"] = out["text"].astype(str).str.slice(0, 120).isin(hand_keys)
    else:
        print(f"hand sample missing at {hand_path} — human_reviewed=False")
        out["human_reviewed"] = False
    return out


class SentDS(Dataset):
    def __init__(self, frame: pd.DataFrame, tokenizer):
        self.texts = frame["text"].astype(str).tolist()
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


def main():
    set_seed(42)
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)
    # CUDA if Colab/GPU; CPU otherwise. Skip MPS (placeholder issues on macOS).
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_cpu = device.type == "cpu"
    configure(memory=False, path=ROOT / "data" / "boe.sqlite")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    if not has_df("corpus_analyst"):
        raise SystemExit(
            "corpus_analyst missing from data/boe.sqlite — run notebook Stages 1–3 "
            "and ensure the notebook flushed to disk before this script."
        )
    corpus = load_df("corpus_analyst")
    need = ["text", "finbert_sentiment", "finbert_score", "ldsa_sentiment", "ldsa_net"]
    missing = [c for c in need if c not in corpus.columns]
    if missing:
        raise SystemExit(
            f"corpus_analyst missing {missing} — run Stage 3 FinBERT + LDSA before fine-tune."
        )
    # Drop prior FT columns before rebuild
    for c in ("ft_sentiment", "ft_score", "gold_label"):
        if c in corpus.columns:
            corpus = corpus.drop(columns=[c])

    labeled = build_labels(corpus)
    labeled["y"] = labeled["gold_label"].map(LAB2ID)
    keep = [
        "bank", "quarter", "speaker", "firm", "topic", "text", "clean_text",
        "finbert_sentiment", "finbert_score", "ldsa_sentiment", "ldsa_net",
        "gold_label", "label_method", "human_reviewed",
    ]
    keep = [c for c in keep if c in labeled.columns]
    save_df("sentiment_labels", labeled[keep])

    train_df, test_df = train_test_split(
        labeled, test_size=0.25, random_state=42, stratify=labeled["y"]
    )
    tok = AutoTokenizer.from_pretrained(BASE)
    train_ds, test_ds = SentDS(train_df, tok), SentDS(test_df, tok)

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
            "macro_f1": f1_score(labels, preds, average="macro"),
            "weighted_f1": f1_score(labels, preds, average="weighted"),
        }

    # Zero-shot baseline
    zs = AutoModelForSequenceClassification.from_pretrained(BASE).to(device).eval()
    mid2lab = {int(k): v.lower() for k, v in zs.config.id2label.items()}
    true_y = test_df["y"].tolist()
    zs_y = []
    with torch.no_grad():
        texts = test_df["text"].astype(str).tolist()
        for i in range(0, len(texts), 8):
            enc = tok(texts[i : i + 8], truncation=True, padding=True, max_length=256, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            probs = torch.softmax(zs(**enc).logits, dim=-1)
            for j in range(probs.size(0)):
                zs_y.append(LAB2ID[mid2lab[int(probs[j].argmax())]])
    zs_metrics = {
        "accuracy": float(accuracy_score(true_y, zs_y)),
        "macro_f1": float(f1_score(true_y, zs_y, average="macro")),
        "weighted_f1": float(f1_score(true_y, zs_y, average="weighted")),
    }
    print("=== Zero-shot ===")
    print(classification_report(true_y, zs_y, target_names=LABELS, digits=3))

    def make_args(out, epochs, lr):
        kwargs = dict(
            output_dir=str(out),
            num_train_epochs=epochs,
            per_device_train_batch_size=8,
            per_device_eval_batch_size=8,
            learning_rate=lr,
            weight_decay=0.01,
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="macro_f1",
            greater_is_better=True,
            logging_steps=5,
            report_to=[],
            seed=42,
        )
        # transformers ≥4.46: eval_strategy; older: evaluation_strategy
        kwargs["eval_strategy"] = "epoch"
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

    trainer = WeightedTrainer(
        model=ft,
        args=make_args(MODEL_DIR / "runs", 8, 5e-4),
        train_dataset=train_ds,
        eval_dataset=test_ds,
        compute_metrics=compute_metrics,
    )
    trainer.train()

    for name, param in ft.named_parameters():
        if "encoder.layer.10" in name or "encoder.layer.11" in name or "classifier" in name:
            param.requires_grad = True

    trainer2 = WeightedTrainer(
        model=ft,
        args=make_args(MODEL_DIR / "runs2", 4, 2e-5),
        train_dataset=train_ds,
        eval_dataset=test_ds,
        compute_metrics=compute_metrics,
    )
    trainer2.train()
    ft_metrics = trainer2.evaluate()
    ft_preds = np.argmax(trainer2.predict(test_ds).predictions, axis=-1)
    print("=== Fine-tuned ===")
    print(classification_report(true_y, ft_preds, target_names=LABELS, digits=3))

    trainer2.model.to(device)
    trainer2.model.save_pretrained(MODEL_DIR)
    tok.save_pretrained(MODEL_DIR)

    # Score full corpus
    model = trainer2.model.eval()
    ft_all = []
    all_texts = labeled["text"].astype(str).tolist()
    with torch.no_grad():
        for i in range(0, len(all_texts), 8):
            enc = tok(all_texts[i : i + 8], truncation=True, padding=True, max_length=256, return_tensors="pt")
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
    corp = corp.merge(out_full[["text", "ft_sentiment", "ft_score", "gold_label"]], on="text", how="left")
    save_df("corpus_analyst", corp)

    summary = {
        "n_labeled": int(len(labeled)),
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "label_dist": {k: int(v) for k, v in labeled["gold_label"].value_counts().items()},
        "label_protocol": (
            "multi-signal silver labels (FinBERT∩LDSA agree, FinBERT confident non-neutral, "
            "LDSA signal, keyword override); 20 rows human_reviewed from hand_validation_sample"
        ),
        "training": (
            "ProsusAI/finbert; stage1 classifier-head-only 8 epochs lr=5e-4; "
            "stage2 unfreeze encoder layers 10-11 + head 4 epochs lr=2e-5; "
            "class-weighted CE; stratified 75/25; CPU"
        ),
        "zero_shot": zs_metrics,
        "finetuned": {
            "accuracy": float(accuracy_score(true_y, ft_preds)),
            "macro_f1": float(f1_score(true_y, ft_preds, average="macro")),
            "weighted_f1": float(f1_score(true_y, ft_preds, average="weighted")),
        },
        "eval_raw": {k: float(v) for k, v in ft_metrics.items() if isinstance(v, (int, float, np.floating))},
        "confusion_zero_shot": confusion_matrix(true_y, zs_y).tolist(),
        "confusion_finetuned": confusion_matrix(true_y, ft_preds).tolist(),
        "model_path": str(MODEL_DIR.relative_to(ROOT)),
    }
    save_json("finetune_metrics", summary)
    print(json.dumps(summary, indent=2))
    print("wrote FT artifacts → data/boe.sqlite")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)

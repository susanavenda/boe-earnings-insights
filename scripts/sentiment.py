#!/usr/bin/env python3
"""Stage 3 — sentiment module: FinBERT (turn + sentence unit) and Loughran–McDonald lexicon.

Owner: Alfred (Qianyi). One place for everything Stage 3.1 / 3.1b / 3.2 needs, so the
notebook, ``score_qa_sentiment.py`` and ``finetune_sentiment.py`` all score text the
same way.

What it fixes versus the first cut
----------------------------------
* **Scoring unit.** FinBERT (ProsusAI/finbert) was trained on single sentences
  (Financial PhraseBank). Analyst turns here are 9 sentences at the median and 26 at
  p90; management answers are longer. Feeding a whole turn truncated at 512 tokens
  collapses to *neutral*. This module scores every sentence and aggregates, and keeps
  the old turn-level columns alongside so nothing downstream breaks.
* **Net score.** Old ``finbert_net`` = sign(argmax) × confidence, which is 0 for every
  neutral call and jumps at the argmax boundary. New ``*_net`` columns use the full
  softmax: ``p_pos − p_neg`` (continuous, keeps a neutral call's lean).
* **LDSA.** The notebook's lexicon was a ~50-word hand list. This uses the
  Loughran–McDonald master dictionary (positive / negative / **uncertainty** /
  **constraining**) with LM's simple negation rule, and exposes a hedging index —
  the honest way to measure "hedged bank language" rather than reading it off
  FinBERT's neutral share.
* **Text noise.** pdfplumber drops fi/ffi/fl ligatures as U+FFFD (``e�ciency``),
  page headers (``9 Investor Relations``) and management speaker names are spliced
  mid-answer. ``normalise_for_sentiment`` repairs these *for scoring only* — the
  stored ``text`` column is never rewritten.

Column contract (added by ``score_corpus`` / ``score_qa``)
----------------------------------------------------------
Turn unit (unchanged names, unchanged meaning):
  finbert_sentiment, finbert_score, finbert_net
Turn unit, new:
  finbert_p_pos, finbert_p_neg, finbert_p_neu, finbert_net_prob
Sentence unit, new:
  finbert_sent_label, finbert_sent_net, finbert_sent_pos_share,
  finbert_sent_neg_share, finbert_sent_n, finbert_sent_neg_max
Lexicon (LM-backed; names kept for finetune / label_agreement compatibility):
  ldsa_sentiment, ldsa_net, lm_pos_n, lm_neg_n, lm_unc_n, lm_constr_n, lm_n_tok,
  lm_uncertainty, lm_hedge, lm_source

CLI
---
  python scripts/sentiment.py --corpus            # score corpus_analyst (text)
  python scripts/sentiment.py --qa                # score qa_pairs question/answer
  python scripts/sentiment.py --corpus --qa --unit both --device cpu
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
import warnings
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

LABELS = ("negative", "neutral", "positive")
FINBERT = "ProsusAI/finbert"
# Sentence-unit label dead zone on mean(p_pos − p_neg). FinBERT's sentence net sits at
# +0.06 median on analyst questions (openers like "good result" before the probe), so a
# ±0.05 zone over-calls positive. 0.15 gives ~64% neutral, in line with the LM lexicon.
# Calibrate against the M4 human gold (scripts/score_sentiment_human.py), not by eye.
DEAD_ZONE = 0.15

# ----------------------------------------------------------------------------
# 1. Text normalisation (scoring-only; never write back to the stored text)
# ----------------------------------------------------------------------------

_LIGATURE_TRIES = ("fi", "fl", "ffi", "ff", "ffl")
_REPL = "�"
_PAGE_HEADER = re.compile(r"\b\d{1,3}\s+Investor Relations\b|\bInvestor Relations\b")
_BRACKET_NOTE = re.compile(r"[\[\(]\s*(inaudible|unclear|crosstalk|laughter|indiscernible)[^\]\)]*[\]\)]", re.I)
_MULTI_WS = re.compile(r"\s+")
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
# Tokens that carry no sentiment content in an earnings-call opener/closer. A sentence
# whose remaining alphabetic tokens (after removing these) number < 3 is "courtesy".
_COURTESY_TOKENS = {
    "thanks", "thank", "you", "for", "taking", "my", "the", "question", "questions", "good", "morning",
    "afternoon", "evening", "hi", "hello", "everyone", "everybody", "all", "guys", "chaps", "okay", "ok",
    "yes", "yeah", "sure", "great", "please", "and", "a", "an", "both", "two", "three", "of", "them", "it",
    "that", "is", "so", "just", "very", "much", "thank", "very", "too", "as", "well", "one", "first", "second",
    "also", "i", "have", "got", "had", "couple", "few", "quick", "ones", "if", "may", "can", "could", "from",
    "here", "there", "morning", "again", "guys", "team", "operator", "next", "go", "ahead", "your", "line",
    "open", "hey", "cheers", "bye", "right", "then", "on", "to", "me", "we", "will", "take",
}


def is_courtesy_sentence(sentence: str) -> bool:
    toks = re.findall(r"[a-z]+", sentence.lower())
    content = [t for t in toks if t not in _COURTESY_TOKENS]
    return len(content) < 3

# Legacy hand lexicon from the notebook's first Stage 3.2 — kept only so old
# numbers can be reproduced with lexicon="legacy".
LEGACY_POS = {
    "growth", "strong", "improve", "improved", "improvement", "resilient", "robust",
    "increase", "increased", "upside", "momentum", "solid", "healthy", "stable",
    "confidence", "confident", "progress", "record", "beat", "outperform",
}
LEGACY_NEG = {
    "risk", "risks", "weak", "weaker", "decline", "declined", "pressure", "pressures",
    "impairment", "impairments", "loss", "losses", "concern", "concerns", "uncertain",
    "uncertainty", "downgrade", "deterioration", "headwind", "headwinds", "stress",
    "default", "npl", "charge", "charges", "cut", "cuts", "slowdown",
}


def build_vocab(texts: Iterable[str], min_count: int = 2) -> set[str]:
    """Words that appear intact (no U+FFFD) in the corpus — used to repair ligatures."""
    c: Counter[str] = Counter()
    for t in texts:
        if not isinstance(t, str):
            continue
        c.update(w for w in re.findall(r"[a-z]{3,}", t.lower()) if _REPL not in w)
    return {w for w, n in c.items() if n >= min_count}


def repair_ligatures(text: str, vocab: set[str] | None = None) -> str:
    """Replace U+FFFD with the ligature that yields a known word (fi > fl > ffi > ff > ffl)."""
    if _REPL not in text:
        return text

    def _fix(m: re.Match) -> str:
        tok = m.group(0)
        low = tok.lower()
        for lig in _LIGATURE_TRIES:
            cand = low.replace(_REPL, lig)
            if vocab is None or cand in vocab:
                # preserve leading capital
                return cand.capitalize() if tok[0].isupper() else cand
        return low.replace(_REPL, "fi")

    return re.sub(rf"\w*{_REPL}\w*", _fix, text)


def strip_speaker_names(text: str, names: Sequence[str]) -> str:
    """Remove spliced management speaker names ('... So I'll pick those up. Anna Cross Okay ...')."""
    for n in sorted(set(names), key=len, reverse=True):
        n = n.strip()
        if len(n) < 5:
            continue
        text = re.sub(rf"(?<![\w])(?:{re.escape(n)})(?![\w])[\s:.,-]*", " ", text)
    return text


def normalise_for_sentiment(
    text: str,
    *,
    vocab: set[str] | None = None,
    mgmt_names: Sequence[str] | None = None,
    drop_courtesy: bool = True,
) -> str:
    """Clean a turn for scoring. Keeps case, numbers and punctuation (FinBERT needs them)."""
    if not isinstance(text, str) or not text.strip():
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = t.replace("’", "'").replace("“", '"').replace("”", '"').replace("„", '"')
    t = t.replace("–", "-").replace("—", " - ")
    t = _HYPHEN_BREAK.sub(r"\1\2", t)
    t = repair_ligatures(t, vocab)
    t = _PAGE_HEADER.sub(" ", t)
    t = _BRACKET_NOTE.sub(" ", t)
    if mgmt_names:
        t = strip_speaker_names(t, mgmt_names)
    t = t.replace("\n", " ")
    t = _MULTI_WS.sub(" ", t).strip()
    if drop_courtesy:
        kept = [s for s in _sent_tokenizer()(t) if not is_courtesy_sentence(s)]
        t2 = " ".join(s.strip() for s in kept).strip()
        if len(t2) >= 20:
            t = t2
    return t


@lru_cache(maxsize=1)
def _sent_tokenizer():
    try:
        from nltk.tokenize import sent_tokenize

        sent_tokenize("Test sentence. Another one.")
        return sent_tokenize
    except Exception:  # punkt missing → regex fallback
        warnings.warn("nltk punkt unavailable — using regex sentence splitter")
        rx = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9£$])")
        return lambda s: rx.split(s)


def split_sentences(text: str, min_tokens: int = 4, drop_courtesy: bool = True) -> list[str]:
    """Sentence units for FinBERT. Drops fragments shorter than ``min_tokens`` words."""
    if not text:
        return []
    out = []
    for s in _sent_tokenizer()(text):
        s = s.strip()
        if len(re.findall(r"\w+", s)) < min_tokens:
            continue
        if drop_courtesy and is_courtesy_sentence(s):
            continue
        out.append(s)
    return out


_NAME_STOP = {
    "thanks", "thank", "good", "morning", "yes", "okay", "and", "the", "in", "we", "so", "question", "operator", "next",
    # places / business lines the speaker regex mistakes for people
    "hong", "kong", "bank", "banking", "group", "uk", "us", "usa", "asia", "europe", "china", "india", "london", "york",
    "states", "kingdom", "capital", "markets", "wealth", "retail", "private", "global", "commercial", "corporate",
    "investment", "treasury", "insurance", "mexico", "middle", "east", "north", "south", "america", "hang", "seng",
}


def management_names_from_turns(all_turns: pd.DataFrame | None, min_turns: int = 3) -> list[str]:
    """Speaker names spliced into answers ('… pick those up. Anna Cross Okay …').

    Uses every speaker (the segmenter mis-roles some analysts as management, and an
    analyst's full name spliced into an answer is noise too). Requires ≥ ``min_turns``
    appearances and a 2–4 word capitalised name with no courtesy token.
    """
    if all_turns is None or all_turns.empty or "speaker" not in all_turns.columns:
        return []
    counts = all_turns["speaker"].dropna().astype(str).str.strip().value_counts()
    keep = []
    for n, k in counts.items():
        if k < min_turns:
            continue
        parts = n.split()
        if not (2 <= len(parts) <= 4) or len(n) > 40:
            continue
        if not all(p[:1].isupper() for p in parts):
            continue
        if any(p.lower().strip(".,") in _NAME_STOP for p in parts):
            continue
        keep.append(n)
    return keep


# ----------------------------------------------------------------------------
# 2. Loughran–McDonald lexicon
# ----------------------------------------------------------------------------

_LM_NEGATORS = {"no", "not", "never", "none", "neither", "nor", "nobody", "nothing", "cannot", "without"}
_LM_CATS = ("Positive", "Negative", "Uncertainty", "Constraining", "Litigious")


def _find_lm_csv() -> Path | None:
    env = os.environ.get("BOE_LM_CSV")
    if env and Path(env).is_file():
        return Path(env)
    for cand in (ROOT / "data" / "lexicon" / "LM.csv", ROOT / "data" / "lexicon" / "Loughran-McDonald_MasterDictionary.csv"):
        if cand.is_file():
            return cand
    try:
        import pysentiment2  # type: ignore

        p = Path(pysentiment2.__file__).parent / "static" / "LM.csv"
        if p.is_file():
            return p
    except Exception:
        pass
    return None


class LMScorer:
    """Loughran–McDonald dictionary scorer with LM's negation rule for positives.

    ``lexicon="lm"`` (default) loads the master dictionary; ``lexicon="legacy"``
    reproduces the notebook's first hand list. Scores are per-token proportions so
    long and short turns are comparable.
    """

    def __init__(self, lexicon: str = "lm", csv_path: Path | str | None = None, neg_window: int = 3):
        self.lexicon = lexicon
        self.neg_window = neg_window
        self.sets: dict[str, set[str]] = {}
        self.source = "legacy"
        if lexicon == "legacy":
            self.sets = {"Positive": set(LEGACY_POS), "Negative": set(LEGACY_NEG), "Uncertainty": set(), "Constraining": set(), "Litigious": set()}
            return
        path = Path(csv_path) if csv_path else _find_lm_csv()
        if path is None:
            warnings.warn(
                "Loughran–McDonald CSV not found (pip install pysentiment2, or set BOE_LM_CSV). "
                "Falling back to the legacy hand lexicon."
            )
            self.sets = {"Positive": set(LEGACY_POS), "Negative": set(LEGACY_NEG), "Uncertainty": set(), "Constraining": set(), "Litigious": set()}
            return
        df = pd.read_csv(path, usecols=["Word", *_LM_CATS])
        df["Word"] = df["Word"].astype(str).str.lower()
        for cat in _LM_CATS:
            v = pd.to_numeric(df[cat], errors="coerce").fillna(0)
            self.sets[cat] = set(df.loc[v > 0, "Word"])
        self.source = f"lm:{path.name}"

    def score(self, text: str) -> dict:
        toks = re.findall(r"[a-z]+(?:'[a-z]+)?", str(text).lower())
        n = len(toks)
        pos = neg = unc = con = lit = 0
        P, N, U, C, L = (self.sets[k] for k in _LM_CATS)
        for i, w in enumerate(toks):
            if w in P:
                window = toks[max(0, i - self.neg_window): i]
                if any(x in _LM_NEGATORS for x in window):
                    neg += 1
                else:
                    pos += 1
            elif w in N:
                neg += 1
            if w in U:
                unc += 1
            if w in C:
                con += 1
            if w in L:
                lit += 1
        net = (pos - neg) / n if n else 0.0
        return {
            "lm_pos_n": pos,
            "lm_neg_n": neg,
            "lm_unc_n": unc,
            "lm_constr_n": con,
            "lm_lit_n": lit,
            "lm_n_tok": n,
            "ldsa_net": float(net),
            "lm_uncertainty": (unc / n) if n else 0.0,
            "lm_hedge": ((unc + con) / n) if n else 0.0,
        }

    @staticmethod
    def label(net: float, threshold: float = 0.01) -> str:
        if net > threshold:
            return "positive"
        if net < -threshold:
            return "negative"
        return "neutral"

    def score_many(self, texts: Iterable[str], threshold: float = 0.01) -> pd.DataFrame:
        rows = [self.score(t) for t in texts]
        out = pd.DataFrame(rows)
        out["ldsa_sentiment"] = out["ldsa_net"].map(lambda x: self.label(x, threshold))
        out["lm_source"] = self.source
        return out


# ----------------------------------------------------------------------------
# 3. FinBERT scorer — turn and sentence units, full softmax
# ----------------------------------------------------------------------------


def pick_device(prefer: str | None = None) -> str:
    import torch

    if prefer:
        return prefer
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class FinBertScorer:
    """ProsusAI/finbert (or a fine-tuned checkpoint) returning full class probabilities."""

    def __init__(
        self,
        model_name: str = FINBERT,
        *,
        device: str | None = None,
        batch_size: int = 16,
        local_files_only: bool = False,
    ):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.model_name = model_name
        self.device = pick_device(device)
        self.batch_size = batch_size
        try:
            self.tok = AutoTokenizer.from_pretrained(model_name, local_files_only=local_files_only)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name, local_files_only=local_files_only)
        except OSError:
            if local_files_only:
                self.tok = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            else:
                raise
        self.model.to(self.device).eval()
        id2label = {int(k): str(v).lower() for k, v in self.model.config.id2label.items()}
        self.col = {lab: i for i, lab in id2label.items()}  # label -> column index
        missing = set(LABELS) - set(self.col)
        if missing:
            raise ValueError(f"{model_name} does not expose labels {LABELS}: {id2label}")
        self._torch = torch

    def probs(self, texts: Sequence[str], max_length: int) -> np.ndarray:
        """(n, 3) probabilities ordered (negative, neutral, positive). Empty text → NaN row."""
        torch = self._torch
        out = np.full((len(texts), 3), np.nan, dtype=float)
        idx = [i for i, t in enumerate(texts) if isinstance(t, str) and t.strip()]
        order = [self.col[l] for l in LABELS]
        with torch.no_grad():
            for s in range(0, len(idx), self.batch_size):
                chunk = idx[s: s + self.batch_size]
                enc = self.tok(
                    [texts[i] for i in chunk],
                    truncation=True,
                    padding=True,
                    max_length=max_length,
                    return_tensors="pt",
                )
                enc = {k: v.to(self.device) for k, v in enc.items()}
                p = torch.softmax(self.model(**enc).logits, dim=-1).float().cpu().numpy()
                out[chunk] = p[:, order]
        return out

    # -- turn unit ---------------------------------------------------------
    def score_turns(self, texts: Sequence[str], max_length: int = 512) -> pd.DataFrame:
        p = self.probs(list(texts), max_length)
        df = pd.DataFrame(p, columns=["finbert_p_neg", "finbert_p_neu", "finbert_p_pos"])
        has = ~np.isnan(p[:, 0])
        arg = np.where(has, np.nanargmax(np.where(has[:, None], p, -1), axis=1), -1)
        lab = np.array([LABELS[i] if i >= 0 else "" for i in arg])
        conf = np.where(has, np.nanmax(np.where(has[:, None], p, -1), axis=1), 0.0)
        sign = np.select([lab == "positive", lab == "negative"], [1.0, -1.0], 0.0)
        df["finbert_sentiment"] = lab
        df["finbert_score"] = conf
        df["finbert_net"] = sign * conf  # legacy definition, unchanged
        df["finbert_net_prob"] = np.where(has, df["finbert_p_pos"] - df["finbert_p_neg"], 0.0)
        return df

    # -- sentence unit -----------------------------------------------------
    def score_sentences(
        self,
        texts: Sequence[str],
        *,
        max_length: int = 128,
        min_tokens: int = 4,
        dead_zone: float = DEAD_ZONE,
        return_sentences: bool = False,
    ) -> pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]:
        """Score each sentence; aggregate per text.

        finbert_sent_net       mean over sentences of (p_pos − p_neg)
        finbert_sent_pos_share share of sentences whose argmax is positive
        finbert_sent_neg_share share of sentences whose argmax is negative
        finbert_sent_neg_max   max p_neg over sentences (single sharpest risk sentence)
        finbert_sent_label     sign of finbert_sent_net outside ±dead_zone, else neutral

        Re-threshold later without re-scoring: ``relabel_sentence(df, dead_zone)``.
        """
        flat, owner = [], []
        for i, t in enumerate(texts):
            for s in split_sentences(t if isinstance(t, str) else "", min_tokens=min_tokens):
                flat.append(s)
                owner.append(i)
        p = self.probs(flat, max_length) if flat else np.zeros((0, 3))
        sent = pd.DataFrame(p, columns=["p_neg", "p_neu", "p_pos"])
        sent["owner"] = owner
        sent["sentence"] = flat
        sent["label"] = [LABELS[int(i)] for i in np.argmax(p, axis=1)] if len(sent) else []
        sent["net"] = sent["p_pos"] - sent["p_neg"]

        n = len(texts)
        agg = pd.DataFrame(
            {
                "finbert_sent_n": np.zeros(n, dtype=int),
                "finbert_sent_net": np.zeros(n),
                "finbert_sent_pos_share": np.zeros(n),
                "finbert_sent_neg_share": np.zeros(n),
                "finbert_sent_neg_max": np.zeros(n),
                "finbert_sent_label": [""] * n,
            }
        )
        if len(sent):
            g = sent.groupby("owner")
            agg.loc[g.size().index, "finbert_sent_n"] = g.size().values
            agg.loc[g["net"].mean().index, "finbert_sent_net"] = g["net"].mean().values
            pos = g["label"].apply(lambda s: float((s == "positive").mean()))
            neg = g["label"].apply(lambda s: float((s == "negative").mean()))
            agg.loc[pos.index, "finbert_sent_pos_share"] = pos.values
            agg.loc[neg.index, "finbert_sent_neg_share"] = neg.values
            agg.loc[g["p_neg"].max().index, "finbert_sent_neg_max"] = g["p_neg"].max().values
        has = agg["finbert_sent_n"] > 0
        agg.loc[has, "finbert_sent_label"] = np.select(
            [agg.loc[has, "finbert_sent_net"] > dead_zone, agg.loc[has, "finbert_sent_net"] < -dead_zone],
            ["positive", "negative"],
            "neutral",
        )
        return (agg, sent) if return_sentences else agg


def relabel_sentence(df: pd.DataFrame, dead_zone: float = DEAD_ZONE, prefix: str = "finbert_sent_") -> pd.DataFrame:
    """Recompute ``<prefix>label`` from ``<prefix>net`` with a new dead zone (no re-scoring)."""
    out = df.copy()
    net = out[f"{prefix}net"]
    has = out[f"{prefix}n"] > 0 if f"{prefix}n" in out.columns else net.notna()
    lab = np.select([net > dead_zone, net < -dead_zone], ["positive", "negative"], "neutral")
    out[f"{prefix}label"] = np.where(has, lab, "")
    return out


# ----------------------------------------------------------------------------
# 4. Frame-level convenience
# ----------------------------------------------------------------------------

TURN_COLS = ["finbert_sentiment", "finbert_score", "finbert_net", "finbert_p_pos", "finbert_p_neg", "finbert_p_neu", "finbert_net_prob"]
SENT_COLS = ["finbert_sent_label", "finbert_sent_net", "finbert_sent_pos_share", "finbert_sent_neg_share", "finbert_sent_n", "finbert_sent_neg_max"]
LM_COLS = ["ldsa_sentiment", "ldsa_net", "lm_pos_n", "lm_neg_n", "lm_unc_n", "lm_constr_n", "lm_lit_n", "lm_n_tok", "lm_uncertainty", "lm_hedge", "lm_source"]


def _prefixed(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    if not prefix:
        return df
    return df.rename(columns={c: f"{prefix}{c}" for c in df.columns})


def score_frame(
    df: pd.DataFrame,
    text_col: str,
    *,
    scorer: FinBertScorer | None = None,
    lm: LMScorer | None = None,
    unit: str = "both",
    prefix: str = "",
    mgmt_names: Sequence[str] | None = None,
    vocab: set[str] | None = None,
    dead_zone: float = DEAD_ZONE,
) -> pd.DataFrame:
    """Add sentiment columns for ``text_col``. ``unit`` in {"turn", "sentence", "both"}.

    ``prefix`` lets the same call score question_/answer_ columns on qa_pairs.
    Existing columns with the same names are replaced.
    """
    if unit not in {"turn", "sentence", "both"}:
        raise ValueError("unit must be turn | sentence | both")
    texts = df[text_col].tolist()
    if vocab is None:
        vocab = build_vocab(texts)
    clean = [normalise_for_sentiment(t, vocab=vocab, mgmt_names=mgmt_names) for t in texts]
    parts = []
    if scorer is not None and unit in {"turn", "both"}:
        parts.append(scorer.score_turns(clean))
    if scorer is not None and unit in {"sentence", "both"}:
        parts.append(scorer.score_sentences(clean, dead_zone=dead_zone))
    if lm is not None:
        parts.append(lm.score_many(clean))
    if not parts:
        return df
    add = _prefixed(pd.concat(parts, axis=1), prefix)
    out = df.drop(columns=[c for c in add.columns if c in df.columns]).reset_index(drop=True)
    return pd.concat([out, add.reset_index(drop=True)], axis=1)


def score_corpus(corpus: pd.DataFrame, *, all_turns: pd.DataFrame | None = None, **kw) -> pd.DataFrame:
    """Stage 3.1 + 3.2 on corpus_analyst (analyst turns, column ``text``)."""
    names = management_names_from_turns(all_turns)
    return score_frame(corpus, "text", mgmt_names=names, **kw)


def score_qa(qa: pd.DataFrame, *, all_turns: pd.DataFrame | None = None, scorer=None, lm=None, unit="both", **kw) -> pd.DataFrame:
    """Stage 3.1b on qa_pairs: question_* and answer_* columns.

    Keeps the legacy names ``question_sentiment / question_score / question_net`` and
    ``answer_*`` (turn unit), adds ``question_sent_*`` / ``answer_sent_*`` and LM columns.
    """
    names = management_names_from_turns(all_turns)
    vocab = build_vocab(pd.concat([qa["question_text"], qa["answer_text"]]).tolist())
    out = qa
    for side in ("question", "answer"):
        scored = score_frame(
            out[[f"{side}_text"]].rename(columns={f"{side}_text": "t"}),
            "t",
            scorer=scorer,
            lm=lm,
            unit=unit,
            mgmt_names=names,
            vocab=vocab,
            **kw,
        ).drop(columns=["t"])
        ren = {}
        for c in scored.columns:
            if c.startswith("finbert_sent_"):
                ren[c] = f"{side}_sent_{c[len('finbert_sent_'):]}"
            elif c.startswith("finbert_"):
                ren[c] = f"{side}_{c[len('finbert_'):]}"
            else:
                ren[c] = f"{side}_{c}"
        scored = scored.rename(columns=ren)
        # legacy names expected downstream
        scored = scored.rename(
            columns={f"{side}_sentiment": f"{side}_sentiment", f"{side}_score": f"{side}_score", f"{side}_net": f"{side}_net"}
        )
        out = out.drop(columns=[c for c in scored.columns if c in out.columns]).reset_index(drop=True)
        out = pd.concat([out, scored.reset_index(drop=True)], axis=1)
    return out


def aggregate(df: pd.DataFrame, by: Sequence[str], *, net_cols: Sequence[str] | None = None, label_col: str = "finbert_sentiment") -> pd.DataFrame:
    """Mean nets + label shares + n per group. n always present (M8)."""
    net_cols = list(net_cols or [c for c in ("finbert_net", "finbert_net_prob", "finbert_sent_net", "ldsa_net", "lm_uncertainty", "lm_hedge") if c in df.columns])
    g = df.groupby(list(by))
    out = g.size().rename("n").reset_index()
    for c in net_cols:
        out = out.merge(g[c].mean().rename(f"mean_{c}").reset_index(), on=list(by))
    if label_col in df.columns:
        for lab in ("negative", "positive"):
            s = g[label_col].apply(lambda x, l=lab: float((x == l).mean())).rename(f"{lab}_share").reset_index()
            out = out.merge(s, on=list(by))
    return out


# ----------------------------------------------------------------------------
# 5. CLI — score tables in data/boe.sqlite
# ----------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> None:
    from store import configure, has_df, load_df, save_df, save_json

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", action="store_true", help="score corpus_analyst.text")
    ap.add_argument("--qa", action="store_true", help="score qa_pairs question/answer")
    ap.add_argument("--unit", default="both", choices=["turn", "sentence", "both"])
    ap.add_argument("--model", default=FINBERT)
    ap.add_argument("--device", default=None)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lexicon", default="lm", choices=["lm", "legacy"])
    ap.add_argument("--dead-zone", type=float, default=DEAD_ZONE)
    ap.add_argument("--no-finbert", action="store_true", help="lexicon only (fast)")
    args = ap.parse_args(argv)
    if not (args.corpus or args.qa):
        ap.error("pass --corpus and/or --qa")

    configure(memory=False)
    all_turns = load_df("all_turns") if has_df("all_turns") else None
    scorer = None if args.no_finbert else FinBertScorer(args.model, device=args.device, batch_size=args.batch_size)
    lm = LMScorer(args.lexicon)
    print(f"device={scorer.device if scorer else 'n/a'} model={args.model} lexicon={lm.source}")

    summary: dict = {"model": args.model, "lexicon": lm.source, "unit": args.unit, "dead_zone": args.dead_zone}
    if args.corpus:
        corpus = load_df("corpus_analyst")
        scored = score_corpus(corpus, all_turns=all_turns, scorer=scorer, lm=lm, unit=args.unit, dead_zone=args.dead_zone)
        save_df("corpus_analyst", scored)
        summary["corpus"] = _dist(scored, "finbert_sentiment", "finbert_sent_label", "ldsa_sentiment")
        print("corpus_analyst", len(scored), json.dumps(summary["corpus"], indent=1))
    if args.qa:
        qa = load_df("qa_pairs")
        scored = score_qa(qa, all_turns=all_turns, scorer=scorer, lm=lm, unit=args.unit, dead_zone=args.dead_zone)
        save_df("qa_pairs", scored)
        save_df("behavioural_signals", scored)
        summary["qa"] = {
            "question": _dist(scored, "question_sentiment", "question_sent_label", "question_ldsa_sentiment"),
            "answer": _dist(scored, "answer_sentiment", "answer_sent_label", "answer_ldsa_sentiment"),
        }
        # keep state_summary in step (mean question/answer nets per bank-quarter)
        if has_df("state_summary"):
            ss = load_df("state_summary")
            extra = scored.groupby(["bank", "quarter"], as_index=False).agg(
                mean_question_net=("question_net", "mean"),
                mean_answer_net=("answer_net", "mean"),
                mean_question_sent_net=("question_sent_net", "mean") if "question_sent_net" in scored.columns else ("question_net", "mean"),
                mean_answer_sent_net=("answer_sent_net", "mean") if "answer_sent_net" in scored.columns else ("answer_net", "mean"),
                mean_answer_hedge=("answer_lm_hedge", "mean") if "answer_lm_hedge" in scored.columns else ("answer_net", "mean"),
            )
            keep = [c for c in ss.columns if c not in extra.columns or c in ("bank", "quarter")]
            save_df("state_summary", ss[keep].merge(extra, on=["bank", "quarter"], how="left"))
        print("qa_pairs", len(scored), json.dumps(summary["qa"], indent=1))
    save_json("sentiment_run", summary)


def _dist(df: pd.DataFrame, *cols: str) -> dict:
    out = {}
    for c in cols:
        if c in df.columns:
            vc = df[c].replace("", np.nan).value_counts(dropna=True)
            out[c] = {k: int(v) for k, v in vc.items()}
    return out


if __name__ == "__main__":
    main()

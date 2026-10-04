"""Stage 2 topic helpers (BERTopic / LDA / drift timestamps).

Quarter labels in this corpus are not ISO dates. ``2024-q1`` is parseable
by pandas; ``2024-interim`` and ``2024-annual`` are not, and the old
fallback kept only the year → 1 Jan — so H1 and FY collapsed onto Q1 and
killed the drift chart. Unparseable values used to become 2026-01-01
(fake recency). This module maps each label to a distinct month and
returns NaT for junk so callers can drop it.
"""
from __future__ import annotations

import os
import re
from typing import Any, Iterable, Sequence

import pandas as pd

# Distinct month-days so q1/q2/q3/q4/interim/annual in one year never collide.
# Numbered quarters follow pandas' 2024-qN starts. HSBC interim ≠ Q1 (H1 mid);
# annual/FY sits after Q4. Protocol still joins interim≡q2 via calendar_period.
_MONTH_DAY = {
    "q1": (1, 1),
    "1q": (1, 1),
    "q2": (4, 1),
    "2q": (4, 1),
    "q3": (7, 1),
    "3q": (7, 1),
    "q4": (10, 1),
    "4q": (10, 1),
    "interim": (6, 30),
    "h1": (6, 30),
    "annual": (12, 31),
    "fy": (12, 31),
}

_LLM_TRUE = {"1", "true", "yes", "on"}


def _llm_opt_in() -> bool:
    return os.environ.get("BOE_USE_LLM_PREPROCESSING", "").strip().lower() in _LLM_TRUE


def clean_timestamp(val) -> pd.Timestamp:
    """Map a corpus quarter/date label to a real timestamp, or NaT."""
    if val is None or (isinstance(val, float) and pd.isna(val)) or pd.isna(val):
        return pd.NaT
    if isinstance(val, pd.Timestamp):
        return val if not pd.isna(val) else pd.NaT

    val_str = str(val).strip().lower()
    if not val_str or val_str in {"nan", "nat", "none"}:
        return pd.NaT

    m = re.match(r"((?:19|20)\d{2})[-_]?(.*)$", val_str)
    if m:
        year, rest = m.group(1), (m.group(2) or "").strip()
        md = _MONTH_DAY.get(rest)
        if md:
            return pd.Timestamp(year=int(year), month=md[0], day=md[1])

    parsed = pd.to_datetime(val_str, errors="coerce")
    if pd.isna(parsed):
        return pd.NaT
    return pd.Timestamp(parsed)


_clean_timestamp = clean_timestamp


def timestamps_for_drift(corpus_df: pd.DataFrame) -> pd.Series:
    """Prefer ``date``, else ``quarter``. Junk → NaT (never a fake 2026)."""
    n = len(corpus_df)
    if "date" in corpus_df.columns:
        ts = corpus_df["date"].map(clean_timestamp)
        if int(ts.notna().sum()) >= max(3, n // 10):
            return ts
    if "quarter" in corpus_df.columns:
        return corpus_df["quarter"].map(clean_timestamp)
    return pd.Series([pd.NaT] * n, index=corpus_df.index)


def get_bertopic_input_column(corpus_df: pd.DataFrame) -> str:
    """Column BERTopic actually reads. LLM paraphrase is opt-in only."""
    if _llm_opt_in() and "llm_preprocessed_text" in corpus_df.columns:
        return "llm_preprocessed_text"
    if "clean_text" in corpus_df.columns:
        return "clean_text"
    if "text" in corpus_df.columns:
        return "text"
    raise ValueError("corpus has no text / clean_text / llm_preprocessed_text column")


def get_lda_input_column(corpus_df: pd.DataFrame) -> str:
    """LDA must score the same text BERTopic modelled."""
    return get_bertopic_input_column(corpus_df)


def get_min_topic_size(n_docs: int) -> int:
    """Grow with corpus size. The old ``min(8, n//20)`` was 8 for anything ≳160 rows."""
    n = max(int(n_docs), 1)
    return max(4, min(40, n // 50))


def get_nr_bins(date_min, date_max, target_granularity: str = "quarter") -> int:
    """Bin count so a 20-year corpus is not smeared into 10 coarse buckets."""
    start, end = pd.Timestamp(date_min), pd.Timestamp(date_max)
    if pd.isna(start) or pd.isna(end) or end <= start:
        return 1
    span_days = float((end - start).days)
    if target_granularity == "year":
        width = 365.25
    elif target_granularity == "month":
        width = 30.44
    else:
        width = 91.25
    return max(1, int(round(span_days / width)))


def fit_bertopic(
    docs: Sequence[str],
    seed: int = 42,
    *,
    embedding_model: Any = None,
    vectorizer_model: Any = None,
    min_topic_size: int | None = None,
):
    """Fit BERTopic with a seeded UMAP so topic ids can be reproduced."""
    from bertopic import BERTopic
    from sentence_transformers import SentenceTransformer
    from umap import UMAP

    docs = ["" if d is None else str(d) for d in docs]
    n = len(docs)
    if min_topic_size is None:
        min_topic_size = get_min_topic_size(n)
    min_topic_size = max(2, min(int(min_topic_size), max(2, n // 2)))
    if embedding_model is None:
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    n_neighbors = max(2, min(15, n - 1))
    n_components = max(2, min(5, n - 2)) if n > 3 else 2
    umap_model = UMAP(
        n_neighbors=n_neighbors,
        n_components=n_components,
        min_dist=0.0,
        metric="cosine",
        random_state=int(seed),
    )
    topic_model = BERTopic(
        embedding_model=embedding_model,
        umap_model=umap_model,
        vectorizer_model=vectorizer_model,
        min_topic_size=min_topic_size,
        calculate_probabilities=False,
        verbose=False,
    )
    topics, _ = topic_model.fit_transform(docs)
    return topic_model, [int(t) for t in topics]


def get_or_rebuild_topic_model(
    docs: Sequence[str],
    topic_model: Any = None,
    topics: Sequence[int] | None = None,
    seed: int = 42,
):
    """Rebuild from docs when a fresh kernel has no ``topic_model`` in scope."""
    if topic_model is not None and topics is not None:
        return topic_model, list(topics)
    return fit_bertopic(docs, seed=seed)


def score_lda(corpus_df: pd.DataFrame, n_topics: int | None = None):
    """LDA on the same column BERTopic used. Missing ``clean_text`` is not a KeyError."""
    from gensim import corpora
    from gensim.models import LdaModel
    from gensim.models.coherencemodel import CoherenceModel

    col = get_lda_input_column(corpus_df)
    tokenised = [str(x).split() for x in corpus_df[col].fillna("").astype(str)]
    dictionary = corpora.Dictionary(tokenised)
    no_below = 2 if len(tokenised) >= 20 else 1
    dictionary.filter_extremes(no_below=no_below, no_above=0.9)
    if len(dictionary) == 0:
        dictionary = corpora.Dictionary(tokenised)
    bow = [dictionary.doc2bow(doc) for doc in tokenised]
    k = n_topics if n_topics is not None else min(10, max(1, len(corpus_df) // 8 or 1))
    k = max(1, min(int(k), max(1, len(dictionary))))
    lda_model = LdaModel(
        corpus=bow,
        id2word=dictionary,
        num_topics=k,
        random_state=42,
        passes=5 if len(tokenised) >= 20 else 2,
    )
    try:
        coherence = float(
            CoherenceModel(
                model=lda_model,
                texts=tokenised,
                dictionary=dictionary,
                coherence="c_v",
                processes=1,
            ).get_coherence()
        )
    except Exception:
        coherence = float("nan")
    return lda_model, coherence


def docs_from_corpus(corpus_df: pd.DataFrame) -> list[str]:
    col = get_bertopic_input_column(corpus_df)
    return corpus_df[col].fillna("").astype(str).tolist()

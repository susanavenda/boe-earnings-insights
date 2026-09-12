"""Generate A2 notebook artifacts without BERTopic re-fit."""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from gensim import corpora
from gensim.models import LdaModel
from gensim.models.coherencemodel import CoherenceModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from store import load_df, save_bytes, save_df  # noqa: E402


def main():
    corpus_df = load_df("corpus_analyst")
    print("corpus", len(corpus_df))

    tokenised = [str(doc).split() for doc in corpus_df["clean_text"].fillna("")]
    dictionary = corpora.Dictionary(tokenised)
    dictionary.filter_extremes(no_below=2, no_above=0.5)
    bow_corpus = [dictionary.doc2bow(doc) for doc in tokenised]
    n_topics = min(10, max(3, len(corpus_df) // 8))
    lda_model = LdaModel(
        corpus=bow_corpus,
        id2word=dictionary,
        num_topics=n_topics,
        random_state=42,
        passes=10,
    )
    lda_topics_words = [
        [w for w, _ in lda_model.show_topic(i, topn=10)] for i in range(n_topics)
    ]
    cm = CoherenceModel(
        topics=lda_topics_words,
        texts=tokenised,
        dictionary=dictionary,
        coherence="c_v",
    )
    c_v = float(cm.get_coherence())
    coherence_df = pd.DataFrame(
        [{"model": "LDA", "n_topics": n_topics, "coherence_c_v": c_v}]
    )
    save_df("topic_coherence", coherence_df)
    print("coherence", coherence_df)

    known_events = pd.DataFrame(
        [
            {
                "bank": "hsbc",
                "quarter": "2025-interim",
                "finbert_note": "Softest interim print in sample",
                "event_context": "Tariffs / BoCom impairment questions dominate Topic 1",
                "aligns_with_topics": "Yes — Topic 1 impairment / cost",
            },
            {
                "bank": "barclays",
                "quarter": "2025-q2",
                "finbert_note": "Thin / neutral FinBERT print",
                "event_context": "Short Q&A; peer quality gate relevant",
                "aligns_with_topics": "Weak peer contrast",
            },
            {
                "bank": "hsbc",
                "quarter": "2025-annual",
                "finbert_note": "Year-end packs — denser metric discussion",
                "event_context": (
                    "Full-year CET1, income, costs, impairment all in IR packs "
                    "→ best window for structured-vs-unstructured compare"
                ),
                "aligns_with_topics": "Mixed; use for metric tagging QA",
            },
        ]
    )
    save_df("known_events_crosscheck", known_events)

    shift = corpus_df.groupby(["bank", "quarter", "topic"], as_index=False).agg(
        finbert_net=("finbert_net", "mean"), n=("finbert_net", "size")
    )
    save_df("sentiment_topic_quarter", shift)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    for ax, bank in zip(axes, ["hsbc", "barclays"]):
        sub = shift[shift["bank"] == bank]
        pivot = sub.pivot_table(
            index="topic", columns="quarter", values="finbert_net", aggfunc="mean"
        )
        cols = sorted(
            pivot.columns,
            key=lambda q: (
                q[:4],
                0 if "q1" in q else 1 if "interim" in q or "q2" in q else 2 if "q3" in q else 3,
                q,
            ),
        )
        pivot = pivot.reindex(columns=cols)
        sns.heatmap(
            pivot, ax=ax, cmap="RdYlGn", center=0, annot=True, fmt=".2f", linewidths=0.3
        )
        ax.set_title(f"{bank.upper()} FinBERT net by topic×quarter")
    plt.tight_layout()
    import io

    buf = io.BytesIO()
    fig.savefig(buf, dpi=120, bbox_inches="tight")
    save_bytes("sentiment_topic_quarter.png", buf.getvalue(), mime="image/png")
    print("heatmap rows", len(shift))

    quarter_to_period = {
        "2025-q1": "2025-H1q1",
        "2025-interim": "2025-H1",
        "2025-q2": "2025-H1",
        "2025-q3": "2025-Q3",
        "2025-annual": "2025-FY",
        "2026-q1": "2026-H1q1",
        "2026-interim": "2026-H1",
        "2026-q2": "2026-H1",
    }
    peer = corpus_df.groupby(["bank", "quarter"], as_index=False).agg(
        sentiment_net=("finbert_net", "mean")
    )
    peer["calendar_period"] = peer["quarter"].map(quarter_to_period).fillna(peer["quarter"])
    save_df("peer_matched_quarters", peer)
    both = int(peer.groupby("calendar_period")["bank"].nunique().ge(2).sum())
    pivot = peer.pivot_table(
        index="calendar_period", columns="bank", values="sentiment_net", aggfunc="mean"
    )
    gap = (pivot["hsbc"] - pivot["barclays"]).dropna()
    print("matched both-bank periods", both)
    print(gap)
    print("OK → data/boe.sqlite")


if __name__ == "__main__":
    main()

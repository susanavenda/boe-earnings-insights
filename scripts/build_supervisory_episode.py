#!/usr/bin/env python3
"""Build supervisory episode artifacts for one or more bank×quarter cases."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from periods import calendar_period  # noqa: E402
from store import load_df, save_df, save_json  # noqa: E402

PROC = ROOT / "data" / "processed"

# Default case studies for A2/A3
EPISODES = [
    {
        "id": "hsbc_2025_h1",
        "bank": "hsbc",
        "quarter": "2025-interim",
        "struct_quarter": "2025-q2",
        "calendar_period": "2025-H1",
        "label": "HSBC 2025-interim (H1)",
    },
    {
        "id": "barclays_2026_h1",
        "bank": "barclays",
        "quarter": "2026-q2",
        "struct_quarter": "2026-q2",
        "calendar_period": "2026-H1",
        "label": "Barclays 2026-q2 (H1)",
    },
    {
        "id": "cs_2022_q4",
        "bank": "credit_suisse",
        "quarter": "2022-q4",
        "struct_quarter": "2022-q4",
        "calendar_period": "2022-FY",
        "label": "Credit Suisse 2022-q4 (FY)",
    },
]

METRIC_KW = {
    "credit_impairment": ["impairment", "ecl", "stage 2", "credit cost", "cost of risk", "viu", "npl"],
    "operating_costs": ["cost", "costs", "efficiency", "expense"],
    "cet1_ratio": ["cet1", "capital"],
    "total_income": ["nii", "income", "revenue", "hibor", "fee"],
}


def clip(text: str, n: int = 280) -> str:
    t = re.sub(r"\s+", " ", str(text)).strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def build_protocol() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "rule_id": "A1",
                "severity": "alert",
                "condition": "Topic 1 negative share rises vs prior print AND credit_impairment narrative disagrees with reported direction",
                "action": "Desk review: pull Q&A quotes + ECL pack; escalate if both persist next quarter",
            },
            {
                "rule_id": "A2",
                "severity": "alert",
                "condition": "Matched peer gap (HSBC−Barclays) < −0.10 on H1/FY, both banks n≥3, and peer side not 100% FinBERT-neutral",
                "action": "Compare cost/impairment themes across banks; check if idiosyncratic or sector",
            },
            {
                "rule_id": "A3",
                "severity": "watch",
                "condition": "FinBERT net soft (< −0.08) but structured metrics agree with narrative",
                "action": "Log only — tone soft without metric contradiction",
            },
            {
                "rule_id": "N1",
                "severity": "null",
                "condition": "Topics stable, FinBERT net ≈ flat, structured↔unstructured agree",
                "action": "Report ‘no early-warning edge from Q&A this quarter’ — valid outcome",
            },
        ]
    )


def build_one(corp, reported, peer, spec: dict) -> dict:
    bank, quarter = spec["bank"], spec["quarter"]
    ep = corp[(corp["bank"] == bank) & (corp["quarter"] == quarter)].copy()
    ep_net = float(ep["finbert_net"].mean()) if len(ep) else float("nan")
    topic_share = (
        ep.groupby("topic")
        .agg(
            n=("text", "size"),
            finbert_net=("finbert_net", "mean"),
            neg_share=("finbert_sentiment", lambda s: (s == "negative").mean()),
        )
        .reset_index()
    )

    struct = reported[
        (reported["bank"].str.lower() == bank) & (reported["quarter"] == spec["struct_quarter"])
    ].copy()

    period = spec["calendar_period"]
    # Build peer sides from corpus (not pre-agg alone) so missing ≠ silent zero
    corp_p = corp.copy()
    corp_p["calendar_period"] = corp_p["quarter"].map(calendar_period)
    side = (
        corp_p[corp_p["calendar_period"] == period]
        .groupby("bank")
        .agg(
            sentiment_net=("finbert_net", "mean"),
            n=("text", "size"),
            non_neutral_share=("finbert_sentiment", lambda s: (s != "neutral").mean()),
        )
    )
    hsbc_row = side.loc["hsbc"] if "hsbc" in side.index else None
    bar_row = side.loc["barclays"] if "barclays" in side.index else None
    peer_gap = None
    peer_hsbc_net = peer_barclays_net = None
    peer_hsbc_n = peer_barclays_n = 0
    peer_hsbc_nn = peer_barclays_nn = None
    peer_usable_for_a2 = False
    peer_caveat = None
    if hsbc_row is not None and bar_row is not None:
        peer_hsbc_net = float(hsbc_row["sentiment_net"])
        peer_barclays_net = float(bar_row["sentiment_net"])
        peer_hsbc_n = int(hsbc_row["n"])
        peer_barclays_n = int(bar_row["n"])
        peer_hsbc_nn = float(hsbc_row["non_neutral_share"])
        peer_barclays_nn = float(bar_row["non_neutral_share"])
        peer_gap = peer_hsbc_net - peer_barclays_net
        both_enough = peer_hsbc_n >= 3 and peer_barclays_n >= 3
        # Trivial all-neutral peer → gap equals the other bank's net; not informative for A2 alert
        informative = peer_hsbc_nn > 0 and peer_barclays_nn > 0
        peer_usable_for_a2 = bool(both_enough and informative)
        if both_enough and not informative:
            peer_caveat = (
                f"Matched {period} has both banks, but one side is 100% FinBERT-neutral "
                f"(HSBC net={peer_hsbc_net:.3f}, n={peer_hsbc_n}, non-neut={peer_hsbc_nn:.0%}; "
                f"Barclays net={peer_barclays_net:.3f}, n={peer_barclays_n}, non-neut={peer_barclays_nn:.0%}). "
                f"Gap {peer_gap:.3f} is not treated as an A2 alert."
            )
    elif hsbc_row is None or bar_row is None:
        peer_caveat = f"No matched peer for {period}: missing {'HSBC' if hsbc_row is None else 'Barclays'} turns."

    # A2 is HSBC−Barclays only. Out-of-sample banks (CS) must not inherit that gap.
    if bank not in {"hsbc", "barclays"}:
        peer_gap = None
        peer_usable_for_a2 = False
        peer_caveat = "Peer gap is HSBC−Barclays only; n/a for out-of-sample banks."

    briefs = []
    for metric, kws in METRIC_KW.items():
        hits = ep[ep["text"].str.lower().apply(lambda t: any(k in t for k in kws))]
        row_s = struct[struct["metric"] == metric]
        direction = row_s["direction"].iloc[0] if len(row_s) else "n/a"
        value = float(row_s["value"].iloc[0]) if len(row_s) else None
        prior = float(row_s["prior"].iloc[0]) if len(row_s) else None
        if hits.empty:
            briefs.append(
                {
                    "episode_id": spec["id"],
                    "bank": bank,
                    "quarter": quarter,
                    "metric": metric,
                    "reported_direction": direction,
                    "reported_value": value,
                    "reported_prior": prior,
                    "n_qa_hits": 0,
                    "qa_finbert_net": None,
                    "narrative_direction": None,
                    "source_quote": None,
                    "speaker": None,
                    "claim": f"Reported {metric} direction={direction} on {spec['struct_quarter']}; no clear Q&A hit.",
                    "faithful": None,  # missing narrative ≠ agreement
                }
            )
            continue
        best = hits.sort_values("finbert_score", ascending=False).iloc[0]
        qa_net = float(hits["finbert_net"].mean())
        narr = "up" if qa_net > 0.05 else "down" if qa_net < -0.05 else "flat"
        agrees = narr == direction or (direction == "flat" and narr == "flat")
        briefs.append(
            {
                "episode_id": spec["id"],
                "bank": bank,
                "quarter": quarter,
                "metric": metric,
                "reported_direction": direction,
                "reported_value": value,
                "reported_prior": prior,
                "n_qa_hits": int(len(hits)),
                "qa_finbert_net": qa_net,
                "narrative_direction": narr,
                "source_quote": clip(best["text"], 320),
                "speaker": best.get("speaker"),
                "claim": (
                    f"Reported {metric} moved {direction} ({prior}→{value}); "
                    f"Q&A tone on related turns is {narr} (net={qa_net:.2f})."
                ),
                "faithful": bool(agrees),
            }
        )

    briefs_df = pd.DataFrame(briefs)
    t1 = ep[ep["topic"] == 1]
    t1_neg = float((t1["finbert_sentiment"] == "negative").mean()) if len(t1) else 0.0
    impair = briefs_df[briefs_df["metric"] == "credit_impairment"]
    impair_faithful = impair.iloc[0]["faithful"] if len(impair) else None
    impair_disagree = (impair_faithful is False)  # None (no Q&A) is not disagreement

    fired = []
    if t1_neg >= 0.2 and impair_disagree:
        fired.append("A1")
    if peer_usable_for_a2 and peer_gap is not None and peer_gap < -0.10:
        fired.append("A2")
    if ep_net < -0.08 and impair_faithful is not False:
        # soft tone; only A3 when impairment does not actively disagree (True or None)
        fired.append("A3")
    if not fired:
        fired.append("N1")

    if "A1" in fired:
        verdict = "ALERT — Topic 1 negatives + impairment narrative vs pack disagreement"
    elif "A2" in fired:
        verdict = "ALERT — large matched peer gap (HSBC softer than Barclays on H1/FY window)"
    elif "A3" in fired:
        verdict = "WATCH — soft Q&A tone but narrative broadly agrees with pack directions"
    else:
        verdict = "NULL — no early-warning edge from Q&A this quarter"

    t1_n = int(topic_share.loc[topic_share.topic == 1, "n"].iloc[0]) if (topic_share.topic == 1).any() else 0

    quotes = (
        ep.sort_values(["finbert_sentiment", "finbert_score"], ascending=[True, False])
        .head(5)[["speaker", "firm", "topic", "finbert_sentiment", "finbert_score", "text"]]
        .assign(text=lambda d: d["text"].map(lambda t: clip(t, 400)))
        .assign(episode_id=spec["id"], bank=bank, quarter=quarter)
    )

    episode = {
        "id": spec["id"],
        "label": spec["label"],
        "bank": bank,
        "quarter": quarter,
        "calendar_period": period,
        "struct_quarter": spec["struct_quarter"],
        "n_turns": int(len(ep)),
        "finbert_net": ep_net,
        "topic1_turns": int(len(t1)),
        "topic1_neg_share": t1_neg,
        "peer_gap_hsbc_minus_barclays": peer_gap,
        "peer_hsbc_net": peer_hsbc_net,
        "peer_barclays_net": peer_barclays_net,
        "peer_hsbc_n": peer_hsbc_n,
        "peer_barclays_n": peer_barclays_n,
        "peer_hsbc_non_neutral_share": peer_hsbc_nn,
        "peer_barclays_non_neutral_share": peer_barclays_nn,
        "peer_usable_for_a2": peer_usable_for_a2,
        "peer_caveat": peer_caveat,
        "rules_fired": fired,
        "verdict": verdict,
        "headline": (
            f"{spec['label']}: FinBERT net {ep_net:.2f}; Topic 1={t1_n} turns; "
            f"peer on {period}: HSBC={peer_hsbc_net:.3f} (n={peer_hsbc_n}) vs "
            f"Barclays={peer_barclays_net:.3f} (n={peer_barclays_n}); gap={peer_gap:.3f}"
            + (f" — {peer_caveat}" if peer_caveat else "")
            if peer_gap is not None
            else (
                f"{spec['label']}: FinBERT net {ep_net:.2f}."
                + (f" {peer_caveat}" if peer_caveat else "")
            )
        ),
        "pitch_angle": verdict,
    }

    return {
        "episode": episode,
        "briefs": briefs_df,
        "quotes": quotes,
        "topic_share": topic_share.assign(episode_id=spec["id"], bank=bank, quarter=quarter),
        "timeline_rows": [
            {
                "episode_id": spec["id"],
                "date_anchor": period,
                "bank": bank,
                "event": f"{spec['label']} — supervisory episode window",
                "signal": f"finbert_net={ep_net:.3f}; Topic 1 dominates ({t1_n} turns)",
            },
            {
                "episode_id": spec["id"],
                "date_anchor": spec["struct_quarter"],
                "bank": bank,
                "event": "Structured data pack directions",
                "signal": "; ".join(f"{r.metric}={r.direction}" for r in struct.itertuples())
                or "no pack rows",
            },
            {
                "episode_id": spec["id"],
                "date_anchor": f"{period} peer",
                "bank": "both",
                "event": "Matched peer window",
                "signal": f"HSBC−Barclays gap={peer_gap:.3f}" if peer_gap is not None else "gap n/a",
            },
        ],
    }


def main(only_id: str | None = None):
    corp = load_df("corpus_analyst")
    reported = load_df("reported_metrics")
    peer = load_df("peer_matched_quarters")

    specs = [e for e in EPISODES if only_id is None or e["id"] == only_id]
    if not specs:
        raise SystemExit(f"No episode matched id={only_id}")

    protocol = build_protocol()
    save_df("alert_null_protocol", protocol)

    all_eps, all_briefs, all_quotes, all_topics, all_timeline = [], [], [], [], []
    for spec in specs:
        out = build_one(corp, reported, peer, spec)
        all_eps.append(out["episode"])
        all_briefs.append(out["briefs"])
        all_quotes.append(out["quotes"])
        all_topics.append(out["topic_share"])
        all_timeline.extend(out["timeline_rows"])

    briefs_df = pd.concat(all_briefs, ignore_index=True)
    quotes_df = pd.concat(all_quotes, ignore_index=True)
    topics_df = pd.concat(all_topics, ignore_index=True)
    timeline_df = pd.DataFrame(all_timeline)

    save_df("episode_metric_briefs", briefs_df)
    save_df("episode_quotes", quotes_df)
    save_df("episode_topic_share", topics_df)
    save_df("event_timeline", timeline_df)

    primary = all_eps[0]
    save_json("supervisory_episode", primary)
    save_json("supervisory_episodes", all_eps)

    if {"calendar_period", "bank", "sentiment_net"}.issubset(peer.columns):
        pivot = peer.pivot_table(
            index="calendar_period", columns="bank", values="sentiment_net", aggfunc="mean"
        )
        if "hsbc" in pivot.columns and "barclays" in pivot.columns:
            gap = pivot.copy()
            gap["gap"] = gap["hsbc"] - gap["barclays"]
            save_df("peer_gap_matched", gap.reset_index())

    print(json.dumps(all_eps, indent=2))
    print(f"wrote {len(all_eps)} episodes → data/boe.sqlite")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default=None, help="Optional single episode id")
    args = ap.parse_args()
    main(only_id=args.id)

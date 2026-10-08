#!/usr/bin/env python3
"""M4 round 2 - score the 43-pair blind second pass (tightened answer rule, 4 Oct).

Reads docs/assignment2/human_labels/sentiment_r2_labels_<name>.csv (one per coder) and
sentiment_r2_machine_key.csv. Reuses the metric code of ``score_sentiment_human.py`` so
round 1 and round 2 are computed the same way.

Reports
  * coder vs coder: raw %, Cohen's kappa, Krippendorff's alpha, confusion - question and answer.
    If ``sentiment_r2_review_changes_<name>.csv`` exists (cells a coder changed after seeing a
    review), the as-first-coded labels are scored too: that is the independent (blind) figure.
  * each machine unit vs each coder, vs the scorer's gold (majority; tie -> first-listed coder)
    and vs the consensus subset (pairs where the coders agree).
  * machine units: FinBERT turn, FinBERT sentence, LM lexicon (hidden key); LLM turn labels
    (llm_sentiment_labels.csv); LLM sentence-by-sentence (llm_sentiment_sentence_labels_r2.csv),
    aggregated here by a rule fixed before scoring; the keyword rule coder when its CSV is present.

LLM sentence aggregation (fixed a priori, mirrors ``finbert_sent_label``):
  net = mean over in-scope sentences of (+1 positive, 0 neutral, -1 negative);
  label = sign(net) outside +/- sentiment.DEAD_ZONE, else neutral.
  In scope = management sentences for the answer side and analyst sentences for the question side
  (the pack tells human coders to label the management content of a garbled answer block);
  if a block has no in-scope sentence, all its sentences are used. ``llm_sentence_all`` uses every
  sentence (sensitivity). ``llm_sentence_turn`` is the LLM's own overall label after the sentence pass.

Writes docs/assignment2/human_labels/sentiment_r2_agreement.json,
docs/assignment2/llm_sentiment_sentence_turns_r2.csv and store document ``sentiment_r2_agreement``.
"""
from __future__ import annotations

import json
import sys
from itertools import combinations
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_sentiment_human import LABELS, _norm, block, krippendorff_alpha_nominal, majority  # noqa: E402
from sentiment import DEAD_ZONE  # noqa: E402
from store import configure, save_json  # noqa: E402

HL = ROOT / "docs" / "assignment2" / "human_labels"
A2 = ROOT / "docs" / "assignment2"
KEY = HL / "sentiment_r2_machine_key.csv"
OUT_JSON = HL / "sentiment_r2_agreement.json"
LLM_CSV = A2 / "llm_sentiment_labels.csv"
LLM_SENT_CSV = A2 / "llm_sentiment_sentence_labels_r2.csv"
LLM_SENT_TURN_RAW = A2 / "llm_sentiment_sentence_turns_r2.csv"
KEYWORD_CSV = A2 / "keyword_rule_sentiment_labels.csv"
R1_JSON = HL / "sentiment_agreement.json"
SIDES = (("question", "q_label"), ("answer", "a_label"))
SIGN = {"negative": -1.0, "neutral": 0.0, "positive": 1.0}
SCOPE = {"question": "analyst", "answer": "management"}


def load_coders() -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """Current labels per coder, and as-first-coded labels where a review-changes file exists."""
    coders, blind = {}, {}
    for f in sorted(HL.glob("sentiment_r2_labels_*.csv")):
        name = f.stem.replace("sentiment_r2_labels_", "")
        if name == "template":
            continue
        df = pd.read_csv(f, dtype=str).fillna("")
        for c in ("q_label", "a_label"):
            df[c] = _norm(df[c])
        if not ((df["q_label"] != "") | (df["a_label"] != "")).any():
            print(f"skip {f.name}: no labels filled in")
            continue
        df = df.set_index("pair_id")
        coders[name] = df
        rc = HL / f"sentiment_r2_review_changes_{name}.csv"
        if rc.is_file():
            first = df.copy()
            ch = pd.read_csv(rc, dtype=str).fillna("")
            for r in ch.to_dict("records"):
                if r["field"] in ("q_label", "a_label") and r["pair_id"] in first.index:
                    assert first.at[r["pair_id"], r["field"]] == r["revised"].strip().lower(), r
                    first.at[r["pair_id"], r["field"]] = r["blind"].strip().lower()
            blind[name] = first
    return coders, blind


def sign_label(net: float) -> str:
    return "positive" if net > DEAD_ZONE else "negative" if net < -DEAD_ZONE else "neutral"


def aggregate_llm_sentences() -> pd.DataFrame | None:
    if not LLM_SENT_CSV.is_file():
        return None
    s = pd.read_csv(LLM_SENT_CSV, dtype={"pair_id": str}).fillna("")
    s["v"] = s["label"].map(SIGN)
    rows = []
    for (pid, side), g in s.groupby(["pair_id", "side"], sort=False):
        scoped = g[g["speaker"] == SCOPE[side]]
        use = scoped if len(scoped) else g
        rows.append({
            "pair_id": pid, "side": side, "n_sent": len(g), "n_in_scope": len(scoped),
            "n_pos": int((use["label"] == "positive").sum()), "n_neg": int((use["label"] == "negative").sum()),
            "net": round(float(use["v"].mean()), 4), "label": sign_label(float(use["v"].mean())),
            "net_all": round(float(g["v"].mean()), 4), "label_all": sign_label(float(g["v"].mean())),
        })
    agg = pd.DataFrame(rows)
    if LLM_SENT_TURN_RAW.is_file():
        prev = pd.read_csv(LLM_SENT_TURN_RAW, dtype={"pair_id": str}).fillna("")
        keep = [c for c in ("pair_id", "side", "llm_turn_label", "llm_turn_confidence", "llm_turn_rationale") if c in prev.columns]
        if len(keep) > 2:
            agg = agg.merge(prev[keep], on=["pair_id", "side"], how="left")
    agg.to_csv(LLM_SENT_TURN_RAW, index=False)
    return agg


def side_map(df: pd.DataFrame, side: str, col: str = "label") -> pd.Series:
    return _norm(df[df["side"] == side].drop_duplicates("pair_id").set_index("pair_id")[col])


def main() -> None:
    configure(memory=False)
    key = pd.read_csv(KEY, dtype={"pair_id": str}).set_index("pair_id")
    pairs = key.index
    units: dict[str, dict[str, pd.Series]] = {
        "finbert_turn": {"question": _norm(key["question_sentiment"]), "answer": _norm(key["answer_sentiment"])},
        "finbert_sentence": {"question": _norm(key["question_sent_label"]), "answer": _norm(key["answer_sent_label"])},
        "lm_lexicon": {"question": _norm(key["question_ldsa_sentiment"]), "answer": _norm(key["answer_ldsa_sentiment"])},
    }
    if LLM_CSV.is_file():
        llm = pd.read_csv(LLM_CSV, dtype=str).fillna("")
        units["llm_turn"] = {s: side_map(llm, s).reindex(pairs).fillna("") for s, _ in SIDES}
    agg = aggregate_llm_sentences()
    if agg is not None:
        units["llm_sentence"] = {s: side_map(agg, s).reindex(pairs).fillna("") for s, _ in SIDES}
        units["llm_sentence_all"] = {s: side_map(agg, s, "label_all").reindex(pairs).fillna("") for s, _ in SIDES}
        if "llm_turn_label" in agg.columns:
            units["llm_sentence_turn"] = {s: side_map(agg, s, "llm_turn_label").reindex(pairs).fillna("") for s, _ in SIDES}
    if KEYWORD_CSV.is_file():
        kw = pd.read_csv(KEYWORD_CSV, dtype=str).fillna("")
        units["keyword_rule"] = {s: side_map(kw, s).reindex(pairs).fillna("") for s, _ in SIDES}

    coders, blind = load_coders()
    names = list(coders)
    if not names:
        raise SystemExit("no filled sentiment_r2_labels_<name>.csv yet")
    lab = {n: {s: coders[n][c].reindex(pairs).fillna("") for s, c in SIDES} for n in names}
    gold = {s: pd.Series([majority([lab[n][s][p] for n in names]) for p in pairs], index=pairs) for s, _ in SIDES}
    agree = {s: pd.Series([len({lab[n][s][p] for n in names}) == 1 and lab[names[0]][s][p] in LABELS for p in pairs], index=pairs) for s, _ in SIDES}

    res: dict = {
        "round": 2, "n_pairs": int(len(pairs)), "coders": names,
        "gold_rule": "majority across coders; tie -> first-listed coder",
        "llm_sentence_rule": f"sign of mean sentence net outside +/-{DEAD_ZONE}; in scope = management (answer) / analyst (question); fixed before scoring",
        "label_dist": {n: {s: lab[n][s][lab[n][s].isin(LABELS)].value_counts().to_dict() for s, _ in SIDES} for n in names},
        "coder_vs_coder": {}, "machine_vs_human": {}, "machine_vs_machine_answer": {},
    }

    def cvc(src: dict, tag: str) -> None:
        for a, b in combinations(names, 2):
            for s, _ in SIDES:
                d = block(src[a][s], src[b][s], f"{a}_vs_{b}_{s}{tag}")
                d.pop("meets_m4_bar", None)
                rows = [[src[a][s][p] or None, src[b][s][p] or None] for p in pairs]
                d["krippendorff_alpha"] = krippendorff_alpha_nominal(rows)
                res["coder_vs_coder"][f"{a}_vs_{b}_{s}{tag}"] = d

    cvc(lab, "")
    if blind:
        first = {n: {s: (blind.get(n, coders[n]))[c].reindex(pairs).fillna("") for s, c in SIDES} for n in names}
        cvc(first, "_as_first_coded")
        res["review_changes"] = {n: int(sum((first[n][s] != lab[n][s]).sum() for s, _ in SIDES)) for n in blind}

    for unit, m in units.items():
        r = {}
        for s, _ in SIDES:
            r[s] = {"vs_gold": block(gold[s], m[s], f"{unit}_{s}_gold")}
            for n in names:
                r[s][f"vs_{n}"] = block(lab[n][s], m[s], f"{unit}_{s}_{n}")
            r[s]["vs_consensus"] = block(gold[s][agree[s]], m[s][agree[s]], f"{unit}_{s}_consensus")
            r[s]["pred_dist"] = m[s][m[s].isin(LABELS)].value_counts().to_dict()
        r["pooled_vs_gold"] = block(
            pd.concat([gold["question"], gold["answer"]], ignore_index=True),
            pd.concat([m["question"], m["answer"]], ignore_index=True), f"{unit}_pooled_gold")
        res["machine_vs_human"][unit] = r
    for a, b in combinations([u for u in units if u.startswith(("llm", "keyword"))], 2):
        d = block(units[a]["answer"], units[b]["answer"], f"{a}_vs_{b}_answer")
        res["machine_vs_machine_answer"][f"{a}_vs_{b}"] = {k: d.get(k) for k in ("n", "raw_agreement", "cohen_kappa")}

    if R1_JSON.is_file():
        r1 = json.loads(R1_JSON.read_text(encoding="utf-8")).get("coder_vs_coder", {})
        res["round1_coder_vs_coder"] = {k: {x: v.get(x) for x in ("n", "raw_agreement", "cohen_kappa")} for k, v in r1.items()}

    OUT_JSON.write_text(json.dumps(res, indent=2), encoding="utf-8")
    save_json("sentiment_r2_agreement", res)

    def f(d: dict) -> str:
        k = d.get("cohen_kappa")
        return f"{d.get('raw_agreement', 0):.0%} k={k:.2f} (n={d.get('n')})" if d.get("n") and k is not None else f"n={d.get('n')}"

    print("coder vs coder")
    for k, d in res["coder_vs_coder"].items():
        print(f"  {k:42s} {f(d)}  alpha={d['krippendorff_alpha']:.2f}")
    for s, _ in SIDES:
        print(f"machine vs human - {s}")
        for unit, r in res["machine_vs_human"].items():
            print(f"  {unit:18s} " + " | ".join(f"{k} {f(v)}" for k, v in r[s].items() if k != "pred_dist"))
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()

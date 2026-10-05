#!/usr/bin/env python3
"""M6 — score human answering-behaviour labels against the machine M6 signals.

Reads docs/assignment2/human_labels/behaviour_90_labels_<name>.csv (one file per coder;
columns pair_id, addressed, changed_topic, metric_given, answer_clean, note) and the
hidden key behaviour_90_machine_key.csv built by scripts/build_behaviour_gold_pack.py.

Machine values are recomputed from the pair text in the key with the *current*
behavioural_signals(), so the score always reflects the code that will ship.

Reports:
  * human vs human: raw % and Cohen's κ per question (when ≥2 coders)
  * directness (and directness_v2 if present) vs `addressed`: Spearman ρ, mean by label,
    AUC for separating "no" from "yes"
  * topic_substitution vs `changed_topic` on machine-measurable pairs, plus how often
    humans see a topic change on pairs the machine cannot measure
  * metric_coverage vs `metric_given`: was a metric asked (machine vs human), and when
    both say asked, was it given
  * answer_clean: share of answers that contain more than management's reply

Human gold = value all coders agree on (majority when ≥3); pairs without agreement are
left out of machine-vs-human and counted. The sample is stratified (substitution "yes"
oversampled), so rates describe the sample, not the corpus.

Writes docs/assignment2/human_labels/behaviour_agreement.json. Touches no sqlite table.
"""
from __future__ import annotations

import json
import sys
from itertools import combinations
from math import sqrt
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_a1_evidence import behavioural_signals  # noqa: E402
from build_behaviour_gold_pack import PACK  # noqa: E402

HL = ROOT / "docs" / "assignment2" / "human_labels"
KEY = HL / f"{PACK}_machine_key.csv"
OUT_JSON = HL / "behaviour_agreement.json"

QUESTIONS = {
    "addressed": ("yes", "partly", "no"),
    "changed_topic": ("yes", "no"),
    "metric_given": ("yes", "no", "na"),
    "answer_clean": ("yes", "no"),
}
ADDRESSED_ORDER = {"no": 0, "partly": 1, "yes": 2}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n <= 0:
        return None
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    margin = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return round(max(0.0, centre - margin), 3), round(min(1.0, centre + margin), 3)


def validate(df: pd.DataFrame, name: str, pair_ids: list[str]) -> pd.DataFrame:
    """Normalise a coder file; raise with every problem listed, not just the first."""
    out = df.copy()
    out["pair_id"] = out["pair_id"].astype(str).str.strip()
    problems = []
    missing_cols = [q for q in QUESTIONS if q not in out.columns]
    if missing_cols:
        raise ValueError(f"{name}: missing columns {missing_cols}")
    missing_ids = sorted(set(pair_ids) - set(out["pair_id"]))
    extra_ids = sorted(set(out["pair_id"]) - set(pair_ids))
    if missing_ids:
        problems.append(f"{len(missing_ids)} pair_ids missing (e.g. {missing_ids[:3]})")
    if extra_ids:
        problems.append(f"{len(extra_ids)} pair_ids not in the key (e.g. {extra_ids[:3]})")
    for q, allowed in QUESTIONS.items():
        out[q] = out[q].fillna("").astype(str).str.strip().str.lower()
        blank = out["pair_id"][out[q] == ""].tolist()
        bad = out.loc[(out[q] != "") & ~out[q].isin(allowed), ["pair_id", q]]
        if blank:
            problems.append(f"{q}: {len(blank)} blank (e.g. {blank[:3]})")
        if len(bad):
            problems.append(f"{q}: values not in {allowed}: {bad.head(3).to_dict('records')}")
    if problems:
        raise ValueError(f"{name}: " + "; ".join(problems))
    return out.set_index("pair_id")[list(QUESTIONS)]


def load_coders(hl: Path = HL) -> dict[str, pd.DataFrame]:
    return {
        f.stem.replace(f"{PACK}_labels_", ""): pd.read_csv(f, dtype=str)
        for f in sorted(hl.glob(f"{PACK}_labels_*.csv"))
        if f.stem != f"{PACK}_labels_template"
    }


def machine_signals(key: pd.DataFrame) -> pd.DataFrame:
    m = behavioural_signals(key[["pair_id", "question_text", "answer_text"]].copy())
    cols = [c for c in ("directness", "directness_v2", "metric_coverage", "topic_substitution", "substitution_measurable") if c in m.columns]
    return m.set_index("pair_id")[cols]


def agreement(a: pd.Series, b: pd.Series) -> dict:
    both = pd.concat([a, b], axis=1).dropna()
    n = len(both)
    if n == 0:
        return {"n": 0, "raw": None, "kappa": None}
    x, y = both.iloc[:, 0].astype(str), both.iloc[:, 1].astype(str)
    raw = float((x == y).mean())
    kappa = float(cohen_kappa_score(x, y)) if len(set(x) | set(y)) > 1 else None
    return {"n": n, "raw": round(raw, 3), "raw_95": wilson(int((x == y).sum()), n), "kappa": None if kappa is None else round(kappa, 3)}


def consensus(coders: dict[str, pd.DataFrame], q: str) -> pd.Series:
    """Agreed value per pair: unanimous for 2 coders, majority for ≥3, else NaN."""
    frame = pd.concat({name: df[q] for name, df in coders.items()}, axis=1)
    k = frame.shape[1]

    def pick(row: pd.Series):
        top = row.value_counts()
        return top.index[0] if top.iloc[0] > k / 2 else None

    return frame.apply(pick, axis=1)


def directness_block(score: pd.Series, addressed: pd.Series) -> dict:
    d = pd.concat([pd.to_numeric(score, errors="coerce"), addressed], axis=1, keys=["s", "a"]).dropna()
    out = {"n": len(d), "mean_by_label": {k: round(float(v), 3) for k, v in d.groupby("a")["s"].mean().items()}}
    if len(d) >= 3 and d["a"].nunique() > 1:
        out["spearman_rho"] = round(float(d["s"].corr(d["a"].map(ADDRESSED_ORDER), method="spearman")), 3)
    yn = d[d["a"].isin(["yes", "no"])]
    if yn["a"].nunique() == 2:
        out["auc_yes_vs_no"] = round(float(roc_auc_score(yn["a"] == "yes", yn["s"])), 3)
        out["n_yes_no"] = len(yn)
    return out


def machine_vs_human(machine: pd.DataFrame, gold: dict[str, pd.Series]) -> dict:
    res = {}
    for col in ("directness", "directness_v2"):
        if col in machine.columns:
            res[col] = directness_block(machine[col], gold["addressed"])

    meas = machine["substitution_measurable"].fillna(False).astype(bool)
    sub = pd.to_numeric(machine["topic_substitution"], errors="coerce").map({1.0: "yes", 0.0: "no"})
    res["substitution_measurable_pairs"] = agreement(sub[meas], gold["changed_topic"][meas])
    unmeas = gold["changed_topic"][~meas].dropna()
    res["human_topic_change_on_unmeasurable"] = {
        "n": len(unmeas),
        "share_yes": round(float((unmeas == "yes").mean()), 3) if len(unmeas) else None,
    }

    cov = pd.to_numeric(machine["metric_coverage"], errors="coerce")
    machine_asked = cov.notna().map({True: "asked", False: "not_asked"})
    human_asked = gold["metric_given"].map(lambda v: None if v is None or pd.isna(v) else ("not_asked" if v == "na" else "asked"))
    res["metric_asked"] = agreement(machine_asked, human_asked)
    both = cov.notna() & gold["metric_given"].isin(["yes", "no"])
    res["metric_given_when_both_asked"] = agreement(cov[both].map({1.0: "yes", 0.0: "no"}), gold["metric_given"][both])
    return res


def score(key: pd.DataFrame, coder_frames: dict[str, pd.DataFrame]) -> dict:
    ids = key["pair_id"].astype(str).tolist()
    coders = {name: validate(df, name, ids) for name, df in coder_frames.items()}
    machine = machine_signals(key).reindex(ids)
    result: dict = {
        "n_pairs": len(ids),
        "coders": sorted(coders),
        "sample_note": "Stratified sample (substitution 'yes' oversampled): rates describe the sample, not corpus prevalence.",
        "human_vs_human": {},
    }
    if len(coders) >= 2:
        for a, b in combinations(sorted(coders), 2):
            result["human_vs_human"][f"{a}_vs_{b}"] = {q: agreement(coders[a][q], coders[b][q]) for q in QUESTIONS}

    gold = {q: consensus(coders, q).reindex(ids) for q in QUESTIONS}
    result["agreed_pairs"] = {q: int(gold[q].notna().sum()) for q in QUESTIONS}
    result["machine_vs_human_gold"] = machine_vs_human(machine, gold)
    result["machine_vs_each_coder"] = {
        name: machine_vs_human(machine, {q: df[q].reindex(ids) for q in QUESTIONS}) for name, df in coders.items()
    }
    clean = gold["answer_clean"].dropna()
    k = int((clean == "no").sum())
    result["answer_not_clean"] = {"n": len(clean), "share": round(k / len(clean), 3) if len(clean) else None, "share_95": wilson(k, len(clean))}
    result["summary"] = summary_lines(result)
    return result


def summary_lines(r: dict) -> list[str]:
    lines = []
    for pair, block in r["human_vs_human"].items():
        a = block["addressed"]
        lines.append(f"Coders {pair}: addressed agree {a['raw']:.0%} (κ={a['kappa']}), n={a['n']}.")
    g = r["machine_vs_human_gold"]
    d = g.get("directness", {})
    if "auc_yes_vs_no" in d:
        lines.append(f"Directness separates human 'addressed yes' from 'no' with AUC {d['auc_yes_vs_no']} (n={d['n_yes_no']}; 0.5 = chance).")
    d2 = g.get("directness_v2", {})
    if "auc_yes_vs_no" in d2:
        lines.append(f"Directness v2 AUC {d2['auc_yes_vs_no']} (n={d2['n_yes_no']}).")
    s = g["substitution_measurable_pairs"]
    if s["n"]:
        lines.append(f"Substitution vs human 'changed topic' on {s['n']} measurable pairs: {s['raw']:.0%} agree (κ={s['kappa']}).")
    u = g["human_topic_change_on_unmeasurable"]
    if u["n"]:
        lines.append(f"Humans saw a topic change on {u['share_yes']:.0%} of {u['n']} pairs the machine cannot measure.")
    c = g["metric_given_when_both_asked"]
    if c["n"]:
        lines.append(f"Coverage vs human 'metric given' where both say a metric was asked: {c['raw']:.0%} agree (n={c['n']}).")
    ac = r["answer_not_clean"]
    if ac["n"]:
        lines.append(f"Answer text not clean (parser bleed or garbled) on {ac['share']:.0%} of {ac['n']} coded pairs.")
    lines.append(r["sample_note"])
    return lines


def main() -> None:
    if not KEY.is_file():
        raise SystemExit(f"{KEY} missing — run scripts/build_behaviour_gold_pack.py first")
    frames = load_coders()
    if not frames:
        raise SystemExit(f"No {PACK}_labels_<name>.csv yet — copy the template, code it, then re-run.")
    key = pd.read_csv(KEY, dtype={"pair_id": str})
    result = score(key, frames)
    OUT_JSON.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print("\n".join(result["summary"]))
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()

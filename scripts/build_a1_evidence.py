#!/usr/bin/env python3
"""A1 v0.1 evidence artefacts that the notebook previously only described.

Writes to data/boe.sqlite:
  corpus_manifest, qa_pairs, numeric_claims, numeric_claims_audit,
  behavioural_signals, prudential_map, state_summary

M3 open extraction is regex (value/unit/horizon). The 50-row audit table is
for humans to score; do not claim 0.8 precision until they do. Defined metric
list remains the fallback (reported_metrics).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from keywords import any_keyword, directness_v2, keyword_in_text  # noqa: E402
from periods import calendar_period, coverage_window, year_from_period  # noqa: E402
from store import configure, has_df, load_df, save_df  # noqa: E402

MONTHS = (
    "January|February|March|April|May|June|July|August|"
    "September|October|November|December"
)
DATE_RE = re.compile(rf"\b(\d{{1,2}}\s+(?:{MONTHS})\s+20\d{{2}})\b", re.I)
CLAIM_RE = re.compile(
    r"(?P<value>£?\s?\d+(?:,\d{3})*(?:\.\d+)?)\s*"
    r"(?P<unit>%|bps|bp|billion|bn|million|mn|m|ppt|\$bn|\$m)?",
    re.I,
)
HORIZON_RE = re.compile(
    r"\b(this quarter|this year|full year|fy\s*20\d{2}|20\d{2}|h1|h2|q[1-4]|guidance|going forward)\b",
    re.I,
)
METRIC_NEAR = re.compile(
    r"(revenue|income|nii|nim|fee|cost|opex|expense|impairment|ecl|"
    r"cet1|capital|rwa|bps|billion|million|percent|profit|rote)",
    re.I,
)
PERSON_NAME = re.compile(
    r"^[A-Z][A-Za-z\.\'\-]+(?:\s+[A-Z][A-Za-z\.\'\-]+){0,4}$"
)

METRIC_KW = {
    "total_income": ["revenue", "total income", "nii", "fee income", "net interest"],
    "operating_costs": ["cost", "costs", "efficiency", "opex", "expense"],
    "credit_impairment": ["impairment", "ecl", "loan loss", "credit loss", "cost of risk", "npl"],
    # "capital" alone is not CET1 ("capital markets"). "cost of risk" is impairment.
    "cet1_ratio": ["cet1", "capital ratio", "rwa", "tier 1"],
}

# A1 M7: eight prudential categories (Aidan dual-codes later)
PRUDENTIAL_8 = {
    "capital_adequacy": ["cet1", "capital", "rwa", "tier 1", "leverage", "buyback"],
    "liquidity_funding": ["liquidity", "deposit", "funding", "lcr", "nsfr", "loan-to-deposit"],
    "asset_quality_credit": ["impairment", "ecl", "npl", "credit", "stage 2", "stage 3", "cost of risk"],
    "profitability_earnings": ["income", "revenue", "nii", "nim", "rote", "profit", "fee"],
    "operational_efficiency": ["cost", "efficiency", "opex", "expense", "jaw"],
    "market_traded_risk": ["markets", "trading", "var", "structural hedge", "swap"],
    "conduct_operational": ["conduct", "operational risk", "cyber", "fraud", "control"],
    "business_model_strategy": ["strategy", "franchise", "wealth", "plan", "guidance", "growth"],
}

SEED_TO_8 = {
    "profitability": "profitability_earnings",
    "efficiency": "operational_efficiency",
    "asset_quality": "asset_quality_credit",
    "capital": "capital_adequacy",
}


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{3,}", str(text).lower()))


def seed_label(text: str) -> str:
    t = str(text).lower()
    hits = [
        b
        for b, keys in {
            "profitability": METRIC_KW["total_income"],
            "efficiency": METRIC_KW["operating_costs"],
            "asset_quality": METRIC_KW["credit_impairment"],
            "capital": METRIC_KW["cet1_ratio"],
        }.items()
        if any_keyword(t, keys)
    ]
    if not hits:
        return "untagged"
    return hits[0] if len(hits) == 1 else "mixed"


def prudential8_label(text: str) -> str:
    t = str(text).lower()
    scored = []
    for cat, keys in PRUDENTIAL_8.items():
        n = sum(1 for k in keys if keyword_in_text(t, k))
        if n:
            scored.append((n, cat))
    if not scored:
        return "untagged"
    scored.sort(reverse=True)
    return scored[0][1]


def infer_quarter(name: str) -> str:
    m = re.search(r"(20\d{2}).*?(q[1-4]|[1-4]q|interim|annual|fy|h1)", name.lower())
    if not m:
        return Path(name).stem
    y, p = m.group(1), m.group(2)
    mapping = {"1q": "q1", "2q": "q2", "3q": "q3", "4q": "q4", "fy": "annual", "h1": "interim"}
    return f"{y}-{mapping.get(p, p)}"


_OTHER_EVENT = (
    "equity-analysts",
    "equity_analysts",
    "analysts-meeting",
    "analysts_meeting",
)


def event_type_from_source(source: str) -> str:
    """results_call vs other. Keep the file; default analyses to results_call."""
    name = Path(str(source)).name.lower()
    if any(tok in name for tok in _OTHER_EVENT):
        return "other"
    return "results_call"


def coverage_by_bank_year(manifest: pd.DataFrame) -> pd.DataFrame:
    """Results-call counts per bank × year (HSBC / Barclays). Zero means absent, not a score."""
    t = manifest[manifest["kind"] == "transcript"].copy()
    t = t[t["bank"].isin(["hsbc", "barclays"])]
    if "event_type" not in t.columns:
        t["event_type"] = t["source"].map(event_type_from_source)
    t = t[t["event_type"] == "results_call"]
    t["year"] = t["quarter"].map(year_from_period)
    t = t.dropna(subset=["year"])
    t["year"] = t["year"].astype(int)
    counts = t.groupby(["year", "bank"]).size().unstack(fill_value=0)
    for col in ("hsbc", "barclays"):
        if col not in counts.columns:
            counts[col] = 0
    out = counts.reset_index()
    out["coverage_window"] = out["year"].map(lambda y: coverage_window(str(int(y))))
    return out[["year", "hsbc", "barclays", "coverage_window"]]


def _pdf_date(path: Path) -> str:
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            head = "\n".join((p.extract_text() or "") for p in pdf.pages[:2])[:4000]
        m = DATE_RE.search(head or "")
        return m.group(1) if m else ""
    except Exception:
        return ""


def build_manifest(raw_root: Path, structured_root: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(raw_root.rglob("*.pdf")) + sorted(structured_root.rglob("*.xlsx")):
        bank = (
            "hsbc"
            if "hsbc" in str(path).lower()
            else "barclays"
            if "barclays" in str(path).lower()
            else "credit_suisse"
            if "credit_suisse" in str(path).lower()
            else "unknown"
        )
        kind = "transcript" if path.suffix.lower() == ".pdf" else "results_pack"
        pub = _pdf_date(path) if path.suffix.lower() == ".pdf" else ""
        rows.append(
            {
                "bank": bank,
                "kind": kind,
                "source": path.name,
                "path": str(path.relative_to(ROOT)),
                "publication_date": pub,
                "quarter": infer_quarter(path.name),
                "event_type": event_type_from_source(path.name),
            }
        )
    df = pd.DataFrame(rows)
    n_t = int((df["kind"] == "transcript").sum())
    df.attrs["m1_note"] = (
        f"M1 planned 20 documents; on disk {n_t} transcripts + "
        f"{int((df.kind=='results_pack').sum())} packs. "
        "Fallback: eight quarters per bank — logged, proceed."
    )
    return df


def _mgmt_names(all_turns: pd.DataFrame) -> list[str]:
    names = []
    for s in all_turns.loc[all_turns["role"] == "management", "speaker"].dropna().unique():
        s = str(s).strip()
        if PERSON_NAME.match(s) and 4 <= len(s) <= 40:
            names.append(s)
    extra = [
        "C.S. Venkatakrishnan",
        "C. S. Venkatakrishnan",
        "Venkatakrishnan",
        "Anna Cross",
        "Coenraad Vrolijk",
        "Georges Elhedery",
        "Pam Kaur",
        "Noel Quinn",
        "Georges Elhedery",
    ]
    names.extend(extra)
    return sorted(set(names), key=len, reverse=True)


def _split_bleed(text: str, names: list[str]) -> tuple[str, str]:
    """Barclays PDFs often leave the exec name + reply inside the analyst turn."""
    if not names or not text:
        return text, ""
    pat = re.compile(r"(?m)^(?:\s*)(" + "|".join(re.escape(n) for n in names) + r")\s*$")
    m = pat.search(text)
    if not m:
        return text, ""
    return text[: m.start()].strip(), text[m.start() :].strip()


def pair_qa(all_turns: pd.DataFrame) -> pd.DataFrame:
    """Consecutive analyst turn + following management turn(s) = one pair."""
    df = all_turns.copy().reset_index(drop=True)
    df["section"] = "qa"
    names = _mgmt_names(df)
    rows = []
    for source, g in df.groupby("source", sort=False):
        g = g.reset_index(drop=True)
        i = 0
        pid = 0
        while i < len(g):
            row = g.iloc[i]
            if row["role"] != "analyst":
                i += 1
                continue
            answers = []
            j = i + 1
            while j < len(g) and g.iloc[j]["role"] == "management":
                answers.append(str(g.iloc[j]["text"]))
                j += 1
            pid += 1
            qtext = str(row["text"])
            pair_mode = "consecutive"
            if not answers:
                qtext, bleed = _split_bleed(qtext, names)
                if bleed:
                    answers = [bleed]
                    pair_mode = "bleed_split"
            atext = " ".join(answers)
            rows.append(
                {
                    "pair_id": f"{row['bank']}_{row['quarter']}_{pid:03d}",
                    "bank": row["bank"],
                    "quarter": row["quarter"],
                    "source": row["source"],
                    "section": "qa",
                    "date": "",
                    "analyst": row.get("speaker"),
                    "analyst_firm": row.get("firm"),
                    "speaker_type": row.get("role") or "analyst",
                    "question_text": qtext,
                    "answer_text": atext,
                    "n_answer_turns": len(answers),
                    "pair_mode": pair_mode,
                    "seed_topic_q": seed_label(qtext),
                    "seed_topic_a": seed_label(atext) if atext else "untagged",
                    "prudential8_q": prudential8_label(qtext),
                    "prudential8_a": prudential8_label(atext) if atext else "untagged",
                }
            )
            i = j if j > i + 1 else i + 1
    return pd.DataFrame(rows)


def extract_numeric_claims(qa: pd.DataFrame, max_per_pair: int = 6) -> pd.DataFrame:
    rows = []
    for _, r in qa.iterrows():
        blob = f"{r['question_text']}\n{r['answer_text']}"
        n = 0
        for m in CLAIM_RE.finditer(blob):
            if n >= max_per_pair:
                break
            val = m.group("value")
            if val is None:
                continue
            raw = re.sub(r"[£$,\s]", "", val)
            try:
                number = float(raw)
            except ValueError:
                continue
            unit = (m.group("unit") or "").strip()
            if 1900 <= number <= 2035 and not unit:
                continue
            window = blob[max(0, m.start() - 48) : m.end() + 48]
            if not unit and not METRIC_NEAR.search(window):
                continue
            hor = HORIZON_RE.search(window)
            rows.append(
                {
                    "pair_id": r["pair_id"],
                    "bank": r["bank"],
                    "quarter": r["quarter"],
                    "value_raw": val.strip(),
                    "unit": unit,
                    "time_horizon": hor.group(1) if hor else "",
                    "span": m.group(0).strip(),
                    "context": re.sub(r"\s+", " ", window).strip(),
                    "source": r["source"],
                }
            )
            n += 1
    return pd.DataFrame(rows)


def audit_sample(claims: pd.DataFrame, n: int = 50, seed: int = 9) -> pd.DataFrame:
    if claims is None or claims.empty:
        return pd.DataFrame()
    k = min(n, len(claims))
    out = claims.sample(k, random_state=seed).copy()
    out["human_ok"] = ""
    out["human_note"] = ""
    return out.reset_index(drop=True)


# M6, seed_label and prudential8_label share whole-word matching (keywords.py).
_M6_BUCKET = {
    "total_income": "profitability",
    "operating_costs": "efficiency",
    "credit_impairment": "asset_quality",
    "cet1_ratio": "capital",
}


def _m6_metrics(text: str) -> list[str]:
    return [m for m, keys in METRIC_KW.items() if any_keyword(text, keys)]


def metric_coverage_for(question, answer, metric: str) -> float | None:
    """M6 coverage for one metric.

    None when that metric was not asked. 0 when it was asked and the answer
    does not use its words. 1 when the answer covers it.
    """
    keys = METRIC_KW[metric]
    if _blank(question) or not any_keyword(question, keys):
        return None
    if _blank(answer):
        return 0.0
    return float(any_keyword(str(answer), keys))


def _m6_bucket(text: str) -> str:
    """Four-line bucket for substitution: untagged, one bucket, or mixed."""
    hits = _m6_metrics(text)
    if not hits:
        return "untagged"
    return _M6_BUCKET[hits[0]] if len(hits) == 1 else "mixed"


def _blank(text) -> bool:
    if pd.isna(text):
        return True
    return str(text).strip().lower() in ("", "nan", "none")


def behavioural_signals(qa: pd.DataFrame) -> pd.DataFrame:
    """M6 per pair. An empty answer is missing (None), not an indirect answer."""
    out = qa.copy()
    dirs, v2s, covs, subs, measurable = [], [], [], [], []
    for _, r in out.iterrows():
        qt, at = r["question_text"], r["answer_text"]
        if _blank(qt) or _blank(at):
            dirs.append(None)
            v2s.append(None)
            covs.append(None)
            subs.append(None)
            measurable.append(False)
            continue
        qt, at = str(qt), str(at)
        tq, ta = _tokens(qt), _tokens(at)
        dirs.append(round(len(tq & ta) / len(tq), 3) if tq and ta else None)
        v2s.append(directness_v2(qt, at))
        req = _m6_metrics(qt)
        if not req:
            covs.append(None)
        else:
            covs.append(float(any(keyword_in_text(at, k) for m in req for k in METRIC_KW[m])))
        qlab, alab = _m6_bucket(qt), _m6_bucket(at)
        # Unchanged definition: only single-bucket Q and A can substitute; the
        # rest score 0.0. substitution_measurable says which rows could.
        can = qlab not in ("untagged", "mixed") and alab not in ("untagged", "mixed")
        measurable.append(can)
        subs.append(float(can and alab != qlab))
    out["directness"] = dirs
    out["directness_v2"] = v2s
    out["metric_coverage"] = covs
    out["topic_substitution"] = subs
    out["substitution_measurable"] = measurable
    return out


def prudential_map(qa: pd.DataFrame) -> pd.DataFrame:
    """Coder1 = keyword 8-way on the question; coder2 on the answer / seed.

    Human dual-code (Aidan + second) still required; this flags machine
    disagreement for review.
    """
    df = qa[["pair_id", "bank", "quarter", "prudential8_q", "prudential8_a", "seed_topic_q"]].copy()
    df["coder1_category"] = df["prudential8_q"]
    mapped_seed = df["seed_topic_q"].map(SEED_TO_8)
    df["coder2_category"] = df["prudential8_a"].where(df["prudential8_a"] != "untagged", mapped_seed)
    df["disagreement"] = df["coder1_category"] != df["coder2_category"]
    return df


def machine_vs_machine(qa: pd.DataFrame) -> dict:
    """coder1 vs coder2 on these pairs, using the current whole-word labels."""
    rows = qa.drop_duplicates("pair_id").copy()
    c1 = rows["question_text"].map(prudential8_label)
    a8 = rows["answer_text"].map(prudential8_label)
    seed = rows["question_text"].map(seed_label).map(SEED_TO_8)
    c2 = a8.where(a8 != "untagged", seed)
    n = int(len(rows))
    n_agree = int((c1.to_numpy() == c2.fillna("untagged").to_numpy()).sum()) if n else 0
    return {"n": n, "n_agree": n_agree, "pct": (n_agree / n) if n else None}


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    p = k / n
    den = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / den
    margin = z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5) / den
    return max(0.0, centre - margin), min(1.0, centre + margin)


def substitution_headline(qa: pd.DataFrame) -> str:
    """Measurable pairs only. The all-pair mean counts non-measurable rows as 0."""
    if qa is None or qa.empty or "substitution_measurable" not in qa.columns:
        return "n/a"
    flag = qa["substitution_measurable"].fillna(False).astype(bool)
    n = int(flag.sum())
    if n == 0:
        return "no measurable pairs"
    k = int(pd.to_numeric(qa.loc[flag, "topic_substitution"], errors="coerce").fillna(0).sum())
    lo, hi = wilson_interval(k, n)
    return f"{k / n:.0%} of {n} measurable pairs (~{lo:.0%}–{hi:.0%})"


def cohort_of(bank) -> str:
    """UK is HSBC and Barclays. Credit Suisse is the separate book."""
    return "UK" if str(bank).lower() in {"hsbc", "barclays"} else "CS"


def state_summary(qa: pd.DataFrame, reported: pd.DataFrame | None) -> pd.DataFrame:
    counts = {}
    if "metric_coverage" in qa.columns:
        counts["n_coverage_asked"] = ("metric_coverage", "count")
    if "substitution_measurable" in qa.columns:
        counts["n_substitution_measurable"] = ("substitution_measurable", "sum")
    agg = qa.groupby(["bank", "quarter"], as_index=False).agg(
        n_pairs=("pair_id", "size"),
        mean_directness=("directness", "mean"),
        **({"mean_directness_v2": ("directness_v2", "mean")} if "directness_v2" in qa.columns else {}),
        metric_coverage_rate=("metric_coverage", "mean"),
        substitution_rate=("topic_substitution", "mean"),
        **counts,
    )
    if reported is not None and len(reported):
        # Pack labels (q2/h1/4q) vs transcript labels (interim/annual) join on calendar period
        left = agg.copy()
        left["calendar_period"] = left["quarter"].map(calendar_period)
        right = reported.copy()
        right["calendar_period"] = right["quarter"].map(calendar_period)
        wide = right.pivot_table(
            index=["bank", "calendar_period"], columns="metric", values="direction", aggfunc="first"
        ).reset_index()
        left = left.merge(wide, on=["bank", "calendar_period"], how="left")
        agg = left.drop(columns=["calendar_period"])
    agg["n"] = agg["n_pairs"]
    agg["cohort"] = agg["bank"].map(cohort_of)
    return agg


def main(*, configure_store: bool = True) -> None:
    if configure_store:
        configure(memory=False)
    raw = ROOT / "data" / "raw" / "transcripts"
    structured = ROOT / "data" / "structured"
    manifest = build_manifest(raw, structured)
    save_df("corpus_manifest", manifest)
    print(manifest.attrs.get("m1_note", ""))
    print("manifest rows", len(manifest))
    print(
        "publication_date on transcripts",
        int(((manifest.kind == "transcript") & (manifest.publication_date != "")).sum()),
        "/",
        int((manifest.kind == "transcript").sum()),
    )
    n_other = int((manifest["event_type"] == "other").sum()) if "event_type" in manifest.columns else 0
    print("event_type=other (kept, excluded from default analyses)", n_other)
    cov = coverage_by_bank_year(manifest)
    save_df("corpus_coverage", cov)
    print("coverage by bank × year (results_call only)\n", cov.to_string(index=False))

    turns = load_df("all_turns")
    if turns is None or turns.empty:
        raise SystemExit("all_turns missing — run notebook Stage 1 first")
    qa = pair_qa(turns)
    dates = manifest.set_index("source")["publication_date"].to_dict()
    types = manifest.set_index("source")["event_type"].to_dict()
    qa["date"] = qa["source"].map(lambda s: dates.get(s, "") or "")
    qa["event_type"] = qa["source"].map(lambda s: types.get(s, event_type_from_source(s)))
    named = (qa["analyst"].fillna("").str.len() > 1).mean()
    n_empty = int((qa["answer_text"].fillna("") == "").sum())
    print(
        f"qa_pairs {len(qa)}  named_analyst {named:.0%}  "
        f"bleed_split {int((qa.pair_mode=='bleed_split').sum())}  empty_answers {n_empty}"
    )

    claims = extract_numeric_claims(qa)
    save_df("numeric_claims", claims)
    audit = audit_sample(claims)
    save_df("numeric_claims_audit", audit)
    print("numeric_claims", len(claims), "audit sample", len(audit))

    beh = behavioural_signals(qa)
    save_df("qa_pairs", beh)
    save_df("behavioural_signals", beh)
    print(beh[["directness", "directness_v2", "topic_substitution"]].mean(numeric_only=True).to_string())
    print("substitution", substitution_headline(beh))

    pmap = prudential_map(beh)
    save_df("prudential_map", pmap)
    print("prudential disagreements", int(pmap["disagreement"].sum()), "/", len(pmap))

    reported = load_df("reported_metrics") if has_df("reported_metrics") else None
    if reported is None or reported.empty:
        print(
            "reported_metrics not in sqlite yet — state_summary without Excel "
            "directions. Stage 6.3 parses the packs."
        )
        reported = None
    ss = state_summary(beh, reported)
    save_df("state_summary", ss)
    print("state_summary\n", ss.to_string(index=False))


if __name__ == "__main__":
    main()

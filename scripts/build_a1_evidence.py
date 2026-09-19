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
from periods import calendar_period  # noqa: E402
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
    "cet1_ratio": ["cet1", "capital ratio", "capital", "rwa", "tier 1"],
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
        if any(k in t for k in keys)
    ]
    if not hits:
        return "untagged"
    return hits[0] if len(hits) == 1 else "mixed"


def prudential8_label(text: str) -> str:
    t = str(text).lower()
    scored = []
    for cat, keys in PRUDENTIAL_8.items():
        n = sum(1 for k in keys if k in t)
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


def behavioural_signals(qa: pd.DataFrame) -> pd.DataFrame:
    out = qa.copy()
    dirs, covs, subs = [], [], []
    for _, r in out.iterrows():
        qt, at = r["question_text"], r["answer_text"]
        tq, ta = _tokens(qt), _tokens(at)
        if not tq or not ta:
            dirs.append(0.0)
        else:
            dirs.append(round(len(tq & ta) / max(len(tq), 1), 3))
        req = [m for m, keys in METRIC_KW.items() if any(k in qt.lower() for k in keys)]
        if not req:
            covs.append(None)
        else:
            covs.append(float(any(any(k in at.lower() for k in METRIC_KW[m]) for m in req)))
        qlab, alab = r["seed_topic_q"], r["seed_topic_a"]
        if qlab in ("untagged", "mixed") or not at:
            subs.append(0.0)
        else:
            subs.append(float(alab not in (qlab, "mixed", "untagged") and alab != qlab))
    out["directness"] = dirs
    out["metric_coverage"] = covs
    out["topic_substitution"] = subs
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


def state_summary(qa: pd.DataFrame, reported: pd.DataFrame | None) -> pd.DataFrame:
    agg = qa.groupby(["bank", "quarter"], as_index=False).agg(
        n_pairs=("pair_id", "size"),
        mean_directness=("directness", "mean"),
        metric_coverage_rate=("metric_coverage", "mean"),
        substitution_rate=("topic_substitution", "mean"),
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

    turns = load_df("all_turns")
    if turns is None or turns.empty:
        raise SystemExit("all_turns missing — run notebook Stage 1 first")
    qa = pair_qa(turns)
    dates = manifest.set_index("source")["publication_date"].to_dict()
    qa["date"] = qa["source"].map(lambda s: dates.get(s, "") or "")
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
    print(beh[["directness", "topic_substitution"]].mean(numeric_only=True).to_string())

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

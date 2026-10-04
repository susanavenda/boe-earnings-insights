#!/usr/bin/env python3
"""Download extra Credit Suisse years (2020–2022 calls + SEC 6-K 4-KPI packs).

CS IR is gone. Transcripts come from public call archives already fetched locally
(Motley Fool ``Name -- Role``, Roic name-only). KPIs come from SEC 6-K Exhibit 99.1.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_credit_suisse_inputs import clean_archive_transcript, write_text_pdf  # noqa: E402

OUT_T = ROOT / "data" / "raw" / "transcripts" / "credit_suisse"
OUT_S = ROOT / "data" / "structured" / "credit_suisse"
TOOLS = Path(
    "/Users/susanavenda/.cursor/projects/Users-susanavenda-Downloads-Boe-Earnings-Insights-Workspace"
    "/agent-tools"
)

LOCAL_TRANSCRIPTS = {
    "2020-q2": "60fc3379-06dd-4946-82ca-4e1c233b15d1.txt",
    "2020-q3": "39c82e36-e614-4f04-9dca-55af5f422c20.txt",
    "2020-q4": "8ca92e4f-efc2-4de9-86fa-c0ff701da4e4.txt",
    "2021-q1": "d77ed7f8-b04c-404d-a40b-8d035a1306bf.txt",
    "2021-q2": "8fbd03dc-cb47-4a84-b699-90c4cc04096a.txt",
    "2021-q3": "5c540283-cc21-4056-ac63-8df9e61b0fdc.txt",
    "2021-q4": "69a10897-39a7-4180-bf16-189f9bee413f.txt",
    "2022-q1": "6e2625d1-5455-4971-95a8-ff926ba44957.txt",
    "2022-q2": "7f98f15f-50e1-4081-8943-cb0bfbc28113.txt",
    "2022-q3": "d5ad624f-72b3-45e0-8e72-3c5301820b68.txt",
}
LOCAL_FALLBACK = {
    "2021-q4": "d4794d34-cd80-41f3-99c5-f84c827a29c6.txt",
}

SEC_UA = "BoeEarningsInsights CambridgeDS susanavenda89@gmail.com"
CIK = "0001159510"

MGMT = {
    "kinner lakhani": "Head of Investor Relations",
    "thomas gottstein": "Chief Executive Officer",
    "david mathers": "Chief Financial Officer",
    "ulrich korner": "Chief Executive Officer",
    "ulrich körner": "Chief Executive Officer",
    "dixit joshi": "Chief Financial Officer",
    "axel lehmann": "Chairman",
    "tidjane thiam": "Chief Executive Officer",
    "romeo cerutti": "General Counsel",
    "antonio horta-osorio": "Chairman",
    "antónio horta-osório": "Chairman",
    "cindy leggett-flynn": "Group Head Corporate Communications",
}

SKIP_NAMES = {
    "credit suisse",
    "motley fool",
    "prepared remarks",
    "call participants",
    "questions answers",
    "operator instructions",
}

NAME_LINE = re.compile(
    r"^([A-Z][a-zA-Z\.\-]+(?:\s+[A-Z][a-zA-Z\.\-']+){0,4})$"
)


def _num(tok: str):
    t = tok.strip().replace(",", "").replace("%", "")
    if t in {"", "–", "-", "—", "n/a", "N/A"}:
        return None
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def normalize_speakers(raw: str, quarter: str) -> str:
    dash_n = len(re.findall(r" -- ", raw))
    label = f"Credit Suisse {quarter.upper()} results — analyst and investor call"
    if dash_n >= 8:
        text = clean_archive_transcript(raw)
        text = re.sub(
            r"Fourth Quarter and Full Year 2022 Results\nAnalyst and Investor Conference Call\nThursday 9 February 2023",
            label,
            text,
            count=1,
        )
        return text

    qa = False
    out = []
    for ln in raw.splitlines():
        s = re.sub(r"^\d{1,2}:\d{2}\s+", "", ln.strip())
        if not s:
            out.append("")
            continue
        if re.search(r"next question|questions?\s*&\s*answers|questions and answers", s, re.I):
            qa = True
        m = NAME_LINE.match(s)
        if m and s.lower() not in SKIP_NAMES and "http" not in s.lower() and len(s) <= 48:
            name = m.group(1)
            key = name.lower()
            if key == "operator":
                out.append("Operator")
                continue
            if key in MGMT:
                out.append(f"{name} -- {MGMT[key]}")
            elif qa:
                out.append(f"{name} -- Analyst")
            else:
                out.append(f"{name} -- Management")
            continue
        out.append(s)
    blob = "\n".join(out)
    if "Operator" not in blob.splitlines()[:40]:
        blob = "Operator\n\n" + blob
    text = clean_archive_transcript(blob)
    text = re.sub(
        r"Fourth Quarter and Full Year 2022 Results\nAnalyst and Investor Conference Call\nThursday 9 February 2023",
        label,
        text,
        count=1,
    )
    return text


def resolve_local(quarter: str) -> Path | None:
    name = LOCAL_TRANSCRIPTS.get(quarter)
    if name and (TOOLS / name).exists():
        return TOOLS / name
    alt = LOCAL_FALLBACK.get(quarter)
    if alt and (TOOLS / alt).exists():
        return TOOLS / alt
    year, qtok = quarter.split("-")
    hits = []
    for p in TOOLS.glob("*.txt"):
        head = p.read_text(encoding="utf-8", errors="replace")[:900].lower()
        if "credit suisse" in head and year in head and qtok in head and "earnings" in head:
            hits.append((p.stat().st_size, p))
    if hits:
        hits.sort(reverse=True)
        return hits[0][1]
    return None


def _sec_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": SEC_UA, "Accept": "application/json,text/html"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def parse_key_metrics(text: str) -> dict | None:
    nr = pcl = opex = cet1 = None
    for line in text.splitlines():
        if "| Net revenues |" in line and nr is None:
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 3:
                nr = (_num(parts[1]), _num(parts[2]))
        elif "| Provision for credit losses |" in line and pcl is None:
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 3:
                pcl = (_num(parts[1]), _num(parts[2]))
        elif "| Total operating expenses |" in line and opex is None:
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 3:
                opex = (_num(parts[1]), _num(parts[2]))
        elif "| CET1 ratio |" in line and cet1 is None:
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 3:
                cet1 = (_num(parts[1]), _num(parts[2]))
        if nr and pcl and opex and cet1:
            break
    if not (nr and pcl and opex and cet1):
        return None
    if None in nr + pcl + opex + cet1:
        return None
    return {
        "Net revenues": nr,
        "Provision for credit losses": pcl,
        "Total operating expenses": opex,
        "CET1 ratio": cet1,
    }


def write_pack(path: Path, parsed: dict, source: str, current_label: str, prior_label: str) -> None:
    df = pd.DataFrame(
        {
            "metric": list(parsed),
            "current": [parsed[k][0] for k in parsed],
            "prior": [parsed[k][1] for k in parsed],
            "unit": ["CHF million", "CHF million", "CHF million", "percent"],
            "current_label": [current_label] * 4,
            "prior_label": [prior_label] * 4,
            "source": [source] * 4,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, sheet_name="Group key metrics", index=False)


def _quarter_from_sec(ex: str, report_date: str, filing_date: str) -> str | None:
    el = ex.lower()
    m = re.search(r"([1-4])q(\d{2})", el) or re.search(r"q([1-4])(\d{2})", el)
    if m:
        q, yy = m.group(1), m.group(2)
        return f"20{yy}-q{q}"
    if report_date.endswith("-12-31"):
        return f"{report_date[:4]}-q4"
    if report_date.endswith("-03-31") or report_date.endswith("-03-30"):
        return f"{report_date[:4]}-q1"
    if report_date.endswith("-06-30"):
        return f"{report_date[:4]}-q2"
    if report_date.endswith("-09-30"):
        return f"{report_date[:4]}-q3"
    month = int(filing_date[5:7])
    year = int(filing_date[:4])
    if month <= 3:
        return f"{year - 1}-q4"
    if month <= 5:
        return f"{year}-q1"
    if month <= 8:
        return f"{year}-q2"
    if month <= 11:
        return f"{year}-q3"
    return f"{year}-q4"


def fetch_sec_packs() -> list[str]:
    written = []
    raw = _sec_get(f"https://data.sec.gov/submissions/CIK{CIK}.json")
    sub = json.loads(raw.decode("utf-8"))
    rec = sub["filings"]["recent"]
    n = len(rec["accessionNumber"])
    seen_q = set()
    for i in range(n):
        if rec["form"][i] != "6-K":
            continue
        fdate = rec["filingDate"][i]
        if fdate < "2020-01-01" or fdate > "2023-05-15":
            continue
        acc = rec["accessionNumber"][i]
        acc_nodash = acc.replace("-", "")
        primary = rec["primaryDocument"][i]
        rdate = rec["reportDate"][i]
        index_url = f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}/{acc_nodash}/index.json"
        try:
            idx = json.loads(_sec_get(index_url).decode("utf-8"))
        except Exception as exc:
            print(f"WARN index {acc}: {exc}")
            continue
        items = idx.get("directory", {}).get("item", [])
        ex = None
        for it in items:
            name = str(it.get("name", "")).lower()
            if name.endswith((".htm", ".html", ".txt")) and (
                "ex99_1" in name or "q1er" in name or "q2er" in name or "q3er" in name or "q4er" in name
            ):
                ex = it["name"]
                break
        if not ex:
            ex = primary
        url = f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}/{acc_nodash}/{ex}"
        try:
            body = _sec_get(url).decode("utf-8", "replace")
        except Exception as exc:
            print(f"WARN fetch {url}: {exc}")
            continue
        parsed = parse_key_metrics(body)
        if not parsed:
            plain = re.sub(r"<[^>]+>", " | ", body)
            parsed = parse_key_metrics(plain)
        if not parsed:
            continue
        q = _quarter_from_sec(ex, rdate, fdate)
        if not q or q in seen_q:
            continue
        path = OUT_S / f"{q}-financial-tables.xlsx"
        if path.exists() and q == "2022-q4":
            seen_q.add(q)
            written.append(f"{q} (kept)")
            continue
        write_pack(path, parsed, f"SEC 6-K {fdate} {ex}", q.upper().replace("-", ""), "prior")
        seen_q.add(q)
        written.append(q)
        print(f"pack {q} <- {ex} ({fdate}) NR={parsed['Net revenues'][0]} CET1={parsed['CET1 ratio'][0]}")
    return written


def write_transcripts() -> list[str]:
    OUT_T.mkdir(parents=True, exist_ok=True)
    done = []
    for quarter in LOCAL_TRANSCRIPTS:
        src = resolve_local(quarter)
        if src is None:
            print(f"SKIP transcript {quarter}: no local dump")
            continue
        raw = src.read_text(encoding="utf-8", errors="replace")
        cleaned = normalize_speakers(raw, quarter)
        pdf = OUT_T / f"{quarter}-results-qa-transcript.pdf"
        txt = OUT_T / f"{quarter}-results-qa-transcript.txt"
        txt.write_text(cleaned, encoding="utf-8")
        write_text_pdf(pdf, cleaned)
        print(f"transcript {quarter} <- {src.name} dashes={cleaned.count(' -- ')} bytes={pdf.stat().st_size}")
        done.append(quarter)
    return done


def main() -> None:
    t = write_transcripts()
    try:
        packs = fetch_sec_packs()
    except Exception as exc:
        print(f"SEC packs failed: {exc}")
        packs = []
    src = OUT_T / "SOURCE.txt"
    prev = src.read_text(encoding="utf-8") if src.exists() else ""
    extra = (
        "\nExtra years 2020–2022: public call archives (Motley Fool / Roic) converted to "
        "Name -- Role PDFs. Four locked KPIs from SEC 6-K Exhibit 99.1 where the table parsed.\n"
        f"Transcripts: {', '.join(t)}\nPacks: {', '.join(packs)}\n"
    )
    if extra not in prev:
        src.write_text(prev.rstrip() + "\n" + extra, encoding="utf-8")
    print(f"done transcripts={len(t)} packs={len(packs)}")


if __name__ == "__main__":
    main()

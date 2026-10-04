#!/usr/bin/env python3
"""Build Credit Suisse Q4 2022 local inputs (transcript + 4-KPI pack).

Transcript: public 9 Feb 2023 analyst-and-investor call, speaker labels only
in Motley Fool / Thomson ``Name -- Role`` form (CS IR site is gone).
KPIs: SEC Form 6-K Exhibit 99.1, 9 Feb 2023 (CHF million / %).
"""
from __future__ import annotations

import re
from pathlib import Path
from textwrap import wrap

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_T = ROOT / "data" / "raw" / "transcripts" / "credit_suisse"
OUT_S = ROOT / "data" / "structured" / "credit_suisse"
FOOL = Path(
    "/Users/susanavenda/.cursor/projects/Users-susanavenda-Downloads-Boe-Earnings-Insights-Workspace"
    "/agent-tools/d305199c-1dec-4b58-8093-a44ddf889d3e.txt"
)


def clean_archive_transcript(raw: str) -> str:
    lines = raw.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.strip() == "Operator"), 0)
    end = next(
        (
            i
            for i, ln in enumerate(lines)
            if ln.strip().startswith("Duration:") or ln.strip().startswith("## Call participants")
        ),
        len(lines),
    )
    keep = []
    skip_heads = {
        "## contents:",
        "## prepared remarks:",
        "## questions & answers:",
        "operator",
    }
    for ln in lines[start:end]:
        s = ln.strip()
        if not s:
            keep.append("")
            continue
        if s.lower() in skip_heads and s.startswith("##"):
            continue
        keep.append(s)
    text = "\n".join(keep)
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    header = (
        "Credit Suisse Group AG\n"
        "Fourth Quarter and Full Year 2022 Results\n"
        "Analyst and Investor Conference Call\n"
        "Thursday 9 February 2023\n\n"
        "Source note: CS IR site is gone. Speaker-labelled Q&A from public call archives "
        "(Motley Fool / Thomson convention: Name -- Role). KPIs are SEC 6-K Exhibit 99.1, "
        "9 February 2023 — not this transcript.\n\n"
    )
    return header + text


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_text_pdf(path: Path, text: str, *, width: int = 96, lines_per: int = 58) -> None:
    wrapped: list[str] = []
    for para in text.split("\n"):
        if not para:
            wrapped.append("")
        elif " -- " in para:
            # Speaker labels must stay on one line or the CS regex misses them.
            wrapped.append(para[:160])
        else:
            wrapped.extend(wrap(para, width) or [para])
    pages = [wrapped[i : i + lines_per] for i in range(0, len(wrapped), lines_per)] or [[]]
    content_ids = []
    page_ids = []
    objs: dict[int, bytes] = {}
    next_id = 3  # 1 catalog, 2 pages

    for page in pages:
        stream_lines = ["BT", "/F1 10 Tf", "14 TL", "36 780 Td"]
        for i, ln in enumerate(page):
            if i:
                stream_lines.append("T*")
            stream_lines.append(f"({_esc(ln)}) Tj")
        stream_lines.append("ET")
        stream = ("\n".join(stream_lines) + "\n").encode("latin-1", "replace")
        cid = next_id
        next_id += 1
        pid = next_id
        next_id += 1
        content_ids.append(cid)
        page_ids.append(pid)
        objs[cid] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"endstream"
        )

    kids = " ".join(f"{i} 0 R" for i in page_ids)
    objs[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()
    objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    font_id = next_id
    next_id += 1
    objs[font_id] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"
    for pid, cid in zip(page_ids, content_ids):
        objs[pid] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {cid} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        ).encode()

    buf = bytearray()
    buf.extend(b"%PDF-1.4\n")
    offsets = {0: 0}
    max_id = max(objs)
    for i in range(1, max_id + 1):
        offsets[i] = len(buf)
        body = objs[i]
        buf.extend(f"{i} 0 obj\n".encode())
        buf.extend(body)
        buf.extend(b"\nendobj\n")
    xref = len(buf)
    buf.extend(f"xref\n0 {max_id + 1}\n".encode())
    buf.extend(b"0000000000 65535 f \n")
    for i in range(1, max_id + 1):
        buf.extend(f"{offsets[i]:010d} 00000 n \n".encode())
    buf.extend(
        f"trailer << /Size {max_id + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    path.write_bytes(buf)


def write_kpi_xlsx(path: Path) -> None:
    """4Q22 vs 3Q22 from SEC 6-K Exhibit 99.1 (CHF million except CET1 %)."""
    df = pd.DataFrame(
        {
            "metric": [
                "Net revenues",
                "Provision for credit losses",
                "Total operating expenses",
                "CET1 ratio",
            ],
            "current": [3060.0, 41.0, 4334.0, 14.1],
            "prior": [3804.0, 21.0, 4125.0, 12.6],
            "unit": ["CHF million", "CHF million", "CHF million", "percent"],
            "current_label": ["4Q22"] * 4,
            "prior_label": ["3Q22"] * 4,
            "source": ["SEC 6-K 9 Feb 2023 Exhibit 99.1"] * 4,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, sheet_name="Group key metrics", index=False)


def main() -> None:
    OUT_T.mkdir(parents=True, exist_ok=True)
    raw = FOOL.read_text(encoding="utf-8", errors="replace")
    cleaned = clean_archive_transcript(raw)
    txt = OUT_T / "2022-q4-results-qa-transcript.txt"
    pdf = OUT_T / "2022-q4-results-qa-transcript.pdf"
    src = OUT_T / "SOURCE.txt"
    txt.write_text(cleaned, encoding="utf-8")
    write_text_pdf(pdf, cleaned)
    src.write_text(
        "Credit Suisse Group AG — 4Q22 / FY22 analyst and investor call, 9 February 2023.\n"
        "CS IR site is gone. UBS archive and SEC 6-K file the earnings release and slides, not a Q&A PDF.\n"
        "This file is a speaker-labelled reconstruction from public call archives "
        "(Name -- Role / Name -- Firm -- Analyst).\n"
        "Structured KPIs: SEC Form 6-K, 9 February 2023, Exhibit 99.1.\n",
        encoding="utf-8",
    )
    xlsx = OUT_S / "2022-q4-financial-tables.xlsx"
    write_kpi_xlsx(xlsx)
    print(f"wrote {txt} ({txt.stat().st_size} bytes)")
    print(f"wrote {pdf} ({pdf.stat().st_size} bytes)")
    print(f"wrote {xlsx}")


if __name__ == "__main__":
    main()

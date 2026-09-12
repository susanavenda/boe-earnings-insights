#!/usr/bin/env python3
"""Generate one-page PRA supervisor notes from supervisory episode JSON."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from store import load_df, load_json, save_text  # noqa: E402

PROC = ROOT / "data" / "processed"
OUT = ROOT / "docs" / "assignment2" / "pra_notes"


def render_note(ep: dict, briefs: pd.DataFrame, protocol: pd.DataFrame) -> str:
    eid = ep.get("id", ep["bank"])
    eb = briefs[briefs["episode_id"] == eid] if "episode_id" in briefs.columns else briefs
    if eb.empty and "bank" in briefs.columns:
        eb = briefs[(briefs["bank"] == ep["bank"]) & (briefs["quarter"] == ep["quarter"])]

    fired = set(ep.get("rules_fired", []))
    proto_rows = []
    for _, r in protocol.iterrows():
        mark = "FIRED" if r["rule_id"] in fired else "—"
        sev = r["severity"]
        if sev is None or (isinstance(sev, float) and pd.isna(sev)) or str(sev).lower() == "nan":
            sev = "null"
        proto_rows.append(f"| {r['rule_id']} | {sev} | {mark} | {r['condition']} |")

    brief_rows = []
    for _, r in eb.iterrows():
        faith = r.get("faithful")
        if faith is True or faith is False:
            agree = "yes" if faith else "no"
        else:
            agree = "n/a"  # missing Q&A tone — not agreement
        narr = r.get("narrative_direction")
        narr_s = "n/a" if narr is None or (isinstance(narr, float) and pd.isna(narr)) else str(narr)
        brief_rows.append(
            f"| {r['metric']} | {r.get('reported_direction','')} | {narr_s} | {agree} |"
        )

    gap = ep.get("peer_gap_hsbc_minus_barclays")
    gap_s = f"{gap:.3f}" if gap is not None else "n/a"
    ph = ep.get("peer_hsbc_net")
    pb = ep.get("peer_barclays_net")
    peer_detail = "n/a"
    if ph is not None and pb is not None:
        peer_detail = (
            f"HSBC {ph:.3f} (n={ep.get('peer_hsbc_n')}, non-neut {ep.get('peer_hsbc_non_neutral_share', 0):.0%}) · "
            f"Barclays {pb:.3f} (n={ep.get('peer_barclays_n')}, non-neut {ep.get('peer_barclays_non_neutral_share', 0):.0%})"
        )
    caveat = ep.get("peer_caveat") or ""

    return f"""# PRA supervisory note — {ep.get('label', ep['bank'].upper() + ' ' + ep['quarter'])}

**Date:** {date.today().isoformat()} · **Group 9** · Bank of England employer project  
**Window:** {ep.get('calendar_period')} (narrative `{ep['quarter']}` · pack `{ep.get('struct_quarter')}`)

---

## Verdict

**{ep.get('verdict')}**

{ep.get('headline', '')}

| KPI | Value |
|---|---|
| Analyst turns | {ep.get('n_turns')} |
| FinBERT net | {ep.get('finbert_net', float('nan')):.3f} |
| Topic 1 turns / neg share | {ep.get('topic1_turns')} / {ep.get('topic1_neg_share', 0):.0%} |
| Peer sides (matched) | {peer_detail} |
| Peer gap (HSBC − Barclays) | {gap_s}{" · **not used for A2**" if ep.get("peer_usable_for_a2") is False and gap is not None else ""} |
| Rules fired | {', '.join(ep.get('rules_fired', []))} |

{f"**Peer caveat:** {caveat}" if caveat else ""}

---

## Struct vs Q&A (claim check)

| Metric | Reported | Q&A tone | Agree? |
|---|---|---|---|
{chr(10).join(brief_rows) if brief_rows else '| — | — | — | — |'}

*Agree? = yes/no only when Q&A tone exists; **n/a** if no metric hits in the episode (absence ≠ agreement).*

---

## Protocol

| Rule | Severity | This note | Condition |
|---|---|---|---|
{chr(10).join(proto_rows)}

---

## Suggested action

- If **alert**: desk pulls quoted turns + ECL/cost pack lines; compare peer on same calendar window (only when both sides are informative).
- If **watch**: log softness; no escalation unless A1/A2 fires next print.
- If **null**: file “no early-warning edge from Q&A this quarter.”

## Re-run cost (next quarter)

Assuming new IR PDFs/Excel packs are available: **~45–90 minutes** (drop files → notebook Stages 1–9 → spot-check 20–40 turns → regenerate this note).

---

*Generated from ``data/boe.sqlite`` (supervisory_episodes) via ``scripts/generate_pra_note.py``.*
"""


def main(episode_id: str | None = None):
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        episodes = load_json("supervisory_episodes")
    except FileNotFoundError:
        episodes = [load_json("supervisory_episode")]

    if episode_id:
        episodes = [e for e in episodes if e.get("id") == episode_id]
        if not episodes:
            raise SystemExit(f"episode id not found: {episode_id}")

    briefs = load_df("episode_metric_briefs")
    protocol = load_df("alert_null_protocol")

    notes = [render_note(ep, briefs, protocol) for ep in episodes]
    pack = "\n\n---\n\n".join(notes)
    pack_path = OUT / "pra_notes.md"
    pack_path.write_text(pack)
    save_text("pra_notes.md", pack, mime="text/markdown")
    print("wrote", pack_path)
    print("wrote pra_notes.md → data/boe.sqlite")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default=None)
    args = ap.parse_args()
    main(episode_id=args.id)

#!/usr/bin/env python3
"""Export the headline tables from data/boe.sqlite to data/exports/ as CSV.

boe.sqlite is gitignored and rebuilt on every run, so the submitted figures
need a tracked copy. This writes one CSV per table in TABLES plus MANIFEST.md
(run ID, commit, row counts, headline figures), so each CSV can be traced to
the notebook run that produced it.

CI runs it after the notebook and uploads data/exports/ with executed.ipynb.
Commit the CSVs once, from the final green run's artifact:

    python scripts/export_tables.py            # local, after a full notebook run
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from store import configure, has_df, load_df  # noqa: E402

EXPORTS = ROOT / "data" / "exports"

TABLES: dict[str, str] = {
    "struct_vs_unstruct": "Stage 6.4 reported direction vs narrative direction per bank x quarter x metric (UK/CS agreement)",
    "reported_metrics": "Stage 6.3 KPIs parsed from the Excel data packs (value, prior, direction)",
    "state_summary": "Stage 1.5 bank x quarter behaviour: directness, coverage, substitution",
    "behavioural_signals": "Stage 1.5 per-pair signals (question/answer text dropped)",
    "prudential_map": "Stage 3.6 eight-way PRA categories, coder1 vs coder2",
    "label_agreement": "FinBERT vs hand-labelled gold (accuracy, macro-F1)",
    "sentiment_agreement": "Human vs machine sentiment agreement (raw, kappa, macro-F1)",
    "summary_quality": "Summary support and review rates per bank x metric",
    "peer_gap": "HSBC vs Barclays sentiment gap per calendar period",
    "peer_matched": "Peer-matched sentiment per bank x quarter",
    "cs_quarter_trend": "Credit Suisse out-of-sample FinBERT trend",
    "topic_coherence": "Topic model coherence (c_v)",
    "protocol": "Stage 8 supervisory protocol rules (M1-M6)",
    "pra_supervisor_log": "Stage 8 supervisory episode log (synthetic supervisor actions)",
}

# Transcript text stays in the internal DB; the exports carry figures, not transcripts.
DROP_COLS = {"question_text", "answer_text"}


def _commit() -> str:
    # The checked-out commit, not GITHUB_SHA: on PR runs that is a merge preview the workflow doesn't build.
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return os.environ.get("GITHUB_SHA", "unknown")


def _run() -> tuple[str, str]:
    run_id = os.environ.get("GITHUB_RUN_ID")
    if not run_id:
        return "local", ""
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    return run_id, f"{server}/{repo}/actions/runs/{run_id}" if repo else ""


def headline_figures(frames: dict[str, pd.DataFrame]) -> list[str]:
    lines = []
    sv = frames.get("struct_vs_unstruct")
    if sv is not None and {"agrees", "cohort"} <= set(sv.columns):
        for cohort in ("UK", "CS"):
            sub = sv[sv["cohort"] == cohort]
            if len(sub):
                k = int(sub["agrees"].astype(bool).sum())
                lines.append(f"Stage 6.4 agreement {cohort}: {k} of {len(sub)} ({k / len(sub):.1%})")
    beh = frames.get("behavioural_signals_full")
    if beh is not None:
        import build_a1_evidence as a1

        lines.append(f"Topic substitution: {a1.substitution_headline(beh)}")
        if hasattr(a1, "directness_length_corr"):
            lines.append(f"Directness v1 vs answer length: r = {a1.directness_length_corr(beh)}")
    return lines


def export(out_dir: Path = EXPORTS) -> dict[str, int]:
    missing = [t for t in TABLES if not has_df(t)]
    if missing:
        raise SystemExit(f"not in boe.sqlite (run the notebook first): {', '.join(missing)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.csv"):
        old.unlink()

    frames, counts = {}, {}
    for name in TABLES:
        df = load_df(name)
        if name == "behavioural_signals":
            frames["behavioural_signals_full"] = df
        df = df.drop(columns=[c for c in df.columns if c in DROP_COLS])
        df.to_csv(out_dir / f"{name}.csv", index=False)
        frames[name], counts[name] = df, len(df)

    run_id, run_url = _run()
    lines = [
        "# Submission tables",
        "",
        "Exported from `data/boe.sqlite` by `scripts/export_tables.py` after a full notebook run.",
        "Do not edit by hand; re-export from the cited run instead.",
        "",
        f"- Run: {f'[{run_id}]({run_url})' if run_url else run_id}",
        f"- Commit: `{_commit()}`",
        f"- Exported: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Headline figures",
        "",
        *[f"- {line}" for line in headline_figures(frames)],
        "",
        "## Tables",
        "",
        "| File | Rows | Contents |",
        "|---|---:|---|",
        *[f"| `{n}.csv` | {counts[n]} | {d} |" for n, d in TABLES.items()],
        "",
    ]
    (out_dir / "MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=None, help="sqlite path (default data/boe.sqlite)")
    ap.add_argument("--out", type=Path, default=EXPORTS)
    args = ap.parse_args()
    configure(memory=False, path=args.db)
    counts = export(args.out)
    print(f"wrote {len(counts)} tables to {args.out}")


if __name__ == "__main__":
    main()

"""PRA Earnings Desk — inbox of protocol cases, then one case file.

Output surface for the factory pack in ``data/boe.sqlite``.
Alert / watch / null is protocol, not a firm rating.
"""
from __future__ import annotations

import html
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from pipeline.auto import ensure_desk
from pipeline.browse import _sort_browse_rows
from pipeline.db import list_episodes, read_asset, read_document, read_table
from pipeline.paths import DB_PATH, DEMO_DATA
from pipeline.pitch_map import (
    DECK_TRAIL,
    KPI_TO_PRA,
    LIQUIDITY_NOTE,
    PROBLEM,
    SLIDES_URL,
    coverage_line,
    inbox_bucket,
    inbox_period_label,
    is_reviewed_episode,
    rows_for_episode,
    trail_for,
)
from pipeline.recalibrate import check_recalibration
from pipeline.registry import load_registry

st.set_page_config(
    page_title="PRA Earnings Desk",
    page_icon="▣",
    layout="wide",
    initial_sidebar_state="expanded",
)

BANK_DISP = {
    "hsbc": "HSBC",
    "barclays": "Barclays",
    "credit_suisse": "Credit Suisse",
}
METRIC_ORDER = ("total_income", "operating_costs", "credit_impairment", "cet1_ratio")
METRIC_LABELS = {
    "total_income": "Total income",
    "operating_costs": "Operating costs",
    "credit_impairment": "Credit impairment / ECL",
    "cet1_ratio": "CET1",
}

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Serif:wght@600&display=swap');

html, body, [class*="css"] { font-family: "IBM Plex Sans", system-ui, sans-serif; }
.block-container { padding-top: 0.85rem; padding-bottom: 2.4rem; max-width: 1120px; }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }

.topbar {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 1rem; padding: 0.1rem 0 0.75rem;
  border-bottom: 1px solid #d9e2ec; margin-bottom: 0.85rem;
}
.topbar .brand {
  font-family: "IBM Plex Serif", Georgia, serif;
  font-size: 1.32rem; font-weight: 600; color: #0b1f33; letter-spacing: -0.02em;
  margin: 0;
}
.topbar .meta { font-size: 0.78rem; color: #627d98; text-align: right; line-height: 1.4; }

.banner {
  background: #f0f4f8; border: 1px solid #d9e2ec; color: #243b53;
  padding: 0.5rem 0.8rem; font-size: 0.84rem; margin: 0 0 0.9rem;
}
.queue {
  display: flex; gap: 1.25rem; flex-wrap: wrap;
  font-size: 0.82rem; color: #486581; margin: 0 0 0.85rem;
}
.queue b { color: #102a43; }

.verdict-pill {
  display: inline-block; padding: 0.22rem 0.65rem; border-radius: 2px;
  font-weight: 700; font-size: 0.76rem; letter-spacing: 0.07em;
}
.verdict-ALERT { background: #f3d0c7; color: #7a1f12; }
.verdict-WATCH { background: #f5e6c8; color: #6b4e12; }
.verdict-NULL  { background: #d5e5d8; color: #1e4d2b; }
.verdict-OTHER { background: #d9e2ec; color: #243b53; }
.verdict-pill.unreviewed {
  background: #eef2f6; color: #486581; font-weight: 600;
  border: 1px dashed #9fb3c8; letter-spacing: 0.04em;
}
.unreviewed-tag {
  display: inline-block; margin-left: 0.45rem; padding: 0.16rem 0.48rem;
  font-size: 0.66rem; font-weight: 700; letter-spacing: 0.07em;
  text-transform: uppercase; color: #486581;
  border: 1px solid #9fb3c8; background: #f7f9fb;
}

.headline {
  font-family: "IBM Plex Serif", Georgia, serif;
  font-size: 1.22rem; font-weight: 600; color: #0b1f33;
  line-height: 1.35; margin: 0.45rem 0 0.35rem;
}
.why { font-size: 0.95rem; color: #243b53; line-height: 1.5; margin: 0 0 0.65rem; }

.metrics {
  display: flex; flex-wrap: wrap; gap: 1rem 1.5rem;
  padding: 0.65rem 0; border-top: 1px solid #e8eef4; border-bottom: 1px solid #e8eef4;
  margin-bottom: 0.85rem;
}
.metrics .m .lbl {
  font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.06em; color: #627d98;
}
.metrics .m .val { font-size: 1.02rem; font-weight: 600; color: #102a43; margin-top: 0.06rem; }

.kpi-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.55rem; margin: 0.4rem 0 0.9rem; }
@media (max-width: 900px) { .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.kpi {
  border: 1px solid #d9e2ec; background: #fff; padding: 0.55rem 0.65rem;
}
.kpi .name { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em; color: #627d98; }
.kpi .dir { font-size: 0.95rem; font-weight: 600; color: #102a43; margin: 0.2rem 0; }
.kpi .qa { font-size: 0.78rem; color: #486581; }
.kpi .agree-yes { color: #1e4d2b; font-weight: 600; }
.kpi .agree-no { color: #7a1f12; font-weight: 600; }
.kpi .agree-na { color: #627d98; }

.caveat {
  background: #fff8eb; border-left: 3px solid #c4a35a; color: #5c4813;
  padding: 0.55rem 0.85rem; font-size: 0.86rem; margin: 0.55rem 0 0.85rem;
}
.note {
  background: #f0f4f8; border-left: 3px solid #486581; color: #243b53;
  padding: 0.5rem 0.8rem; font-size: 0.84rem; margin: 0.4rem 0 0.8rem;
}

.section-h {
  font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em;
  color: #627d98; font-weight: 600; margin: 1.15rem 0 0.45rem;
  border-bottom: 1px solid #e8eef4; padding-bottom: 0.28rem;
}

.quote-block {
  border-left: 3px solid #1a3d5c; background: #f7f9fb;
  padding: 0.6rem 0.85rem; margin: 0.35rem 0; font-size: 0.88rem; color: #243b53;
}
.quote-meta { font-size: 0.74rem; color: #627d98; margin-bottom: 0.25rem; }

.rule {
  display: grid; grid-template-columns: 3.2rem 4.4rem 4.4rem 1fr;
  gap: 0.4rem; font-size: 0.82rem; padding: 0.35rem 0;
  border-bottom: 1px solid #e8eef4;
}
.rule.head { color: #627d98; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; }
.rule.fired { background: #fff8eb; }

.admin-card {
  background: #f7f9fb; border: 1px solid #d9e2ec;
  padding: 0.5rem 0.65rem; margin: 0.3rem 0 0.5rem; font-size: 0.8rem; color: #243b53;
}
.admin-card .k { color: #627d98; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em; }
.admin-card .v { font-weight: 600; color: #102a43; margin-top: 0.08rem; }
.admin-badge { display: inline-block; padding: 0.18rem 0.5rem; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }
.admin-badge.go { background: #d5e5d8; color: #1e4d2b; }
.admin-badge.wait { background: #f5e6c8; color: #6b4e12; }

.factory {
  font-size: 0.72rem; color: #627d98; margin: -0.15rem 0 0.7rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.pra { font-size: 0.72rem; color: #1a3d5c; font-weight: 600; margin-top: 0.15rem; }
.trail { font-size: 0.88rem; color: #243b53; margin: 0 0 0.7rem; }
.m6-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.55rem; margin: 0.4rem 0 0.7rem; }
@media (max-width: 900px) { .m6-grid { grid-template-columns: 1fr; } }
.deck-row { font-size: 0.78rem; color: #243b53; padding: 0.35rem 0; border-bottom: 1px solid #e8eef4; }
.deck-row .after { color: #627d98; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em; }
</style>
""",
    unsafe_allow_html=True,
)


def _esc(v) -> str:
    return html.escape("" if v is None else str(v))


def verdict_class(text: str) -> str:
    t = (text or "").upper()
    if t.startswith("ALERT"):
        return "ALERT"
    if t.startswith("WATCH"):
        return "WATCH"
    if t.startswith("NULL"):
        return "NULL"
    return "OTHER"


def short_verdict(text: str) -> str:
    raw = (text or "—").split("—")[0].split("-")[0].strip().upper()
    return raw if raw in {"ALERT", "WATCH", "NULL"} else (text or "—")[:24]


def bank_label(ep: dict) -> str:
    raw = str(ep.get("bank") or "").lower()
    return BANK_DISP.get(raw, (ep.get("bank") or "").replace("_", " ").title())


def fmt_ts(mtime: float) -> str:
    if not mtime:
        return "—"
    return datetime.fromtimestamp(mtime).strftime("%d %b %Y · %H:%M")


def in_peer_window(label) -> bool:
    m = re.search(r"(20\d{2})", str(label or ""))
    if not m:
        return False
    y = int(m.group(1))
    return 2012 <= y <= 2025


def agree_row(row: pd.Series) -> str:
    # 0/1 from SQLite is not `is True` / `is False`.
    labelled = None
    faith = row.get("faithful")
    try:
        missing = bool(pd.isna(faith))
    except (TypeError, ValueError):
        missing = faith is None
    if not missing:
        labelled = "yes" if bool(faith) else "no"
    if labelled is not None:
        return labelled
    nar = str(row.get("narrative_direction") or "").strip().lower()
    hits = row.get("n_qa_hits")
    if pd.isna(hits) or int(hits or 0) == 0 or nar in ("", "nan", "none"):
        return "n/a"
    rep = str(row.get("reported_direction") or "").lower()
    return "yes" if rep == nar else "no"


def pick_pra_section(text: str, ep: dict) -> str:
    chunks = text.split("\n\n---\n\n")
    eid_bits = (
        (ep.get("label") or ""),
        (ep.get("calendar_period") or ""),
        (ep.get("quarter") or ""),
        (ep.get("bank") or "").upper(),
    )
    for ch in chunks:
        if ep.get("id") and ep["id"] in ch:
            return ch
        if eid_bits[0] and eid_bits[0] in ch:
            return ch
        bank, period = eid_bits[3], eid_bits[1]
        if bank and period and bank in ch and period in ch:
            return ch
    return chunks[0] if chunks else text


def request_refresh() -> None:
    st.session_state.force_refresh = True
    st.rerun()


def render_ops(status: dict) -> None:
    if st.button("Rebuild episodes + PRA", use_container_width=True):
        with st.spinner("Rebuilding…"):
            st.session_state.desk_status = ensure_desk(force=True, rebuild_episodes=True)
            st.cache_data.clear()
        st.rerun()
    st.markdown(
        f"""<div class="admin-card"><div class="k">Pack updated</div>
        <div class="v">{_esc(fmt_ts(status.get("desk_mtime") or 0))}</div></div>""",
        unsafe_allow_html=True,
    )
    if st.button("Check FT gates", use_container_width=True):
        st.session_state.show_recal = True
    if st.session_state.get("show_recal"):
        chk = check_recalibration()
        ready = bool(chk.get("retrain_recommended"))
        st.markdown(
            '<span class="admin-badge go">Retrain</span>' if ready
            else '<span class="admin-badge wait">Not promoted</span>',
            unsafe_allow_html=True,
        )
        bits = [
            f"Human gold {chk.get('n_m4_gold_pairs') or 0} M4 pairs",
            f"hand queue {chk.get('n_hand_queue_reviewed') or 0}",
        ]
        if chk.get("active_model_id"):
            bits.append(f"new since promote {chk.get('n_new_since_promote') or 0}")
        st.caption(" · ".join(bits))
        for tip in (chk.get("advice") or [])[:3]:
            st.caption(tip)
    reg = load_registry()
    st.markdown(
        f"""<div class="admin-card"><div class="k">Active model</div>
        <div class="v">{_esc(reg.get("active_model_id") or "Zero-shot FinBERT")}</div></div>""",
        unsafe_allow_html=True,
    )
    st.caption("Batch recalibration only. Never retrain on a single IR drop-in.")


def render_ops_page(status: dict) -> None:
    st.markdown('<div class="section-h">Ops</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="note">Engineering only — FT promotion gates, not the '
        "supervisory readout. On silver labels alone, fine-tuning looked like it "
        "helped — that is the circular trap the gate exists to catch. Against "
        "human gold it did worse, so it stays unpromoted.</div>",
        unsafe_allow_html=True,
    )
    render_ops(status)


def _hide_sidebar() -> None:
    st.markdown(
        "<style>[data-testid='stSidebar'] {display: none;}</style>",
        unsafe_allow_html=True,
    )


def _protocol_lookup(episodes: list[dict]) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for e in episodes:
        bank = str(e.get("bank") or "").lower()
        out[(bank, str(e.get("quarter") or ""))] = e
        out[(bank, str(e.get("calendar_period") or ""))] = e
    return out


def _verdict_markup(ep: dict) -> str:
    vc = verdict_class(ep.get("verdict", ""))
    sv = short_verdict(ep.get("verdict", ""))
    if is_reviewed_episode(ep):
        return f'<span class="verdict-pill verdict-{vc}">{_esc(sv)}</span>'
    return (
        f'<span class="verdict-pill verdict-{vc} unreviewed">{_esc(sv)}</span>'
        f'<span class="unreviewed-tag">Unreviewed</span>'
    )


def _cell(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    s = str(v).strip()
    if s.lower() in {"", "nan", "none", "<na>"}:
        return "—"
    return _esc(s)


def _render_browse_row(row: pd.Series, proto_ep: dict | None) -> None:
    q = str(row.get("question_text") or "")
    if q.lower() in {"", "nan", "none"}:
        q = "—"
    title = (
        f"{bank_label({'bank': row.get('bank')})} · "
        f"{row.get('calendar_period') or '—'} — {q[:80]}"
    )
    with st.expander(title):
        st.markdown(
            f'<div class="quote-meta">{_cell(row.get("bank"))} · '
            f'{_cell(row.get("calendar_period"))}</div>'
            f'<div class="quote-block">{_cell(row.get("question_text"))}</div>'
            f'<div class="quote-block">{_cell(row.get("answer_text"))}</div>'
            f'<div class="metrics">'
            f'  <div class="m"><div class="lbl">FinBERT</div><div class="val">{_cell(row.get("finbert_sentiment"))}</div></div>'
            f'  <div class="m"><div class="lbl">LDSA</div><div class="val">{_cell(row.get("ldsa_sentiment"))}</div></div>'
            f'  <div class="m"><div class="lbl">Directness</div><div class="val">{_cell(row.get("directness"))}</div></div>'
            f'  <div class="m"><div class="lbl">Topic</div><div class="val">{_cell(row.get("topic_id"))}</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if proto_ep is None:
            st.caption("No protocol row for this bank-quarter.")
        else:
            st.markdown(_verdict_markup(proto_ep), unsafe_allow_html=True)
            if is_reviewed_episode(proto_ep):
                st.caption("Reviewed Case File episode — open Case File for the captioned walkthrough.")
            else:
                st.caption(
                    "Same A1–A3/N1 rules as the Case File. Unreviewed — not captioned."
                )


def render_browse_tab(mtime: float, episodes: list[dict] | None = None) -> None:
    st.markdown('<div class="section-h">Browse the full corpus</div>', unsafe_allow_html=True)

    full = _table("qa_pairs_full", None, mtime)
    if full is None or full.empty:
        st.markdown(
            '<div class="note">No full-corpus export yet. Run Stage 9 in the '
            "factory notebook, then refresh.</div>",
            unsafe_allow_html=True,
        )
        return

    proto = _protocol_lookup(episodes or [])

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        bank_options = ["All"] + sorted(full["bank"].dropna().unique().tolist())
        bank_pick = st.selectbox("Bank", bank_options)
    with col2:
        scoped = full if bank_pick == "All" else full[full["bank"] == bank_pick]
        quarter_options = ["All"] + sorted(scoped["calendar_period"].dropna().unique().tolist())
        quarter_pick = st.selectbox("Quarter", quarter_options)
    with col3:
        sort_pick = st.selectbox(
            "Sort by",
            ["Most negative (FinBERT)", "Least direct", "Topic-substituted first"],
        )

    rows = full.copy()
    if bank_pick != "All":
        rows = rows[rows["bank"] == bank_pick]
    if quarter_pick != "All":
        rows = rows[rows["calendar_period"] == quarter_pick]

    rows = _sort_browse_rows(rows, sort_pick)

    st.caption(f"{len(rows)} pairs match this filter.")
    st.caption(
        "Unreviewed protocol uses the same A1–A3/N1 gates. It is not a Case File caption."
    )

    for _, row in rows.head(50).iterrows():
        bank = str(row.get("bank") or "").lower()
        proto_ep = proto.get((bank, str(row.get("quarter") or ""))) or proto.get(
            (bank, str(row.get("calendar_period") or ""))
        )
        _render_browse_row(row, proto_ep)


# —— Bootstrap ——————————————————————————————————————————————
force = bool(st.session_state.pop("force_refresh", False))
if "desk_status" not in st.session_state or force:
    if force or not DB_PATH.exists():
        with st.spinner("Loading supervisory pack…"):
            st.session_state.desk_status = ensure_desk(force=force)
            st.cache_data.clear()
    else:
        st.session_state.desk_status = ensure_desk(force=False)

status = st.session_state.desk_status


@st.cache_data
def _episodes(mtime: float) -> list[dict]:
    _ = mtime
    return list_episodes()


@st.cache_data
def _table(name: str, episode_id: str | None, mtime: float) -> pd.DataFrame:
    _ = mtime
    return read_table(name, episode_id=episode_id)


mt = status.get("desk_mtime") or (DB_PATH.stat().st_mtime if DB_PATH.exists() else 0)

st.markdown(
    f"""
    <div class="topbar">
      <p class="brand">PRA Earnings Desk</p>
      <div class="meta">Group 9 · Bank of England employer project<br>pack {_esc(fmt_ts(mt))}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not status.get("desk_ready") and not DB_PATH.exists():
    st.error("No supervisory pack. Run the factory notebook (Stages 1–9), then refresh.")
    with st.sidebar:
        if st.button("Refresh pack from factory", use_container_width=True):
            request_refresh()
    st.stop()

episodes = _episodes(mt)
if not episodes:
    st.warning("Desk has no protocol cases yet.")
    with st.sidebar:
        if st.button("Build episodes from factory", use_container_width=True):
            st.session_state.desk_status = ensure_desk(force=True, rebuild_episodes=True)
            st.cache_data.clear()
            st.rerun()
    st.stop()

by_id = {e.get("id"): e for e in episodes if e.get("id")}


def _default_id(eps: list[dict]) -> str:
    for e in eps:
        if e.get("id") == "hsbc_2025_h1":
            return e["id"]
    return eps[0].get("id") or ""


if "selected_id" not in st.session_state:
    st.session_state.selected_id = _default_id(episodes)
if st.session_state.selected_id not in by_id:
    st.session_state.selected_id = _default_id(episodes)

view = (
    st.segmented_control(
        "Desk view",
        options=["Case File", "Browse", "Ops"],
        default="Case File",
        key="desk_view",
        label_visibility="collapsed",
    )
    or "Case File"
)

if view != "Case File":
    _hide_sidebar()

if view == "Browse":
    render_browse_tab(mt, episodes)
    st.stop()

if view == "Ops":
    render_ops_page(status)
    st.stop()

with st.sidebar:
    st.markdown("**Inbox**")

    grouped: dict[str, list[dict]] = {"paired": [], "in_progress": [], "a3": []}
    for e in episodes:
        if is_reviewed_episode(e):
            grouped[inbox_bucket(e)].append(e)

    def _nav_button(e: dict) -> None:
        eid0 = e.get("id")
        sv0 = short_verdict(e.get("verdict", ""))
        bank0 = bank_label(e)
        period0 = inbox_period_label(e)
        selected = eid0 == st.session_state.selected_id
        if st.button(
            f"{sv0}  ·  {bank0} {period0}",
            key=f"nav_{eid0}",
            use_container_width=True,
            type="primary" if selected else "secondary",
        ):
            st.session_state.selected_id = eid0
            st.rerun()

    st.caption("Paired quarter · HSBC interim ≡ Barclays q2")
    for e in grouped["paired"]:
        _nav_button(e)
    st.caption("Peer on this case: Barclays 2025-H1 (q2).")

    st.caption("2012–2025 · both complete")
    st.caption("2026 · in progress, 2 quarters to date")
    for e in grouped["in_progress"]:
        _nav_button(e)

    st.caption("Credit Suisse · deferred to A3")
    for e in grouped["a3"]:
        _nav_button(e)

    unreviewed_eps = [e for e in episodes if not is_reviewed_episode(e)]
    if unreviewed_eps:
        st.divider()
        st.caption("Unreviewed — same rules, not captioned")
        unreviewed_eps = sorted(
            unreviewed_eps,
            key=lambda e: str(e.get("calendar_period") or e.get("quarter") or ""),
            reverse=True,
        )
        labels = [
            f"{short_verdict(e.get('verdict', ''))} · {bank_label(e)} "
            f"{e.get('calendar_period') or e.get('quarter')}"
            for e in unreviewed_eps
        ]
        pick = st.selectbox(
            "Computed quarters",
            options=["—"] + labels,
            key="unreviewed_pick",
        )
        if pick != "—":
            chosen = unreviewed_eps[labels.index(pick)]
            if chosen.get("id") != st.session_state.selected_id:
                st.session_state.selected_id = chosen["id"]
                st.rerun()

    st.divider()
    if st.button("Refresh pack from factory", use_container_width=True):
        request_refresh()
    st.caption("Copies factory `boe.sqlite` into this desk. Does not re-run the notebook.")
    with st.expander("This desk completes the deck", expanded=False):
        st.caption(
            "After each slide, the live proof is here — not a second speech. "
            f"[A2 slides]({SLIDES_URL})"
        )
        for row in DECK_TRAIL:
            st.markdown(
                f'<div class="deck-row"><div class="after">{_esc(row["after"])}</div>'
                f"<strong>{_esc(row['shows'])}</strong><br>"
                f"<span class='factory'>{_esc(row['factory'])} · {_esc(row['table'])}</span></div>",
                unsafe_allow_html=True,
            )

ep = by_id[st.session_state.selected_id]
eid = ep.get("id")
vc = verdict_class(ep.get("verdict", ""))
sv = short_verdict(ep.get("verdict", ""))
net = ep.get("finbert_net")
net_s = f"{net:.3f}" if isinstance(net, (int, float)) else "—"
period = ep.get("calendar_period") or ep.get("quarter") or ""
bank = bank_label(ep)
reviewed = is_reviewed_episode(ep)
cs_case = "credit" in str(ep.get("bank") or "").lower()
neg = ep.get("topic1_neg_share")
neg_s = f"{float(neg):.0%}" if isinstance(neg, (int, float)) else "—"

st.markdown(
    f"""
    <div class="banner">
      {_esc(PROBLEM)}
      Alert / watch / null is a <strong>protocol output</strong>, not a PRA rating
      (Bank TRUSTED: Ethical — decision-augmentation; a supervisor decides).
    </div>
    <div class="queue">
      <span>HSBC <b>73</b></span>
      <span>Barclays <b>63</b></span>
      <span>Paired quarters <b>62</b></span>
      <span>2026 <b>in progress</b></span>
    </div>
    """,
    unsafe_allow_html=True,
)

# —— Case file (one scroll) ————————————————————————————————
st.markdown(
    f"""
    {_verdict_markup(ep)}
    <span style="margin-left:0.65rem;font-weight:600;color:#102a43">{_esc(bank)} · {_esc(period)}</span>
    <p class="headline">{_esc(ep.get("label") or f"{bank} {period}")}</p>
    <p class="why">{_esc(ep.get("verdict") or "")}</p>
    <p class="trail">{_esc(trail_for(ep))}</p>
    <div class="metrics">
      <div class="m"><div class="lbl">FinBERT net</div><div class="val">{_esc(net_s)}</div></div>
      <div class="m"><div class="lbl">Analyst turns</div><div class="val">{_esc(ep.get("n_turns", "—"))}</div></div>
      <div class="m"><div class="lbl">Topic 1 turns</div><div class="val">{_esc(ep.get("topic1_turns", "—"))}</div></div>
      <div class="m"><div class="lbl">Topic 1 neg</div><div class="val">{_esc(neg_s)}</div></div>
      <div class="m"><div class="lbl">Rules</div><div class="val">{_esc(", ".join(ep.get("rules_fired") or ["—"]))}</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)
if reviewed and cs_case:
    st.markdown(
        '<div class="note"><strong>Out-of-sample.</strong> Credit Suisse is a protocol case '
        "for 2022-Q4 only. Extra 2020–2022 calls stay in the corpus trend below — they are not extra failed-bank proofs.</div>",
        unsafe_allow_html=True,
    )
if ep.get("peer_caveat"):
    st.markdown(
        f'<div class="caveat"><strong>Peer caveat</strong> — {_esc(ep["peer_caveat"])}</div>',
        unsafe_allow_html=True,
    )

# Four KPIs
briefs = _table("metric_briefs", eid, mt)
st.markdown('<div class="section-h">Four KPIs — pack vs Q&amp;A</div>', unsafe_allow_html=True)
if briefs is not None and not briefs.empty:
    by_m = {str(r["metric"]): r for _, r in briefs.iterrows()}
    tiles = []
    for m in METRIC_ORDER:
        row = by_m.get(m)
        pra = KPI_TO_PRA.get(m, {})
        pra_s = f"{pra.get('pra', '')} · {pra.get('seed', '')}" if pra else ""
        if row is None:
            tiles.append(
                f'<div class="kpi"><div class="name">{METRIC_LABELS[m]}</div>'
                f'<div class="dir">—</div><div class="qa agree-na">not in this pack</div>'
                f'<div class="pra">{_esc(pra_s)}</div></div>'
            )
            continue
        agree = agree_row(row)
        cls = {"yes": "agree-yes", "no": "agree-no"}.get(agree, "agree-na")
        rep = row.get("reported_direction") or "n/a"
        nar = row.get("narrative_direction")
        nar_s = "n/a" if nar is None or (isinstance(nar, float) and pd.isna(nar)) else str(nar)
        hits = int(row.get("n_qa_hits") or 0)
        tiles.append(
            f'<div class="kpi"><div class="name">{METRIC_LABELS[m]}</div>'
            f'<div class="dir">Pack { _esc(rep) }</div>'
            f'<div class="qa">Q&amp;A { _esc(nar_s) } · {hits} hits · '
            f'<span class="{cls}">agree {agree}</span></div>'
            f'<div class="pra">{_esc(pra_s)}</div></div>'
        )
    st.markdown('<div class="kpi-grid">' + "".join(tiles) + "</div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="factory">scripts/build_metric_briefs.py · PRA codes from '
        "docs/assignment2/A2_prudential_taxonomies.md (independent of the corpus)</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Agree is yes/no only when Q&A tone exists. Absence of a metric hit is n/a, not agreement. "
        + LIQUIDITY_NOTE
    )
else:
    st.caption("No metric briefs for this case — rebuild episodes from Ops.")

# Differentiator #1 — how they answered (not FinBERT)
st.markdown(
    '<div class="section-h">How they answered — not just how it sounded</div>',
    unsafe_allow_html=True,
)
ss = _table("state_summary", None, mt)
ss_ep = rows_for_episode(ss, ep)
if ss_ep is not None and not ss_ep.empty:
    r0 = ss_ep.iloc[0]

    def _num(val, kind: str) -> str:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return "—"
        try:
            v = float(val)
        except (TypeError, ValueError):
            return "—"
        if kind == "rate":
            return f"{v:.0%}" if v <= 1 else f"{v:.0f}%"
        return f"{v:.2f}"

    d = _num(r0.get("mean_directness"), "score")
    cov = _num(r0.get("metric_coverage_rate"), "rate")
    sub = _num(r0.get("substitution_rate"), "rate")
    n_pairs = r0.get("n") or r0.get("n_pairs") or "—"
    st.markdown(
        f"""
        <div class="m6-grid">
          <div class="kpi"><div class="name">Answer directness</div>
            <div class="dir">{_esc(d)}</div>
            <div class="qa">token overlap Q∩A · n={_esc(n_pairs)}</div></div>
          <div class="kpi"><div class="name">Metric covered when asked</div>
            <div class="dir">{_esc(cov)}</div>
            <div class="qa">four KPIs only</div></div>
          <div class="kpi"><div class="name">Topic substitution</div>
            <div class="dir">{_esc(sub)}</div>
            <div class="qa">asked one theme, answered another</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="factory">scripts/build_a1_evidence.py → behavioural_signals() / '
        "state_summary · Avoidance is behaviour, not a FinBERT class</div>",
        unsafe_allow_html=True,
    )
    beh = _table("behavioural_signals", None, mt)
    beh_ep = rows_for_episode(beh, ep)
    if beh_ep is not None and not beh_ep.empty and "topic_substitution" in beh_ep.columns:
        swapped = beh_ep[pd.to_numeric(beh_ep["topic_substitution"], errors="coerce").fillna(0) > 0]
        if not swapped.empty:
            ex = swapped.iloc[0]
            q = str(ex.get("question_text") or "")[:280]
            a = str(ex.get("answer_text") or "")[:280]
            st.markdown(
                f'<div class="quote-block"><div class="quote-meta">Substitution example this print</div>'
                f"<strong>Q</strong> {_esc(q)}<br><strong>A</strong> {_esc(a)}</div>",
                unsafe_allow_html=True,
            )
else:
    st.caption("No M6 row for this print in state_summary — extras still hold the corpus series.")

# Protocol
proto = _table("protocol", None, mt)
fired = set(ep.get("rules_fired") or [])
st.markdown('<div class="section-h">Protocol this print</div>', unsafe_allow_html=True)
if proto is not None and not proto.empty:
    st.markdown(
        '<div class="rule head"><div>Rule</div><div>Severity</div><div>This case</div><div>Condition</div></div>',
        unsafe_allow_html=True,
    )
    for _, r in proto.iterrows():
        rid = str(r.get("rule_id") or "")
        mark = "FIRED" if rid in fired else "—"
        cls = "rule fired" if rid in fired else "rule"
        st.markdown(
            f'<div class="{cls}"><div><strong>{_esc(rid)}</strong></div>'
            f'<div>{_esc(r.get("severity"))}</div><div>{mark}</div>'
            f'<div>{_esc(r.get("condition"))}</div></div>',
            unsafe_allow_html=True,
        )
    st.caption(
        "A2 peer ALERT is HSBC−Barclays only, and only when both sides are informative "
        "(not 100% FinBERT-neutral). scripts/build_supervisory_episode.py"
    )
else:
    st.caption("No protocol table in this pack.")

# Quotes
quotes = _table("quotes", eid, mt)
st.markdown('<div class="section-h">Quoted turns</div>', unsafe_allow_html=True)
if quotes is not None and not quotes.empty:
    for _, q in quotes.head(6).iterrows():
        sent = str(q.get("finbert_sentiment") or "")
        text = str(q.get("text") or "")
        st.markdown(
            f"""
            <div class="quote-block">
              <div class="quote-meta">{_esc(q.get("speaker", ""))} · {_esc(q.get("firm", ""))}
              · topic {_esc(q.get("topic", ""))} · <strong>{_esc(sent)}</strong>
              ({float(q.get("finbert_score") or 0):.2f})</div>
              {_esc(text[:520])}{"…" if len(text) > 520 else ""}
            </div>
            """,
            unsafe_allow_html=True,
        )
else:
    st.caption("No quotes stored for this case.")
st.markdown(
    '<div class="factory">scripts/build_supervisory_episode.py · quotes table</div>',
    unsafe_allow_html=True,
)

# Peer
st.markdown('<div class="section-h">Matched peer (HSBC − Barclays)</div>', unsafe_allow_html=True)
if cs_case:
    st.caption("Peer gap is HSBC−Barclays only. n/a for out-of-sample banks.")
else:
    hs = ep.get("peer_hsbc_net")
    ba = ep.get("peer_barclays_net")
    gap = ep.get("peer_gap_hsbc_minus_barclays")
    usable = bool(ep.get("peer_usable_for_a2"))
    hs_s = f"{hs:.3f}" if isinstance(hs, (int, float)) else "—"
    ba_s = f"{ba:.3f}" if isinstance(ba, (int, float)) else "—"
    gap_s = f"{gap:.3f}" if isinstance(gap, (int, float)) else "—"
    hs_nn = ep.get("peer_hsbc_non_neutral_share")
    ba_nn = ep.get("peer_barclays_non_neutral_share")
    hs_nn_s = f"{float(hs_nn):.0%}" if isinstance(hs_nn, (int, float)) else "—"
    ba_nn_s = f"{float(ba_nn):.0%}" if isinstance(ba_nn, (int, float)) else "—"
    st.write(
        f"**{period}** · HSBC {hs_s} (n={ep.get('peer_hsbc_n', '—')}, non-neut {hs_nn_s}) · "
        f"Barclays {ba_s} (n={ep.get('peer_barclays_n', '—')}, non-neut {ba_nn_s}) · "
        f"gap {gap_s} · A2-usable **{'yes' if usable else 'no'}**"
    )
    cov = _table("corpus_coverage", None, mt)
    st.caption(coverage_line(cov))
    st.markdown(
        '<div class="factory">scripts/periods.py · calendar_period() joins HSBC interim≡Barclays q2. '
        "Never fillna(0) on a gap — zero would read as 'the banks matched'.</div>",
        unsafe_allow_html=True,
    )
    peer_gap = _table("peer_gap", None, mt)
    if peer_gap is not None and not peer_gap.empty and "calendar_period" in peer_gap.columns:
        hist = peer_gap[peer_gap["calendar_period"].map(in_peer_window)].copy()
        keep = [c for c in ["calendar_period", "hsbc", "barclays", "gap"] if c in hist.columns]
        if keep:
            hist = hist[keep]
        for c in ("hsbc", "barclays", "gap"):
            if c in hist.columns:
                hist[c] = pd.to_numeric(hist[c], errors="coerce").round(3)
        st.caption("History is HSBC vs Barclays, 2012–2025. 2026 stays on this case file, not the chart.")
        if not hist.empty:
            st.dataframe(hist.tail(12), width="stretch", hide_index=True)
    peer_file = DEMO_DATA / "peer_gap_matched.png"
    blob = peer_file.read_bytes() if peer_file.exists() else read_asset("peer_gap_matched.png")
    if blob:
        st.image(blob, width="stretch")

# PRA note
st.markdown('<div class="section-h">PRA one-pager</div>', unsafe_allow_html=True)
if not reviewed:
    st.caption("No PRA one-pager — this quarter has not been reviewed.")
else:
    pra = read_document("pra_notes.md")
    if pra:
        st.markdown(pick_pra_section(pra, ep))
        st.download_button(
            "Download full PRA pack",
            data=pra,
            file_name="pra_notes.md",
            mime="text/markdown",
            type="primary",
        )
    else:
        st.caption("PRA note missing — Ops → Rebuild episodes + PRA.")
st.markdown(
    '<div class="factory">scripts/generate_pra_note.py · docs/assignment2/pra_notes/</div>',
    unsafe_allow_html=True,
)

# Corpus extras — not the case file
with st.expander("Corpus extras (not protocol)", expanded=False):
    st.caption(
        "Coverage, stress-window notes from the deck, CS extra-year trend, synthetic log. "
        "None of this is a firm rating or an extra protocol case. Association, not prediction: "
        "neither HSBC nor Barclays had a prudential event in-window."
    )
    cov_tbl = _table("corpus_coverage", None, mt)
    if cov_tbl is not None and not cov_tbl.empty:
        st.markdown("**Coverage by bank × year (results_call)**")
        st.dataframe(cov_tbl, width="stretch", hide_index=True)
    st.markdown("**Deck stress windows (association only)**")
    st.caption(
        "COVID: 2019 Q3–2020 Q1 — did credit/provisioning directness fall before lockdown? "
        "Truss mini-budget Sep 2022. SVB / CS Mar 2023: 2022 Q2 onward — deposits/liquidity. "
        "2023 is the better test of anticipation; COVID was exogenous."
    )
    trend = _table("cs_quarter_trend", None, mt)
    if trend is not None and not trend.empty:
        st.markdown("**Credit Suisse extra years (corpus only)**")
        st.dataframe(trend, width="stretch", hide_index=True)
    log = _table("pra_supervisor_log", None, mt)
    if log is not None and not log.empty:
        st.markdown("**Synthetic desk log**")
        if "disclaimer" in log.columns:
            st.caption(str(log["disclaimer"].iloc[0]))
        cols = [c for c in ["timestamp_utc", "episode_id", "action", "protocol_output", "note"] if c in log.columns]
        st.dataframe(log[cols], width="stretch", hide_index=True)
    pmap = _table("prudential_map", None, mt)
    pmap_ep = rows_for_episode(pmap, ep)
    if pmap_ep is not None and not pmap_ep.empty and "coder1_category" in pmap_ep.columns:
        st.markdown("**Eight-way machine map this print (not the human dual-code)**")
        st.dataframe(
            pmap_ep["coder1_category"].value_counts().rename("n").reset_index(),
            width="stretch",
            hide_index=True,
        )
    topics = _table("topic_share", eid, mt)
    if topics is not None and not topics.empty:
        st.markdown("**Topic share this print**")
        st.dataframe(topics, width="stretch", hide_index=True)


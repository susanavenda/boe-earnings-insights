"""Stage 6.3 parsers: four locked KPIs and their direction from the Excel data packs.

Moved out of the notebook so Stage 1.5 can build `reported_metrics` before
`state_summary` (issue #86). Before, `state_summary` read the table Stage 6.3 had
written on the *previous* run, so a fresh run had no reported directions.

Same four lines as Stage 2.0 / M3 — do not add ROA, NIM, NPL, LDR here.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from hsbc_pack import parse_hsbc_datapack  # HSBC changed pack layout in 2018 Q4 and 2020 Q2
from keywords import reported_direction
from periods import calendar_period

ROOT = Path(__file__).resolve().parents[1]
STRUCTURED_ROOT = ROOT / "data" / "structured"
METRICS_OF_INTEREST = ['total_income', 'operating_costs', 'credit_impairment', 'cet1_ratio']


def _norm(s):
    return re.sub(r'\s+', ' ', str(s).replace('\n', ' ').strip().lower())

def _to_float(v):
    if isinstance(v, (int, float)) and not pd.isna(v):
        return float(v)
    return None

def _direction(curr, prev, metric=None, flat_tol=0.01):
    # Costs and impairment: compare absolute values (a larger charge is "up").
    return reported_direction(curr, prev, metric=metric, flat_tol=flat_tol, rescale_pct=True)

def _first_match(label_map, aliases):
    hits = [(lab, vals) for lab, vals in label_map.items() if any(a == lab or a in lab for a in aliases)]
    if not hits:
        return None
    hits.sort(key=lambda x: len(x[0]))
    return hits[0][1]

def _quarter_from_name(path):
    """Filename → bank-style quarter (join key with transcript `quarter`).

    Peer/Excel calendar keys use periods.calendar_period() on that label — do not
    duplicate a year table here. Stem aliases (h1→interim, 2q→q2) are filename parsing.
    """
    name = Path(path).stem.lower()
    m = re.search(r'(20\d{2}).*?(q[1-4]|h1|fy|1q|2q|3q|4q|interim|annual)', name)
    if not m:
        return Path(path).stem
    y, p = m.group(1), m.group(2)
    mapping = {'h1': 'interim', 'fy': 'annual', '1q': 'q1', '2q': 'q2', '3q': 'q3', '4q': 'q4'}
    return f'{y}-{mapping.get(p, p)}'

def parse_barclays_group_ph(path):
    xl = pd.ExcelFile(path)
    needles = (
        'group ph', 'group p&l', 'group pl', 'performance highlight',
        'income statement', 'profit and loss',
    )
    sheet = next((s for s in xl.sheet_names if any(n in s.lower() for n in needles)), None)
    if sheet is None:
        # 2024 tables workbooks sometimes omit the Group PH tab name — scan for Total income
        for s in xl.sheet_names:
            preview = pd.read_excel(path, sheet_name=s, header=None, nrows=80)
            blob = ' '.join(preview.astype(str).values.ravel()[:400]).lower()
            if 'total income' in blob:
                sheet = s
                break
    if sheet is None:
        print(f"WARN: no P&L sheet in {Path(path).name}: {xl.sheet_names}")
        return {}
    df = pd.read_excel(path, sheet_name=sheet, header=None)
    label_map = {}
    layouts = [(1, 2, 3), (0, 1, 2)]
    for lab_i, a_i, b_i in layouts:
        trial = {}
        for _, row in df.iterrows():
            if lab_i >= len(row):
                continue
            lab = row.iloc[lab_i]
            if pd.isna(lab):
                continue
            a, b = _to_float(row.iloc[a_i] if a_i < len(row) else None), _to_float(row.iloc[b_i] if b_i < len(row) else None)
            if a is None or b is None:
                continue
            trial[_norm(lab)] = (a, b)
        if _first_match(trial, ['total income']):
            label_map = trial
            break
        if len(trial) > len(label_map):
            label_map = trial
    return {
        'total_income': _first_match(label_map, ['total income']),
        'operating_costs': _first_match(label_map, ['operating costs', 'operating expenses', 'total operating expenses']),
        'credit_impairment': _first_match(label_map, ['credit impairment charges', 'credit impairment', 'impairment charges']),
        'cet1_ratio': _first_match(label_map, ['common equity tier 1 ratio', 'cet1 ratio']),
    }

def parse_credit_suisse_pack(path):
    """4 locked KPIs from a one-sheet CS pack (SEC 6-K Exhibit 99.1 numbers)."""
    df = pd.read_excel(path, sheet_name='Group key metrics')
    alias = {
        'net revenues': 'total_income',
        'provision for credit losses': 'credit_impairment',
        'total operating expenses': 'operating_costs',
        'cet1 ratio': 'cet1_ratio',
    }
    out = {}
    for _, row in df.iterrows():
        lab = str(row.get('metric', '')).strip().lower()
        key = alias.get(lab)
        if not key:
            continue
        curr, prev = _to_float(row.get('current')), _to_float(row.get('prior'))
        if curr is None or prev is None:
            continue
        out[key] = (curr, prev)
    return out

def build_reported_metrics(structured_root: Path = STRUCTURED_ROOT) -> pd.DataFrame:
    """One row per bank × quarter × metric from every pack under structured_root."""
    rows = []
    for bank, folder, parser in [
        ('barclays', structured_root / 'barclays', parse_barclays_group_ph),
        ('hsbc', structured_root / 'hsbc', parse_hsbc_datapack),
        ('credit_suisse', structured_root / 'credit_suisse', parse_credit_suisse_pack),
    ]:
        if not folder.exists():
            continue
        n_files, n_parsed = 0, 0
        for path in sorted(folder.glob('*.xlsx')):
            n_files += 1
            try:
                parsed = parser(path)
            except Exception as exc:
                print(f'WARN: skip {path.name}: {type(exc).__name__}: {exc}')
                continue
            if parsed:
                n_parsed += 1
            q = _quarter_from_name(path)
            for metric, vals in parsed.items():
                if not vals or metric not in METRICS_OF_INTEREST:
                    continue
                curr, prev = vals
                rows.append({
                    'bank': bank,
                    'quarter': q,
                    'metric': metric,
                    'value': curr,
                    'prior': prev,
                    'direction': _direction(curr, prev, metric),
                    'source': path.name,
                })
        print(f'{bank}: parsed {n_parsed} of {n_files} packs')
    out = pd.DataFrame(rows)
    if len(out):
        out['calendar_period'] = out['quarter'].map(calendar_period)
    return out

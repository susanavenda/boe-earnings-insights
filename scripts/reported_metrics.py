"""Stage 6.3 parsers: four locked KPIs and their direction from the Excel data packs.

Moved out of the notebook so Stage 1.5 can build `reported_metrics` before
`state_summary` (issue #86). Before, `state_summary` read the table Stage 6.3 had
written on the *previous* run, so a fresh run had no reported directions.

Same four lines as Stage 2.0 / M3 — do not add ROA, NIM, NPL, LDR here.
"""
from __future__ import annotations

import re
from datetime import datetime
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
    # Some older packs store figures as text, e.g. "31,440 " (Barclays 2010 FY).
    if isinstance(v, str) and re.fullmatch(r'\s*-?[\d,]+(\.\d+)?\s*', v):
        return float(v.replace(',', ''))
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

_PERIOD_END = {'q1': '03-31', 'interim': '06-30', 'q2': '06-30', 'q3': '09-30', 'annual': '12-31', 'q4': '12-31'}
_POUND_M = re.compile(r'^£\s*m$', re.I)
_DATE_TEXT = re.compile(r'\b(\d{2})\.(\d{2})\.(\d{2}|\d{4})\b')
CET1_ALIASES = ['common equity tier 1 ratio', 'cet1 ratio']


def _header_layout(df, max_rows=15):
    """(label, current, prior) columns from the first row with two '£m' headings.

    Older Barclays sheets put a Notes column (2011-12 FY) or blank spacer columns
    (2011 Q3) between the label and the figures, so fixed layouts miss them (#90).
    """
    for i in range(min(max_rows, len(df))):
        cols = [j for j, v in enumerate(df.iloc[i]) if isinstance(v, str) and _POUND_M.match(v.strip())]
        if len(cols) < 2:
            continue
        below = df.iloc[i + 1:, :cols[0]]
        if below.shape[1] == 0:
            return None
        text = below.apply(lambda c: c.map(lambda v: isinstance(v, str) and _to_float(v) is None).sum())
        return int(text.idxmax()), cols[0], cols[1]
    return None


def _first_header_date(df, max_rows=8):
    for v in df.iloc[:max_rows].to_numpy().ravel():
        if isinstance(v, datetime):
            return v.strftime('%Y-%m-%d')
        if isinstance(v, str):
            m = _DATE_TEXT.search(v)
            if m:
                d, mo, y = m.groups()
                return f"{'20' + y if len(y) == 2 else y}-{mo}-{d}"
    return None


def _sheet_for_period(xl, path, expected):
    """First sheet dated `expected` that prints a total income line, or None.

    The 2014 and 2015 H1 workbooks put the 2013 FY tables first and the H1 tables
    after them, so the first P&L-looking sheet is the wrong period (#90).
    """
    for sheet in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=sheet, header=None, nrows=80)
        if _first_header_date(df) != expected:
            continue
        if 'total income' in ' '.join(_norm(v) for v in df.to_numpy().ravel() if isinstance(v, str)):
            return sheet
    return None


def _cet1_from_summary(xl, path, expected=None, first=None, max_sheets=3):
    """CET1 (current, prior) from a summary sheet's capital block, when the P&L sheet has none.

    2013-15 packs print it lower down the first sheet with its own columns. Sheets dated
    another period are ignored. Rows with a single value are skipped: a direction needs
    a prior, and a missing prior reads as flat.
    """
    sheets = ([first] if first else []) + [s for s in xl.sheet_names[:max_sheets] if s != first]
    for sheet in sheets:
        df = pd.read_excel(xl, sheet_name=sheet, header=None, nrows=80)
        found = _first_header_date(df)
        if expected and found and found != expected:
            continue
        for _, row in df.iterrows():
            texts = [_norm(v) for v in row if isinstance(v, str) and _to_float(v) is None]
            if not texts or not any(a in texts[0] for a in CET1_ALIASES):
                continue
            nums = [x for x in (_to_float(v) for v in row) if x is not None and 0 < abs(x) <= 30]
            return (nums[0], nums[1]) if len(nums) >= 2 else None
    return None


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
            preview = pd.read_excel(xl, sheet_name=s, header=None, nrows=80)
            # fillna first: pandas 3 keeps NaN as float through astype(str), which breaks join.
            blob = ' '.join(preview.fillna('').astype(str).values.ravel()[:400]).lower()
            if 'total income' in blob:
                sheet = s
                break
    if sheet is None:
        print(f"WARN: no P&L sheet in {Path(path).name}: {xl.sheet_names}")
        return {}
    df = pd.read_excel(xl, sheet_name=sheet, header=None)
    # If that sheet is dated another period, look for the sheet of the filename's period
    # (2014 and 2015 H1 put the 2013 FY tables first, #90). Skip the pack if there is none.
    q = _quarter_from_name(path)
    expected = f"{q[:4]}-{_PERIOD_END[q[5:]]}" if q[5:] in _PERIOD_END else None
    found = _first_header_date(df)
    if expected and found and found != expected:
        sheet = _sheet_for_period(xl, path, expected)
        if sheet is None:
            print(f"WARN: skip {Path(path).name}: header period ends {found}, filename says {expected}")
            return {}
        df = pd.read_excel(xl, sheet_name=sheet, header=None)
    label_map = {}
    header = _header_layout(df)
    layouts = ([header] if header else []) + [(1, 2, 3), (0, 1, 2)]
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
        # The 2011-12 statutory sheets print gross "total income" above the net line; the
        # net line is what every other pack of that era reports, so prefer it.
        'total_income': _first_match(label_map, ['total income net of insurance claims']) or _first_match(label_map, ['total income']),
        'operating_costs': _first_match(label_map, ['operating costs', 'operating expenses', 'total operating expenses']),
        'credit_impairment': _first_match(label_map, ['credit impairment charges', 'credit impairment', 'impairment charges']),
        'cet1_ratio': _first_match(label_map, CET1_ALIASES) or _cet1_from_summary(xl, path, expected, first=sheet),
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
            if path.name.startswith('~$'):  # Excel lock file while a pack is open
                continue
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

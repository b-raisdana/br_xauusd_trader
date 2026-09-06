from __future__ import annotations
import argparse, csv, gzip, json, math, os, sys, zipfile
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
import numpy as np

MODES = (
    'STICKY_3_CONTROL',
    'SESSION_RESET_3',
    'GAP_BOOTSTRAP_3',
    'PROGRESSIVE_123',
    'GAP_PROGRESSIVE_123',
    'GAP_PROGRESSIVE_BUFFER_0_5',
)
BUFFER_USD = 0.5


def parse_dt(s: str) -> datetime:
    s = s.strip().replace('T', ' ')
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(s)
    except Exception:
        for f in (
            '%Y.%m.%d %H:%M:%S.%f', '%Y.%m.%d %H:%M:%S',
            '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
            try:
                return datetime.strptime(s, f)
            except Exception:
                pass
    raise ValueError(s)


def find_cache() -> Path:
    base = Path(os.environ.get('LOCALAPPDATA', '')) / 'XAUUSD_PY_RESEARCH_CACHE'
    if not base.exists():
        raise RuntimeError(f'Cache base not found: {base}')
    cands = [p for p in base.glob('MetaQuotesDemo_XAUUSD_*')
             if (p / 'm15_bars_server.csv.gz').exists() and (p / 'ticks').is_dir()]
    if not cands:
        raise RuntimeError(f'No usable XAUUSD cache found under {base}')
    cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0]


def find_dataset(root: Path) -> Path:
    cands = list((root / 'evidence').glob('ZONE_EVENT_DATASET_*/ZONE_REACTION_EVENT_DATASET.csv.gz'))
    if not cands:
        cands = list(root.glob('**/ZONE_REACTION_EVENT_DATASET.csv.gz'))
    if not cands:
        raise RuntimeError('ZONE_REACTION_EVENT_DATASET.csv.gz not found under project root.')
    cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0]


def find_summary(root: Path) -> Path:
    for p in (
        root / 'reference' / 'R2_ALLFLAT_H4S15_100K_summary.csv',
        root / 'trend_reference' / 'R2_ALLFLAT_H4S15_100K_summary.csv'):
        if p.exists():
            return p
    xs = list(root.glob('**/R2_ALLFLAT_H4S15_100K_summary.csv'))
    if xs:
        return xs[0]
    raise RuntimeError('R2 ALL_FLAT summary not found.')


def load_bars(path: Path):
    rows = []
    with gzip.open(path, 'rt', encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            st = parse_dt(r['server_time']).replace(tzinfo=None)
            ut = parse_dt(r['utc_time'])
            if ut.tzinfo is None:
                ut = ut.replace(tzinfo=timezone.utc)
            rows.append(dict(
                server_time=st, utc_time=ut, utc_ms=int(ut.timestamp() * 1000),
                open=float(r['open']), high=float(r['high']), low=float(r['low']), close=float(r['close'])))
    rows.sort(key=lambda x: x['utc_ms'])
    n = len(rows)
    bar_ms = np.array([x['utc_ms'] for x in rows], dtype=np.int64)
    high = np.array([x['high'] for x in rows], dtype=float)
    low = np.array([x['low'] for x in rows], dtype=float)
    ref_hi = np.full(n, np.nan)
    ref_lo = np.full(n, np.nan)
    for i in range(3, n):
        ref_hi[i] = np.max(high[i-3:i])
        ref_lo[i] = np.min(low[i-3:i])
    day_to_indices = defaultdict(list)
    for i, b in enumerate(rows):
        day_to_indices[b['server_time'].strftime('%Y.%m.%d')].append(i)
    first = rows[0]
    server_epoch = first['server_time'].replace(tzinfo=timezone.utc).timestamp()
    utc_epoch = first['utc_time'].timestamp()
    offset_ms = int(round((server_epoch - utc_epoch) * 1000))
    return rows, bar_ms, high, low, ref_hi, ref_lo, day_to_indices, offset_ms


def progressive_refs_for_ticks(bi, day_bar_indices, high, low):
    ord_map = {g: j + 1 for j, g in enumerate(day_bar_indices)}
    pr_hi = np.full(len(bi), np.nan)
    pr_lo = np.full(len(bi), np.nan)
    ord_tick = np.zeros(len(bi), dtype=np.int16)
    for g in np.unique(bi[bi >= 0]):
        g = int(g)
        ordn = ord_map.get(g, 0)
        idx = np.where(bi == g)[0]
        ord_tick[idx] = ordn
        if ordn <= 1:
            continue
        prev = day_bar_indices[max(0, ordn - 1 - 3):ordn - 1]
        if prev:
            pr_hi[idx] = float(np.max(high[prev]))
            pr_lo[idx] = float(np.min(low[prev]))
    return pr_hi, pr_lo, ord_tick


def state_series(bid, hi, lo, initial_state: int, buffer_arr=None):
    if buffer_arr is None:
        buffer_arr = np.zeros(len(bid), dtype=float)
    raw = np.zeros(len(bid), dtype=np.int8)
    good = np.isfinite(hi) & np.isfinite(lo)
    raw[good & (bid > hi + buffer_arr)] = 1
    raw[good & (bid < lo - buffer_arr)] = -1
    last = np.maximum.accumulate(np.where(raw != 0, np.arange(len(raw), dtype=np.int64), -1))
    out = np.empty(len(raw), dtype=np.int8)
    has = last >= 0
    out[has] = raw[last[has]]
    out[~has] = initial_state
    return out


def tname(x):
    return 'UP' if int(x) == 1 else 'DOWN' if int(x) == -1 else 'NONE'


def gap_state(gap, buffer=0.0):
    if gap is None or not np.isfinite(gap) or abs(gap) <= buffer:
        return 0
    return 1 if gap > 0 else -1


def load_events(path: Path):
    rows = []
    with gzip.open(path, 'rt', encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            r['_dt'] = parse_dt(r['server_time']).replace(tzinfo=None)
            rows.append(r)
    return rows


def reversal_required_state(r):
    return 'UP' if r['approach_direction'] == 'BELOW_TO_ZONE' else 'DOWN'


def safe_float(x):
    try:
        return float(x)
    except Exception:
        return math.nan


def summarize_event_rows(rows):
    def values(k):
        a = [safe_float(r.get(k, '')) for r in rows]
        return [x for x in a if np.isfinite(x)]
    def mean(a): return float(np.mean(a)) if a else math.nan
    def med(a): return float(np.median(a)) if a else math.nan
    m3, a3 = values('mfe_reversal_3bar'), values('mae_reversal_3bar')
    m5, a5 = values('mfe_reversal_5bar'), values('mae_reversal_5bar')
    return dict(
        events=len(rows),
        mean_mfe3=mean(m3), mean_mae3=mean(a3), median_mfe3=med(m3), median_mae3=med(a3),
        mean_mfe5=mean(m5), mean_mae5=mean(a5), median_mfe5=med(m5), median_mae5=med(a5))


def load_reversal_pnl(summary: Path):
    fills, closes = {}, {}
    with summary.open('r', encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            sig, ev = r.get('signal', ''), r.get('event', '')
            try:
                ticket = int(float(r.get('position_ticket', '0') or 0))
            except Exception:
                ticket = 0
            counted = str(r.get('counted_in_pnl', '')).lower() == 'true'
            if ev == 'ORDER_FILLED' and sig in ('R-B', 'R-S') and counted and ticket:
                fills[ticket] = r
            if ev == 'POSITION_CLOSED' and counted and ticket:
                closes[ticket] = safe_float(r.get('net_pnl', '0'))
    out = []
    for t, r in fills.items():
        rr = dict(r)
        rr['_ticket'] = t
        rr['_pnl'] = closes.get(t, math.nan)
        out.append(rr)
    return out


def write_csv(path: Path, rows, fields=None):
    if fields is None:
        fields = []
        for r in rows:
            for k in r:
                if k not in fields:
                    fields.append(k)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=str(Path(__file__).resolve().parent))
    a = ap.parse_args()
    root = Path(a.root).resolve()
    cache = find_cache()
    dataset = find_dataset(root)
    summary = find_summary(root)
    outbase = root / 'evidence'
    outbase.mkdir(exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = outbase / f'TREND_INIT_SCREEN_{stamp}'
    out.mkdir(parents=True)

    events = load_events(dataset)
    bars, bar_ms, high, low, ref_hi, ref_lo, day_bars, offset_ms = load_bars(cache / 'm15_bars_server.csv.gz')
    ev_by_day = defaultdict(list)
    for i, r in enumerate(events):
        ev_by_day[r['server_day']].append((i, r))

    states = {m: {} for m in MODES}
    prior_sticky = 0
    day_meta = []
    prev_close = None

    for day in sorted(ev_by_day):
        tickfile = cache / 'ticks' / f"ticks_server_{day.replace('.', '')}.npz"
        if not tickfile.exists():
            raise RuntimeError(f'Missing tick cache: {tickfile}')
        z = np.load(tickfile, mmap_mode=None)
        tms = z['time_msc'].astype(np.int64, copy=False)
        bid = z['bid'].astype(np.float64, copy=False)
        bi = np.searchsorted(bar_ms, tms, 'right') - 1
        good = (bi >= 0) & (bi < len(bar_ms))
        hi = np.full(len(tms), np.nan)
        lo = np.full(len(tms), np.nan)
        hi[good] = ref_hi[bi[good]]
        lo[good] = ref_lo[bi[good]]

        db = day_bars.get(day, [])
        if not db:
            raise RuntimeError(f'No M15 bars for {day}')
        gap = (bars[db[0]]['open'] - prev_close) if prev_close is not None else math.nan
        pr_hi, pr_lo, ord_tick = progressive_refs_for_ticks(bi, db, high, low)

        mode_arr = {
            'STICKY_3_CONTROL': state_series(bid, hi, lo, prior_sticky),
            'SESSION_RESET_3': state_series(bid, hi, lo, 0),
            'GAP_BOOTSTRAP_3': state_series(bid, hi, lo, gap_state(gap, 0.0)),
            'PROGRESSIVE_123': state_series(bid, pr_hi, pr_lo, 0),
            'GAP_PROGRESSIVE_123': state_series(bid, pr_hi, pr_lo, gap_state(gap, 0.0)),
        }
        buf = np.where((ord_tick > 0) & (ord_tick <= 3), BUFFER_USD, 0.0)
        mode_arr['GAP_PROGRESSIVE_BUFFER_0_5'] = state_series(
            bid, pr_hi, pr_lo, gap_state(gap, BUFFER_USD), buf)

        prior_sticky = int(mode_arr['STICKY_3_CONTROL'][-1]) if len(tms) else prior_sticky
        prev_close = bars[db[-1]]['close']

        exact = 0
        for ei, r in ev_by_day[day]:
            server_ms = int(r['_dt'].replace(tzinfo=timezone.utc).timestamp() * 1000)
            utc_ms = server_ms - offset_ms
            pos = int(np.searchsorted(tms, utc_ms, 'left'))
            candidates = [q for q in (pos - 1, pos, pos + 1) if 0 <= q < len(tms)]
            if not candidates:
                continue
            k = min(candidates, key=lambda q: abs(int(tms[q]) - utc_ms))
            delta = abs(int(tms[k]) - utc_ms)
            if delta <= 1:
                exact += 1
            for m in MODES:
                states[m][ei] = tname(mode_arr[m][k])
        day_meta.append(dict(day=day, ticks=len(tms), events=len(ev_by_day[day]),
                             event_tick_exact_le_1ms=exact, opening_gap_usd=gap))

    total = matched = 0
    for i, r in enumerate(events):
        if i in states['STICKY_3_CONTROL']:
            total += 1
            if states['STICKY_3_CONTROL'][i] == r.get('live_trend', ''):
                matched += 1
    control_ratio = matched / total if total else 0.0
    if control_ratio < 0.995:
        raise RuntimeError(f'STICKY control equivalence below gate: {matched}/{total}={control_ratio:.6f}')

    control_eligible = {i for i, r in enumerate(events)
                        if states['STICKY_3_CONTROL'].get(i) == reversal_required_state(r)}

    detailed = []
    for i, r in enumerate(events):
        dr = {k: v for k, v in r.items() if k != '_dt'}
        req = reversal_required_state(r)
        for m in MODES:
            st = states[m].get(i, 'NONE')
            dr[f'trend_{m}'] = st
            dr[f'eligible_{m}'] = str(st == req).lower()
        detailed.append(dr)

    matrix = []
    for m in MODES:
        eligible_idx = {i for i, r in enumerate(events) if states[m].get(i) == reversal_required_state(r)}
        scopes = {
            'ALL': [events[i] for i in sorted(eligible_idx)],
            'OPEN_1_3': [events[i] for i in sorted(eligible_idx) if events[i].get('opening_stage') in ('OPEN_1', 'OPEN_2', 'OPEN_3')],
            'OPEN_1': [events[i] for i in sorted(eligible_idx) if events[i].get('opening_stage') == 'OPEN_1'],
            'OPEN_2': [events[i] for i in sorted(eligible_idx) if events[i].get('opening_stage') == 'OPEN_2'],
            'OPEN_3': [events[i] for i in sorted(eligible_idx) if events[i].get('opening_stage') == 'OPEN_3'],
            'STEADY': [events[i] for i in sorted(eligible_idx) if events[i].get('opening_stage') == 'STEADY'],
        }
        for scope, rr in scopes.items():
            row = dict(mode=m, scope=scope, **summarize_event_rows(rr))
            if scope == 'ALL':
                row['new_eligible_vs_control'] = len(eligible_idx - control_eligible)
                row['lost_eligible_vs_control'] = len(control_eligible - eligible_idx)
                row['overlap_with_control'] = len(eligible_idx & control_eligible)
            else:
                row['new_eligible_vs_control'] = ''
                row['lost_eligible_vs_control'] = ''
                row['overlap_with_control'] = ''
            matrix.append(row)

    # Actual realized Reversal retention screen.
    revfills = load_reversal_pnl(summary)
    event_key = {(r['server_time'], r['zone_id']): i for i, r in enumerate(events)}
    pnl_rows = []
    fill_detail = []
    for m in MODES:
        retained_n = suppressed_n = unmatched_n = 0
        retained_pnl = suppressed_pnl = 0.0
        for r in revfills:
            key = (r.get('server_time', ''), r.get('zone_id', ''))
            i = event_key.get(key)
            pnl = safe_float(r.get('_pnl', math.nan))
            if i is None:
                unmatched_n += 1
                continue
            req = 'DOWN' if r.get('signal') == 'R-B' else 'UP'
            keep = states[m].get(i, 'NONE') == req
            if keep:
                retained_n += 1
                if np.isfinite(pnl): retained_pnl += pnl
            else:
                suppressed_n += 1
                if np.isfinite(pnl): suppressed_pnl += pnl
            fill_detail.append(dict(mode=m, server_time=r.get('server_time',''), zone_id=r.get('zone_id',''),
                                    signal=r.get('signal',''), position_ticket=r.get('_ticket',''), pnl=pnl,
                                    mode_trend=states[m].get(i,'NONE'), required_trend=req, retained=str(keep).lower()))
        pnl_rows.append(dict(mode=m, actual_reversal_total=len(revfills), matched_actual_reversal=len(revfills)-unmatched_n,
                             unmatched_actual_reversal=unmatched_n, retained_n=retained_n, retained_pnl=retained_pnl,
                             suppressed_n=suppressed_n, suppressed_pnl=suppressed_pnl))

    write_csv(out / 'TREND_INIT_EVENT_MATRIX.csv', matrix)
    write_csv(out / 'TREND_INIT_DAY_COVERAGE.csv', day_meta)
    write_csv(out / 'TREND_INIT_ACTUAL_REVERSAL_RETENTION.csv', pnl_rows)
    write_csv(out / 'TREND_INIT_ACTUAL_REVERSAL_DETAIL.csv', fill_detail)
    write_csv(out / 'TREND_INIT_EVENT_STATES.csv.gz.tmp', [])  # placeholder removed below
    (out / 'TREND_INIT_EVENT_STATES.csv.gz.tmp').unlink(missing_ok=True)
    with gzip.open(out / 'TREND_INIT_EVENT_STATES.csv.gz', 'wt', encoding='utf-8-sig', newline='') as f:
        fields = list(detailed[0].keys()) if detailed else []
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader(); w.writerows(detailed)

    gate_text = (
        'TREND_INIT_SCREEN_GATE=PASS\n'
        f'STICKY_CONTROL_MATCH={matched}/{total}\n'
        f'STICKY_CONTROL_MATCH_RATIO={control_ratio:.6f}\n'
        f'EVENT_ROWS={len(events)}\n'
        f'ACTUAL_REVERSAL_FILLS={len(revfills)}\n'
        f'SERVER_UTC_OFFSET_HOURS={offset_ms/3600000:+.2f}\n'
        f'BUFFERED_BOOTSTRAP_USD={BUFFER_USD:.2f}\n'
        'NOTE=Screen only; no trading-rule promotion. Actual-PnL table is static retention, not causal challenger replay.\n')
    (out / 'TREND_INIT_GATE.txt').write_text(gate_text, encoding='utf-8')
    meta = dict(cache_dir=str(cache), dataset=str(dataset), summary=str(summary), python=sys.version,
                numpy=np.__version__, modes=list(MODES), buffer_usd=BUFFER_USD)
    (out / 'TREND_INIT_META.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')

    zip_path = outbase / f'{out.name}.zip'
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(out.iterdir()):
            zf.write(p, arcname=p.name)
    print(gate_text.strip())
    print(f'EVIDENCE_ZIP={zip_path}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f'ERROR: {e}', file=sys.stderr)
        raise

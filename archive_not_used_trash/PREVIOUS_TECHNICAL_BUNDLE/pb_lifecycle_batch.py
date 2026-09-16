from __future__ import annotations

import csv
import gzip
import json
import math
import os
import re
import sys
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

MERGE_GAP = 1.5
PENETRATION = 0.20
R_CAP = 6.0
CUT_MINUTES = 5
BASELINE_TRADES = 288
BASELINE_PNL = 30.01
BASELINE_PF = 1.034
FIXED_REGRESSION = {3: (268, 53.50), 5: (288, 30.01), 7: (301, -15.18), 9: (310, -26.49)}


@dataclass
class Zone:
    day: str
    id: str
    low: float
    high: float
    priority: str
    index: int


@dataclass
class Cycle:
    day: str
    zone_id: str
    buy: bool
    parent_id: str
    valid_bar_no: int = 1
    penetration: bool = False
    pending: bool = False
    requested: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    r0: float = 0.0


@dataclass
class Position:
    day: str
    zone_id: str
    buy: bool
    parent_id: str
    age: int
    use_ordinal: int
    priority: str
    requested: float
    fill: float
    sl: float
    tp: float
    r0: float
    entry_ms: int
    stage: int = 0
    mfe: float = 0.0
    mae: float = 0.0


def parse_dt(s: str) -> datetime:
    s = str(s).strip().replace("T", " ")
    for f in ("%Y.%m.%d %H:%M:%S.%f", "%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, f)
        except:
            pass
    try:
        return datetime.fromisoformat(s)
    except:
        raise ValueError(s)


def pf_of(vals):
    vals = np.asarray(vals, dtype=float)
    w = float(vals[vals > 0].sum()) if len(vals) else 0.0
    l = float(-vals[vals < 0].sum()) if len(vals) else 0.0
    return (w / l) if l > 0 else (math.inf if w > 0 else math.nan)


def load_ranges(path: Path):
    raw = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if str(r.get("enabled", "true")).strip().lower() in ("false", "0", "no", "off"):
                continue
            try:
                lo = float(r["lower"])
                hi = float(r["upper"])
            except:
                continue
            if lo <= 0 or hi <= 0:
                continue
            p = str(r.get("priority", "normal")).strip().lower()
            if p not in ("high", "normal"):
                continue
            raw[str(r["date"]).strip()].append((min(lo, hi), max(lo, hi), p))
    out = {}
    for day, arr in raw.items():
        arr = sorted(arr)
        pre = [[lo, hi, p, f"R{i}"] for i, (lo, hi, p) in enumerate(arr, 1)]
        merged = []
        for lo, hi, p, zid in pre:
            if not merged:
                merged.append([lo, hi, p, zid])
                continue
            if lo - merged[-1][1] < MERGE_GAP:
                merged[-1][1] = max(merged[-1][1], hi)
                if p == "high":
                    merged[-1][2] = "high"
                merged[-1][3] += "&" + zid
            else:
                merged.append([lo, hi, p, zid])
        out[day] = [Zone(day, zid, lo, hi, p, i) for i, (lo, hi, p, zid) in enumerate(merged)]
    return out


def load_summary(path: Path):
    rows = []
    schedules = {}
    actual_pb = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                r["_dt"] = parse_dt(r["server_time"])
            except:
                continue
            rows.append(r)
            if r.get("event") == "SESSION_SCHEDULE":
                m = re.search(r"day=([A-Z]+).*?raw_from=(\d\d:\d\d:\d\d).*?raw_to=(\d\d:\d\d:\d\d)", r.get("note", ""))
                if m:
                    schedules[m.group(1)] = (m.group(2), m.group(3))
    closes = {}
    for r in rows:
        if r.get("event") == "POSITION_CLOSED" and str(r.get("signal", "")).startswith("PB-"):
            try:
                closes[int(float(r.get("position_ticket") or 0))] = float(r.get("net_pnl") or 0)
            except:
                pass
    for r in rows:
        if r.get("event") == "ORDER_FILLED" and str(r.get("signal", "")).startswith("PB-"):
            try:
                t = int(float(r.get("position_ticket") or 0))
            except:
                t = 0
            actual_pb.append(
                dict(
                    day=r["_dt"].strftime("%Y.%m.%d"),
                    zone_id=r["zone_id"],
                    signal=r["signal"],
                    parent_id=r.get("parent_breakout_id", ""),
                    pnl=closes.get(t, 0.0),
                    fill_time=r["_dt"],
                )
            )
    return rows, schedules, actual_pb


def load_bars(path: Path):
    rows = []
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            st = parse_dt(r["server_time"]).replace(tzinfo=None)
            ut = parse_dt(r["utc_time"])
            if ut.tzinfo is None:
                ut = ut.replace(tzinfo=timezone.utc)
            rows.append(
                (st, int(ut.timestamp() * 1000), float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]))
            )
    rows.sort(key=lambda x: x[1])
    st = [r[0] for r in rows]
    ms = np.array([r[1] for r in rows], dtype=np.int64)
    op = np.array([r[2] for r in rows], dtype=float)
    hi = np.array([r[3] for r in rows], dtype=float)
    lo = np.array([r[4] for r in rows], dtype=float)
    cl = np.array([r[5] for r in rows], dtype=float)
    server_epoch = st[0].replace(tzinfo=timezone.utc).timestamp() * 1000
    offset_ms = int(round(server_epoch - ms[0]))
    return st, ms, op, hi, lo, cl, offset_ms


def precompute_structure(hi, lo):
    n = len(hi)
    buy = np.full(n, np.nan)
    sell = np.full(n, np.nan)
    swing_lo = np.zeros(n, dtype=bool)
    swing_hi = np.zeros(n, dtype=bool)
    if n >= 3:
        swing_lo[1:-1] = (lo[1:-1] < lo[:-2]) & (lo[1:-1] < lo[2:])
        swing_hi[1:-1] = (hi[1:-1] > hi[:-2]) & (hi[1:-1] > hi[2:])
    lows = []
    highs = []
    for j in range(n):
        k = j - 2
        if k >= 1:
            if swing_lo[k]:
                lows.append(k)
            if swing_hi[k]:
                highs.append(k)
        if len(lows) >= 2:
            a, b = lows[-1], lows[-2]
            if lo[a] > lo[b]:
                buy[j] = lo[a]
        if len(highs) >= 2:
            a, b = highs[-1], highs[-2]
            if hi[a] < hi[b]:
                sell[j] = hi[a]
    return buy, sell


def discover_cache(root: Path):
    explicit = os.environ.get("XAUUSD_PY_RESEARCH_CACHE_DIR")
    cands = []
    if explicit:
        cands.append(Path(explicit))
    env = os.environ.get("LOCALAPPDATA")
    if env:
        base = Path(env) / "XAUUSD_PY_RESEARCH_CACHE"
        if base.exists():
            cands += [p for p in base.iterdir() if p.is_dir()]
    if (root / "cache").is_dir():
        cands.append(root / "cache")
    good = []
    for p in cands:
        if (p / "m15_bars_server.csv.gz").exists() and (p / "ticks").is_dir():
            good.append(p)
    if not good:
        raise RuntimeError(
            "No valid XAUUSD_PY_RESEARCH_CACHE found. Do not redownload; reuse the existing local cache."
        )
    good.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return good[0]


def weekday_name(dt):
    return dt.strftime("%A").upper()


def sec(s):
    h, m, x = map(int, s.split(":"))
    return h * 3600 + m * 60 + x


def risk_model(zones, zi, buy, entry):
    if buy:
        if zi <= 0:
            return None
        sl = max(zones[zi - 1].high, entry - R_CAP)
        r0 = entry - sl
        if r0 <= 0:
            return None
        tp = None
        for j in range(zi + 1, len(zones)):
            if zones[j].low - entry >= r0 - 1e-9:
                tp = zones[j].low
                break
    else:
        if zi + 1 >= len(zones):
            return None
        sl = min(zones[zi + 1].low, entry + R_CAP)
        r0 = sl - entry
        if r0 <= 0:
            return None
        tp = None
        for j in range(zi - 1, -1, -1):
            if entry - zones[j].high >= r0 - 1e-9:
                tp = zones[j].high
                break
    if tp is None:
        return None
    return float(sl), float(tp), float(r0)


def scenario_cap(zone, normal_cap, high_cap):
    cap = high_cap if zone.priority == "high" else normal_cap
    return None if cap is None else int(cap)


def simulate(
    name,
    mode,
    nmax,
    normal_cap,
    high_cap,
    zones_by_day,
    breakouts_by_day,
    cache,
    bar_ms,
    hi,
    lo,
    close,
    offset_ms,
    schedules,
):
    buy_struct, sell_struct = precompute_structure(hi, lo)
    trades = []
    rejected = 0
    missing_days = []
    invalidated = 0
    reuse_blocked = 0
    expired = 0
    for day in sorted(zones_by_day):
        tf = cache / "ticks" / f"ticks_server_{day.replace('.', '')}.npz"
        if not tf.exists():
            missing_days.append(day)
            continue
        dat = np.load(tf, mmap_mode=None)
        tms = dat["time_msc"].astype(np.int64, copy=False)
        bid = dat["bid"].astype(float, copy=False)
        ask = dat["ask"].astype(float, copy=False)
        if len(tms) == 0:
            continue
        zs = zones_by_day[day]
        zmap = {z.id: i for i, z in enumerate(zs)}
        cycles = {}
        positions = []
        use_count = defaultdict(int)
        bos = breakouts_by_day.get(day, [])
        bp = 0
        last_bi = None
        session_done = False
        sample_server = datetime.fromtimestamp((int(tms[0]) + offset_ms) / 1000, tz=timezone.utc).replace(tzinfo=None)
        sch = schedules.get(weekday_name(sample_server), ("00:00:00", "23:00:00"))
        cutoff_sec = sec(sch[1]) - CUT_MINUTES * 60
        for k in range(len(tms)):
            tm = int(tms[k])
            b = float(bid[k])
            aask = float(ask[k])
            server_dt = datetime.fromtimestamp((tm + offset_ms) / 1000, tz=timezone.utc).replace(tzinfo=None)
            ssec = server_dt.hour * 3600 + server_dt.minute * 60 + server_dt.second
            bi = int(np.searchsorted(bar_ms, tm, "right") - 1)
            if bi < 0:
                continue
            if last_bi is None:
                last_bi = bi
            elif bi > last_bi:
                for new_bi in range(last_bi + 1, bi + 1):
                    completed = new_bi - 1
                    dead = []
                    for key, c in list(cycles.items()):
                        zi = zmap.get(c.zone_id)
                        if zi is None:
                            dead.append(key)
                            continue
                        z = zs[zi]
                        if mode == "structure" and completed >= 0:
                            cclose = float(close[completed])
                            bad = (cclose < z.low - 1e-12) if c.buy else (cclose > z.high + 1e-12)
                            if bad:
                                dead.append(key)
                                invalidated += 1
                                continue
                        if c.valid_bar_no >= nmax:
                            dead.append(key)
                            expired += 1
                        else:
                            c.valid_bar_no += 1
                    for key in dead:
                        cycles.pop(key, None)
                last_bi = bi
            if ssec >= cutoff_sec:
                if not session_done:
                    cycles.clear()
                    for p in positions:
                        px = b if p.buy else aask
                        fav = (b - p.fill) if p.buy else (p.fill - aask)
                        adv = (p.fill - b) if p.buy else (aask - p.fill)
                        p.mfe = max(p.mfe, fav)
                        p.mae = max(p.mae, adv)
                        pnl = (px - p.fill) if p.buy else (p.fill - px)
                        trades.append((p, px, pnl, "ALL_FLAT"))
                    positions = []
                    session_done = True
                continue
            survivors = []
            for p in positions:
                fav = (b - p.fill) if p.buy else (p.fill - aask)
                adv = (p.fill - b) if p.buy else (aask - p.fill)
                p.mfe = max(p.mfe, fav)
                p.mae = max(p.mae, adv)
                close_px = None
                reason = ""
                if p.buy:
                    if b <= p.sl:
                        close_px = b
                        reason = "SL"
                    elif b >= p.tp:
                        close_px = b
                        reason = "TP"
                else:
                    if aask >= p.sl:
                        close_px = aask
                        reason = "SL"
                    elif aask <= p.tp:
                        close_px = aask
                        reason = "TP"
                if close_px is not None:
                    pnl = (close_px - p.fill) if p.buy else (p.fill - close_px)
                    trades.append((p, close_px, pnl, reason))
                else:
                    survivors.append(p)
            positions = survivors
            fill_keys = []
            for key, c in list(cycles.items()):
                if not c.pending:
                    continue
                zi = zmap.get(c.zone_id)
                if zi is None:
                    fill_keys.append(key)
                    continue
                z = zs[zi]
                cap = scenario_cap(z, normal_cap, high_cap)
                if cap is not None and use_count[c.zone_id] >= cap:
                    fill_keys.append(key)
                    reuse_blocked += 1
                    continue
                trig = (aask >= c.requested) if c.buy else (b <= c.requested)
                if trig:
                    fill = aask if c.buy else b
                    use_count[c.zone_id] += 1
                    positions.append(
                        Position(
                            c.day,
                            c.zone_id,
                            c.buy,
                            c.parent_id,
                            c.valid_bar_no,
                            use_count[c.zone_id],
                            z.priority,
                            c.requested,
                            fill,
                            c.sl,
                            c.tp,
                            c.r0,
                            tm,
                        )
                    )
                    fill_keys.append(key)
            for key in fill_keys:
                cycles.pop(key, None)
            # If a fill reached a daily zone cap, cancel any other unfilled cycles for that zone.
            for zid, count in list(use_count.items()):
                zi = zmap.get(zid)
                if zi is None:
                    continue
                cap = scenario_cap(zs[zi], normal_cap, high_cap)
                if cap is not None and count >= cap:
                    for key, c in list(cycles.items()):
                        if c.zone_id == zid:
                            cycles.pop(key, None)
                            reuse_blocked += 1
            while bp < len(bos) and bos[bp]["utc_ms"] <= tm:
                bo = bos[bp]
                bp += 1
                if bo["zone_id"] not in zmap:
                    continue
                z = zs[zmap[bo["zone_id"]]]
                cap = scenario_cap(z, normal_cap, high_cap)
                if cap is not None and use_count[bo["zone_id"]] >= cap:
                    reuse_blocked += 1
                    continue
                key = (bo["zone_id"], bo["buy"])
                if key in cycles:
                    continue
                cycles[key] = Cycle(day, bo["zone_id"], bo["buy"], bo["id"])
            for key, c in list(cycles.items()):
                zi = zmap.get(c.zone_id)
                if zi is None:
                    continue
                z = zs[zi]
                cap = scenario_cap(z, normal_cap, high_cap)
                if cap is not None and use_count[c.zone_id] >= cap:
                    cycles.pop(key, None)
                    reuse_blocked += 1
                    continue
                if not c.penetration:
                    pen = (b <= z.high - PENETRATION) if c.buy else (b >= z.low + PENETRATION)
                    if pen:
                        c.penetration = True
                if c.penetration and not c.pending:
                    req = z.high if c.buy else z.low
                    can = (req > aask) if c.buy else (req < b)
                    if not can:
                        continue
                    rm = risk_model(zs, zi, c.buy, req)
                    if rm is None:
                        cycles.pop(key, None)
                        rejected += 1
                        continue
                    c.requested = req
                    c.sl, c.tp, c.r0 = rm
                    c.pending = True
            for p in positions:
                favorable = (b - p.requested) if p.buy else (p.requested - aask)
                if favorable < 0:
                    favorable = 0.0
                if p.stage < 1 and favorable >= p.r0:
                    p.stage = 1
                if p.stage < 2 and favorable >= 1.5 * p.r0:
                    p.stage = 2
                if p.stage < 3 and favorable >= 2.0 * p.r0:
                    p.stage = 3
                desired = None
                if p.stage >= 3 and bi < len(buy_struct):
                    piv = buy_struct[bi] if p.buy else sell_struct[bi]
                    if np.isfinite(piv):
                        improves = (piv > p.sl + 1e-9) if p.buy else (piv < p.sl - 1e-9)
                        valid = (piv < b) if p.buy else (piv > aask)
                        if improves and valid:
                            desired = float(piv)
                if desired is None and p.stage >= 2:
                    d = p.requested + (0.5 * p.r0 if p.buy else -0.5 * p.r0)
                    improves = (d > p.sl + 1e-9) if p.buy else (d < p.sl - 1e-9)
                    valid = (d < b) if p.buy else (d > aask)
                    if improves and valid:
                        desired = float(d)
                if desired is None and p.stage >= 1:
                    d = p.fill
                    improves = (d > p.sl + 1e-9) if p.buy else (d < p.sl - 1e-9)
                    valid = (d < b) if p.buy else (d > aask)
                    if improves and valid:
                        desired = float(d)
                if desired is not None:
                    p.sl = desired
        if positions:
            b = float(bid[-1])
            aask = float(ask[-1])
            for p in positions:
                px = b if p.buy else aask
                pnl = (px - p.fill) if p.buy else (p.fill - px)
                trades.append((p, px, pnl, "DAY_END_FALLBACK"))
    out = []
    for p, exit_px, pnl, reason in trades:
        out.append(
            dict(
                scenario=name,
                mode=mode,
                nmax=nmax,
                normal_cap=("unlimited" if normal_cap is None else normal_cap),
                high_cap=("unlimited" if high_cap is None else high_cap),
                day=p.day,
                zone_id=p.zone_id,
                priority=p.priority,
                signal="PB-B" if p.buy else "PB-S",
                parent_breakout_id=p.parent_id,
                age=p.age,
                use_ordinal=p.use_ordinal,
                requested=p.requested,
                fill=p.fill,
                exit=exit_px,
                tp=p.tp,
                r0=p.r0,
                pnl=pnl,
                mfe=max(0, p.mfe),
                mae=max(0, p.mae),
                close_reason=reason,
            )
        )
    return out, dict(
        rejected_c1=rejected,
        structure_invalidated=invalidated,
        reuse_blocked=reuse_blocked,
        expired=expired,
        missing_tick_days="|".join(missing_days),
    )


def write_csv(path, rows):
    keys = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main():
    root = Path(__file__).resolve().parent
    ref = root / "pb_lifecycle_reference"
    summary = ref / "R2_ALLFLAT_H4S15_100K_summary.csv"
    ranges = ref / "ranges.csv"
    if not summary.exists() or not ranges.exists():
        raise RuntimeError("Self-contained reference files are missing from the patch.")
    print(f"SCRIPT_DIR={root}")
    print(f"REFERENCE_DIR={ref}")
    cache = discover_cache(root)
    bar_st, bar_ms, op, hi, lo, close, offset_ms = load_bars(cache / "m15_bars_server.csv.gz")
    rows, schedules, actual = load_summary(summary)
    zones = load_ranges(ranges)
    raw_bos = defaultdict(list)
    for r in rows:
        if r.get("event") != "BREAKOUT_SIGNAL" or r.get("signal") not in ("BO-B", "BO-S"):
            continue
        d = r["_dt"].strftime("%Y.%m.%d")
        utc_ms = int(r["_dt"].replace(tzinfo=timezone.utc).timestamp() * 1000) - offset_ms
        raw_bos[d].append(
            dict(
                utc_ms=utc_ms, zone_id=r.get("zone_id", ""), buy=r.get("signal") == "BO-B", id=r.get("breakout_id", "")
            )
        )
    bos = defaultdict(list)
    day_boundary_ignored = []
    for d, items in raw_bos.items():
        items.sort(key=lambda x: x["utc_ms"])
        first_reset = next((i for i, x in enumerate(items) if x["id"] == "BO#01"), None)
        if first_reset is None:
            day_boundary_ignored.extend((d, x["zone_id"], x["id"]) for x in items)
            continue
        if first_reset > 0:
            day_boundary_ignored.extend((d, x["zone_id"], x["id"]) for x in items[:first_reset])
        bos[d] = items[first_reset:]
    days = sorted(zones)
    train = set(days[:15])
    forward = set(days[15:])
    scenarios = []
    for n in (3, 5, 7, 9):
        scenarios.append((f"FIXED_N{n}_UNLIMITED", "fixed", n, None, None))
    for n in (3, 5, 7, 9):
        scenarios.append((f"STRUCT_NMAX{n}_UNLIMITED", "structure", n, None, None))
    for n in (3, 5):
        for nc in (1, 2):
            for hc in (2, 3, None):
                hs = "INF" if hc is None else str(hc)
                scenarios.append((f"FIXED_N{n}_NORM{nc}_HIGH{hs}", "fixed", n, nc, hc))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = root / "evidence" / f"PB_LIFECYCLE_BATCH_{stamp}"
    outdir.mkdir(parents=True, exist_ok=True)
    alltr = []
    diag = []
    for name, mode, nmax, nc, hc in scenarios:
        tr, dg = simulate(name, mode, nmax, nc, hc, zones, bos, cache, bar_ms, hi, lo, close, offset_ms, schedules)
        alltr.extend(tr)
        diag.append(
            dict(
                scenario=name,
                mode=mode,
                nmax=nmax,
                normal_cap=("unlimited" if nc is None else nc),
                high_cap=("unlimited" if hc is None else hc),
                day_boundary_breakouts_ignored=len(day_boundary_ignored),
                **dg,
            )
        )
    matrix = []
    for name, mode, nmax, nc, hc in scenarios:
        d = [x for x in alltr if x["scenario"] == name]
        for scope, ds in [("TRAIN", train), ("FORWARD", forward), ("ALL", set(days))]:
            g = [x for x in d if x["day"] in ds]
            p = [x["pnl"] for x in g]
            matrix.append(
                dict(
                    scenario=name,
                    mode=mode,
                    nmax=nmax,
                    normal_cap=("unlimited" if nc is None else nc),
                    high_cap=("unlimited" if hc is None else hc),
                    scope=scope,
                    trades=len(g),
                    net_pnl=sum(p),
                    pf=pf_of(p),
                    expectancy=(sum(p) / len(g) if g else math.nan),
                    mean_mfe=(sum(x["mfe"] for x in g) / len(g) if g else math.nan),
                    mean_mae=(sum(x["mae"] for x in g) / len(g) if g else math.nan),
                )
            )
    ordrows = []
    for name, _, _, _, _ in scenarios:
        d = [x for x in alltr if x["scenario"] == name]
        for pr in ("normal", "high"):
            vals = [x for x in d if x["priority"] == pr]
            if not vals:
                continue
            for o in sorted(set(x["use_ordinal"] for x in vals)):
                g = [x for x in vals if x["use_ordinal"] == o]
                p = [x["pnl"] for x in g]
                ordrows.append(
                    dict(
                        scenario=name,
                        priority=pr,
                        use_ordinal=o,
                        trades=len(g),
                        net_pnl=sum(p),
                        pf=pf_of(p),
                        expectancy=sum(p) / len(g),
                    )
                )
    # Hard equivalence and fixed-window regression gate.
    control = [x for x in alltr if x["scenario"] == "FIXED_N5_UNLIMITED"]
    actual_keys = {(x["day"], x["zone_id"], x["signal"], x["parent_id"]) for x in actual}
    sim_keys = {(x["day"], x["zone_id"], x["signal"], x["parent_breakout_id"]) for x in control}
    inter = len(actual_keys & sim_keys)
    ratio = inter / max(1, len(actual_keys))
    cpnl = sum(x["pnl"] for x in control)
    cpf = pf_of([x["pnl"] for x in control])
    gate = (
        len(control) == BASELINE_TRADES
        and ratio >= 0.999
        and abs(cpnl - BASELINE_PNL) <= 0.05
        and math.isfinite(cpf)
        and abs(cpf - BASELINE_PF) <= 0.005
    )
    regress = []
    for n, (etr, epnl) in FIXED_REGRESSION.items():
        g = [x for x in alltr if x["scenario"] == f"FIXED_N{n}_UNLIMITED"]
        got = (len(g), sum(x["pnl"] for x in g))
        ok = got[0] == etr and abs(got[1] - epnl) <= 0.05
        regress.append(
            dict(window=n, expected_trades=etr, actual_trades=got[0], expected_pnl=epnl, actual_pnl=got[1], pass_=ok)
        )
        gate = gate and ok
    write_csv(outdir / "PB_LIFECYCLE_BATCH_MATRIX.csv", matrix)
    write_csv(outdir / "PB_LIFECYCLE_BATCH_TRADES.csv", alltr)
    write_csv(outdir / "PB_LIFECYCLE_BATCH_DIAGNOSTICS.csv", diag)
    write_csv(outdir / "PB_LIFECYCLE_REUSE_ORDINAL.csv", ordrows)
    write_csv(outdir / "PB_LIFECYCLE_FIXED_REGRESSION.csv", regress)
    lines = [
        f"PB_LIFECYCLE_BATCH_GATE={'PASS' if gate else 'FAIL'}",
        f"N5_ACTUAL_KEY_MATCH={inter}/{len(actual_keys)}",
        f"N5_MATCH_RATIO={ratio:.6f}",
        f"N5_TRADES={len(control)}",
        f"N5_PNL={cpnl:.2f}",
        f"N5_PF={cpf:.6f}",
        f"DAY_BOUNDARY_BREAKOUTS_IGNORED={len(day_boundary_ignored)}",
        f"SCENARIOS={len(scenarios)}",
        f"CACHE_DIR={cache}",
        f"SERVER_UTC_OFFSET_HOURS={offset_ms / 3600000:+.2f}",
        "SCOPE1=Fixed N3/N5/N7/N9 regression control.",
        "SCOPE2=Structure-valid PB cycle: completed M15 close beyond broken Zone far edge invalidates cycle; Nmax is safety ceiling.",
        "SCOPE3=Reuse: max PB fills per Zone/day across directions; once cap is reached, remaining unfilled cycles on that Zone are cancelled. Normal 1/2 x High 2/3/unlimited, tested under N3 and N5.",
        "NOTE=No rule promotion. PB-only branch replay; finalists still require combined MT5 Every Tick Based on Real Ticks validation.",
    ]
    (outdir / "PB_LIFECYCLE_BATCH_GATE.txt").write_text("\n".join(lines), encoding="utf-8")
    (outdir / "PB_LIFECYCLE_BATCH_META.json").write_text(
        json.dumps(
            dict(
                python=sys.version,
                numpy=np.__version__,
                cache=str(cache),
                train_days=sorted(train),
                forward_days=sorted(forward),
                scenarios=[x[0] for x in scenarios],
                day_boundary_ignored=day_boundary_ignored,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    zpath = root / "evidence" / f"PB_LIFECYCLE_BATCH_{stamp}.zip"
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(outdir.iterdir()):
            z.write(p, p.name)
    print("\n".join(lines))
    print(f"EVIDENCE_ZIP={zpath}")
    if not gate:
        print("BATCH VALIDATION FAILED: send the evidence ZIP. Do not rerun MT5 or redownload ticks.")
        return 2
    print("BATCH_RANKING_READY=YES")
    # concise forward output for the user console
    for r in matrix:
        if r["scope"] == "FORWARD" and (r["scenario"].startswith("STRUCT_") or ("NORM" in r["scenario"])):
            print(
                f"{r['scenario']} FORWARD trades={r['trades']} pnl={r['net_pnl']:.2f} pf={r['pf']:.3f} exp={r['expectancy']:.3f}"
            )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise

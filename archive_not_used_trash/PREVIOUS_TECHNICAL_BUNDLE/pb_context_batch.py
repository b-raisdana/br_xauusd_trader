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
BASELINE_PF = 1.0339633318243346
N3_TRADES = 268
N3_PNL = 53.50
REUSE_N5_N1_HINF_TRADES = 134
REUSE_N5_N1_HINF_PNL = 36.27
REUSE_N5_N2_HINF_TRADES = 199
REUSE_N5_N2_HINF_PNL = 66.46


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
    bo_free_space: float = math.nan
    bo_mtr20: float = math.nan
    bo_space_score: float = math.nan
    bo_hour: int = -1


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
    bo_free_space: float = math.nan
    bo_mtr20: float = math.nan
    bo_space_score: float = math.nan
    bo_hour: int = -1
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
    vals = np.asarray(list(vals), dtype=float)
    if len(vals) == 0:
        return math.nan
    w = float(vals[vals > 0].sum())
    l = float(-vals[vals < 0].sum())
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
    op = np.array([r[2] for r in rows])
    hi = np.array([r[3] for r in rows])
    lo = np.array([r[4] for r in rows])
    cl = np.array([r[5] for r in rows])
    server_epoch = st[0].replace(tzinfo=timezone.utc).timestamp() * 1000
    offset_ms = int(round(server_epoch - ms[0]))
    tr = np.empty(len(hi), dtype=float)
    tr[0] = hi[0] - lo[0]
    if len(hi) > 1:
        pc = cl[:-1]
        tr[1:] = np.maximum(hi[1:] - lo[1:], np.maximum(np.abs(hi[1:] - pc), np.abs(lo[1:] - pc)))
    mtr20 = np.full(len(tr), np.nan)
    for i in range(20, len(tr) + 1):
        # value for a new bar at index i uses the previous 20 completed bars [i-20, i)
        if i < len(tr):
            mtr20[i] = float(np.median(tr[i - 20 : i]))
    return st, ms, op, hi, lo, cl, mtr20, offset_ms


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
    cands = []
    explicit = os.environ.get("XAUUSD_PY_RESEARCH_CACHE_DIR")
    if explicit:
        cands.append(Path(explicit))
    env = os.environ.get("LOCALAPPDATA")
    if env:
        base = Path(env) / "XAUUSD_PY_RESEARCH_CACHE"
        if base.exists():
            cands += [p for p in base.iterdir() if p.is_dir()]
    if (root / "cache").is_dir():
        cands.append(root / "cache")
    good = [p for p in cands if (p / "m15_bars_server.csv.gz").exists() and (p / "ticks").is_dir()]
    if not good:
        raise RuntimeError(
            "No valid XAUUSD_PY_RESEARCH_CACHE found. Reuse the existing cache; do not redownload ticks."
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


def directional_space(zs, zi, buy):
    if buy:
        if zi + 1 >= len(zs):
            return math.inf
        return max(0.0, float(zs[zi + 1].low - zs[zi].high))
    if zi <= 0:
        return math.inf
    return max(0.0, float(zs[zi].low - zs[zi - 1].high))


def simulate_fixed(nmax, zones_by_day, breakouts_by_day, cache, bar_ms, hi, lo, close, mtr20, offset_ms, schedules):
    buy_struct, sell_struct = precompute_structure(hi, lo)
    trades = []
    missing = []
    for day in sorted(zones_by_day):
        tf = cache / "ticks" / f"ticks_server_{day.replace('.', '')}.npz"
        if not tf.exists():
            missing.append(day)
            continue
        dat = np.load(tf)
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
        cutoff_sec = sec(schedules.get(weekday_name(sample_server), ("00:00:00", "23:00:00"))[1]) - CUT_MINUTES * 60
        for k in range(len(tms)):
            tm = int(tms[k])
            b = float(bid[k])
            aa = float(ask[k])
            server_dt = datetime.fromtimestamp((tm + offset_ms) / 1000, tz=timezone.utc).replace(tzinfo=None)
            ssec = server_dt.hour * 3600 + server_dt.minute * 60 + server_dt.second
            bi = int(np.searchsorted(bar_ms, tm, "right") - 1)
            if bi < 0:
                continue
            if last_bi is None:
                last_bi = bi
            elif bi > last_bi:
                for _new in range(last_bi + 1, bi + 1):
                    dead = []
                    for key, c in cycles.items():
                        if c.valid_bar_no >= nmax:
                            dead.append(key)
                        else:
                            c.valid_bar_no += 1
                    for key in dead:
                        cycles.pop(key, None)
                last_bi = bi
            if ssec >= cutoff_sec:
                if not session_done:
                    cycles.clear()
                    for p in positions:
                        px = b if p.buy else aa
                        fav = (b - p.fill) if p.buy else (p.fill - aa)
                        adv = (p.fill - b) if p.buy else (aa - p.fill)
                        p.mfe = max(p.mfe, fav)
                        p.mae = max(p.mae, adv)
                        pnl = (px - p.fill) if p.buy else (p.fill - px)
                        trades.append((p, px, pnl, "ALL_FLAT"))
                    positions = []
                    session_done = True
                continue
            survivors = []
            for p in positions:
                fav = (b - p.fill) if p.buy else (p.fill - aa)
                adv = (p.fill - b) if p.buy else (aa - p.fill)
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
                    if aa >= p.sl:
                        close_px = aa
                        reason = "SL"
                    elif aa <= p.tp:
                        close_px = aa
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
                trig = (aa >= c.requested) if c.buy else (b <= c.requested)
                if trig:
                    zi = zmap[c.zone_id]
                    z = zs[zi]
                    fill = aa if c.buy else b
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
                            c.bo_free_space,
                            c.bo_mtr20,
                            c.bo_space_score,
                            c.bo_hour,
                        )
                    )
                    fill_keys.append(key)
            for key in fill_keys:
                cycles.pop(key, None)
            while bp < len(bos) and bos[bp]["utc_ms"] <= tm:
                bo = bos[bp]
                bp += 1
                if bo["zone_id"] not in zmap:
                    continue
                key = (bo["zone_id"], bo["buy"])
                if key in cycles:
                    continue
                zi = zmap[bo["zone_id"]]
                fs = directional_space(zs, zi, bo["buy"])
                mbi = int(np.searchsorted(bar_ms, bo["utc_ms"], "right") - 1)
                mv = float(mtr20[mbi]) if 0 <= mbi < len(mtr20) and np.isfinite(mtr20[mbi]) else math.nan
                score = (
                    (fs / mv)
                    if np.isfinite(fs) and np.isfinite(mv) and mv > 0
                    else (math.inf if math.isinf(fs) else math.nan)
                )
                bo_server = datetime.fromtimestamp((bo["utc_ms"] + offset_ms) / 1000, tz=timezone.utc).replace(
                    tzinfo=None
                )
                cycles[key] = Cycle(
                    day,
                    bo["zone_id"],
                    bo["buy"],
                    bo["id"],
                    bo_free_space=fs,
                    bo_mtr20=mv,
                    bo_space_score=score,
                    bo_hour=bo_server.hour,
                )
            for key, c in list(cycles.items()):
                zi = zmap.get(c.zone_id)
                if zi is None:
                    continue
                z = zs[zi]
                if not c.penetration:
                    if (b <= z.high - PENETRATION) if c.buy else (b >= z.low + PENETRATION):
                        c.penetration = True
                if c.penetration and not c.pending:
                    req = z.high if c.buy else z.low
                    can = (req > aa) if c.buy else (req < b)
                    if not can:
                        continue
                    rm = risk_model(zs, zi, c.buy, req)
                    if rm is None:
                        cycles.pop(key, None)
                        continue
                    c.requested = req
                    c.sl, c.tp, c.r0 = rm
                    c.pending = True
            for p in positions:
                favorable = (b - p.requested) if p.buy else (p.requested - aa)
                favorable = max(0.0, favorable)
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
                        valid = (piv < b) if p.buy else (piv > aa)
                        if improves and valid:
                            desired = float(piv)
                if desired is None and p.stage >= 2:
                    d = p.requested + (0.5 * p.r0 if p.buy else -0.5 * p.r0)
                    improves = (d > p.sl + 1e-9) if p.buy else (d < p.sl - 1e-9)
                    valid = (d < b) if p.buy else (d > aa)
                    if improves and valid:
                        desired = float(d)
                if desired is None and p.stage >= 1:
                    d = p.fill
                    improves = (d > p.sl + 1e-9) if p.buy else (d < p.sl - 1e-9)
                    valid = (d < b) if p.buy else (d > aa)
                    if improves and valid:
                        desired = float(d)
                if desired is not None:
                    p.sl = desired
        if positions:
            b = float(bid[-1])
            aa = float(ask[-1])
            for p in positions:
                px = b if p.buy else aa
                pnl = (px - p.fill) if p.buy else (p.fill - px)
                trades.append((p, px, pnl, "DAY_END_FALLBACK"))
    out = []
    for p, exit_px, pnl, reason in trades:
        out.append(
            dict(
                base=f"N{nmax}",
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
                r0=p.r0,
                pnl=pnl,
                mfe=max(0, p.mfe),
                mae=max(0, p.mae),
                bo_free_space=p.bo_free_space,
                bo_mtr20=p.bo_mtr20,
                bo_space_score=p.bo_space_score,
                bo_hour=p.bo_hour,
                close_reason=reason,
            )
        )
    return out, missing


def scenario_defs():
    s = []

    def add(name, base="N5", nc=None, hc=None, priority="all", min_space=None, min_score=None):
        s.append(
            dict(
                scenario=name,
                base=base,
                normal_cap=nc,
                high_cap=hc,
                priority_filter=priority,
                min_space=min_space,
                min_score=min_score,
            )
        )

    add("CTRL_N5_UNLIMITED")
    add("CTRL_N3_UNLIMITED", base="N3")
    add("N5_NORM1_HIGHINF", nc=1)
    add("N5_NORM2_HIGHINF", nc=2)
    add("N3_NORM1_HIGHINF", base="N3", nc=1)
    add("N3_NORM2_HIGHINF", base="N3", nc=2)
    add("N5_HIGH_ONLY", priority="high")
    add("N5_NORMAL_ONLY", priority="normal")
    for x in (5, 10, 15, 20, 25):
        add(f"N5_SPACE_GE_{x}", min_space=float(x))
    for x in (0.5, 1, 1.5, 2, 2.5, 3, 4):
        add(f"N5_SPACESCORE_GE_{str(x).replace('.', 'P')}", min_score=float(x))
    for x in (5, 10, 15, 20, 25):
        add(f"N5_N1_HINF_SPACE_GE_{x}", nc=1, min_space=float(x))
    for x in (0.5, 1, 1.5, 2, 2.5, 3, 4):
        add(f"N5_N1_HINF_SCORE_GE_{str(x).replace('.', 'P')}", nc=1, min_score=float(x))
    for x in (5, 10, 15, 20):
        add(f"N5_HIGH_SPACE_GE_{x}", priority="high", min_space=float(x))
    for x in (1, 2, 3):
        add(f"N5_HIGH_SCORE_GE_{x}", priority="high", min_score=float(x))
    for x in (10, 15, 20):
        add(f"N3_N1_HINF_SPACE_GE_{x}", base="N3", nc=1, min_space=float(x))
    for x in (1, 2, 3):
        add(f"N3_N1_HINF_SCORE_GE_{x}", base="N3", nc=1, min_score=float(x))
    for x in (1, 2, 3):
        add(f"N5_N1_HINF_SPACE15_SCORE{x}", nc=1, min_space=15.0, min_score=float(x))
    return s


def retain(base_rows, sc):
    out = []
    for r in base_rows:
        if sc["priority_filter"] != "all" and r["priority"] != sc["priority_filter"]:
            continue
        nc = sc["normal_cap"]
        hc = sc["high_cap"]
        if r["priority"] == "normal" and nc is not None and int(r["use_ordinal"]) > int(nc):
            continue
        if r["priority"] == "high" and hc is not None and int(r["use_ordinal"]) > int(hc):
            continue
        if sc["min_space"] is not None:
            x = float(r["bo_free_space"])
            if not (np.isfinite(x) or math.isinf(x)) or x + 1e-12 < sc["min_space"]:
                continue
        if sc["min_score"] is not None:
            x = float(r["bo_space_score"])
            if not (np.isfinite(x) or math.isinf(x)) or x + 1e-12 < sc["min_score"]:
                continue
        out.append(r)
    return out


def metrics(rows):
    p = [float(x["pnl"]) for x in rows]
    return dict(
        trades=len(rows),
        net_pnl=sum(p),
        pf=pf_of(p),
        expectancy=(sum(p) / len(p) if p else math.nan),
        mean_mfe=(sum(float(x["mfe"]) for x in rows) / len(rows) if rows else math.nan),
        mean_mae=(sum(float(x["mae"]) for x in rows) / len(rows) if rows else math.nan),
    )


def write_csv(path, rows):
    keys = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main():
    root = Path(__file__).resolve().parent
    ref = root / "pb_context_reference"
    summary = ref / "R2_ALLFLAT_H4S15_100K_summary.csv"
    ranges = ref / "ranges.csv"
    if not summary.exists() or not ranges.exists():
        raise RuntimeError("Self-contained reference files missing.")
    print(f"SCRIPT_DIR={root}")
    print(f"REFERENCE_DIR={ref}")
    cache = discover_cache(root)
    st, bar_ms, op, hi, lo, close, mtr20, offset_ms = load_bars(cache / "m15_bars_server.csv.gz")
    rows, schedules, actual = load_summary(summary)
    zones = load_ranges(ranges)
    raw = defaultdict(list)
    for r in rows:
        if r.get("event") != "BREAKOUT_SIGNAL" or r.get("signal") not in ("BO-B", "BO-S"):
            continue
        d = r["_dt"].strftime("%Y.%m.%d")
        utc_ms = int(r["_dt"].replace(tzinfo=timezone.utc).timestamp() * 1000) - offset_ms
        raw[d].append(
            dict(
                utc_ms=utc_ms, zone_id=r.get("zone_id", ""), buy=r.get("signal") == "BO-B", id=r.get("breakout_id", "")
            )
        )
    bos = defaultdict(list)
    ignored = []
    for d, items in raw.items():
        items.sort(key=lambda x: x["utc_ms"])
        first = next((i for i, x in enumerate(items) if x["id"] == "BO#01"), None)
        if first is None:
            ignored.extend((d, x["zone_id"], x["id"]) for x in items)
            continue
        ignored.extend((d, x["zone_id"], x["id"]) for x in items[:first])
        bos[d] = items[first:]
    base5, miss5 = simulate_fixed(5, zones, bos, cache, bar_ms, hi, lo, close, mtr20, offset_ms, schedules)
    base3, miss3 = simulate_fixed(3, zones, bos, cache, bar_ms, hi, lo, close, mtr20, offset_ms, schedules)
    # hard equivalence gates
    actual_keys = {(x["day"], x["zone_id"], x["signal"], x["parent_id"]) for x in actual}
    sim_keys = {(x["day"], x["zone_id"], x["signal"], x["parent_breakout_id"]) for x in base5}
    inter = len(actual_keys & sim_keys)
    ratio = inter / max(1, len(actual_keys))
    m5 = metrics(base5)
    m3 = metrics(base3)
    n1 = retain(base5, dict(priority_filter="all", normal_cap=1, high_cap=None, min_space=None, min_score=None))
    n2 = retain(base5, dict(priority_filter="all", normal_cap=2, high_cap=None, min_space=None, min_score=None))
    mn1 = metrics(n1)
    mn2 = metrics(n2)
    gate = (
        m5["trades"] == BASELINE_TRADES
        and ratio >= 0.999
        and abs(m5["net_pnl"] - BASELINE_PNL) <= 0.05
        and abs(m5["pf"] - BASELINE_PF) <= 0.005
        and m3["trades"] == N3_TRADES
        and abs(m3["net_pnl"] - N3_PNL) <= 0.05
        and mn1["trades"] == REUSE_N5_N1_HINF_TRADES
        and abs(mn1["net_pnl"] - REUSE_N5_N1_HINF_PNL) <= 0.05
        and mn2["trades"] == REUSE_N5_N2_HINF_TRADES
        and abs(mn2["net_pnl"] - REUSE_N5_N2_HINF_PNL) <= 0.05
        and not miss5
        and not miss3
    )
    days = sorted(zones)
    train = set(days[:15])
    forward = set(days[15:])
    bases = {"N5": base5, "N3": base3}
    scens = scenario_defs()
    matrix = []
    selected = []
    for sc in scens:
        rr = retain(bases[sc["base"]], sc)
        for r in rr:
            z = dict(r)
            z["scenario"] = sc["scenario"]
            selected.append(z)
        for scope, ds in [("TRAIN", train), ("FORWARD", forward), ("ALL", set(days))]:
            g = [x for x in rr if x["day"] in ds]
            mm = metrics(g)
            matrix.append(dict(**sc, scope=scope, **mm))
    # Context diagnostics from controls without multiplying exact-tick runs.
    breakdown = []
    for bname, br in bases.items():
        for fld in ("priority", "age", "use_ordinal", "bo_hour"):
            vals = sorted(set(x[fld] for x in br))
            for v in vals:
                g = [x for x in br if x[fld] == v]
                mm = metrics(g)
                breakdown.append(dict(base=bname, dimension=fld, value=v, scope="ALL", **mm))
                gf = [x for x in g if x["day"] in forward]
                mf = metrics(gf)
                breakdown.append(dict(base=bname, dimension=fld, value=v, scope="FORWARD", **mf))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = root / "evidence" / f"PB_CONTEXT_BATCH_{stamp}"
    outdir.mkdir(parents=True, exist_ok=True)
    write_csv(outdir / "PB_CONTEXT_BATCH_MATRIX.csv", matrix)
    write_csv(outdir / "PB_CONTEXT_CONTROL_TRADES.csv", base5 + base3)
    write_csv(outdir / "PB_CONTEXT_SELECTED_TRADES.csv", selected)
    write_csv(outdir / "PB_CONTEXT_BREAKDOWN.csv", breakdown)
    lines = [
        f"PB_CONTEXT_BATCH_GATE={'PASS' if gate else 'FAIL'}",
        f"N5_ACTUAL_KEY_MATCH={inter}/{len(actual_keys)}",
        f"N5_MATCH_RATIO={ratio:.6f}",
        f"N5_TRADES={m5['trades']}",
        f"N5_PNL={m5['net_pnl']:.2f}",
        f"N5_PF={m5['pf']:.6f}",
        f"N3_TRADES={m3['trades']}",
        f"N3_PNL={m3['net_pnl']:.2f}",
        f"N5_NORM1_HIGHINF_TRADES={mn1['trades']}",
        f"N5_NORM1_HIGHINF_PNL={mn1['net_pnl']:.2f}",
        f"N5_NORM2_HIGHINF_TRADES={mn2['trades']}",
        f"N5_NORM2_HIGHINF_PNL={mn2['net_pnl']:.2f}",
        f"SCENARIOS={len(scens)}",
        "EXACT_TICK_BASE_RUNS=2",
        f"DAY_BOUNDARY_BREAKOUTS_IGNORED={len(ignored)}",
        f"CACHE_DIR={cache}",
        f"SERVER_UTC_OFFSET_HOURS={offset_ms / 3600000:+.2f}",
        "SPACE_DEFINITION=PB trade-direction immediate neighbor gap at parent Breakout.",
        "SPACESCORE_DEFINITION=PB trade-direction free-space / MTR20 computed only from completed M15 bars at parent Breakout.",
        "FILTER_METHOD=Exact-tick N3/N5 base replay once; independent entry-context/reuse gates are deterministic retention of those exact fills, avoiding repeated 12M-tick passes.",
        "NOTE=Screen/ranking only. No trading rule promotion; combined MT5 Real Tick finalist validation remains mandatory.",
    ]
    (outdir / "PB_CONTEXT_BATCH_GATE.txt").write_text("\n".join(lines), encoding="utf-8")
    (outdir / "PB_CONTEXT_BATCH_META.json").write_text(
        json.dumps(
            dict(
                python=sys.version,
                numpy=np.__version__,
                cache=str(cache),
                train_days=sorted(train),
                forward_days=sorted(forward),
                scenarios=scens,
                ignored=ignored,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    zpath = root / "evidence" / f"PB_CONTEXT_BATCH_{stamp}.zip"
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(outdir.iterdir()):
            z.write(p, p.name)
    print("\n".join(lines))
    print(f"EVIDENCE_ZIP={zpath}")
    if not gate:
        print("CONTEXT BATCH FAILED CONTROL GATE. Send ZIP; do not rerun prior stages or MT5.")
        return 2
    fw = [r for r in matrix if r["scope"] == "FORWARD" and r["trades"] >= 20 and r["net_pnl"] > 0 and r["pf"] > 1.0]
    fw.sort(key=lambda r: (r["pf"], r["net_pnl"]), reverse=True)
    print(f"FORWARD_POSITIVE_MIN20={len(fw)}")
    for r in fw[:12]:
        print(
            f"SHORTLIST {r['scenario']} trades={r['trades']} pnl={r['net_pnl']:.2f} pf={r['pf']:.3f} exp={r['expectancy']:.3f}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise

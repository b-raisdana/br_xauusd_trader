from __future__ import annotations
import csv, gzip, json, math, os, re, sys, zipfile
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
import numpy as np

WINDOWS=(3,5,7,9)
MERGE_GAP=1.5
PENETRATION=0.20
R_CAP=6.0
CUT_MINUTES=5
BASELINE_TRADES=288
BASELINE_PNL=30.01
BASELINE_PF=1.034

@dataclass
class Zone:
    day:str; id:str; low:float; high:float; priority:str; index:int

@dataclass
class Cycle:
    day:str; zone_id:str; buy:bool; parent_id:str; valid_bar_no:int=1
    penetration:bool=False; pending:bool=False
    requested:float=0.0; sl:float=0.0; tp:float=0.0; r0:float=0.0

@dataclass
class Position:
    day:str; zone_id:str; buy:bool; parent_id:str; age:int
    requested:float; fill:float; sl:float; tp:float; r0:float
    entry_ms:int; stage:int=0; mfe:float=0.0; mae:float=0.0


def parse_dt(s:str)->datetime:
    s=str(s).strip().replace('T',' ')
    for f in ('%Y.%m.%d %H:%M:%S.%f','%Y.%m.%d %H:%M:%S','%Y-%m-%d %H:%M:%S.%f','%Y-%m-%d %H:%M:%S'):
        try:return datetime.strptime(s,f)
        except:pass
    try:return datetime.fromisoformat(s)
    except: raise ValueError(s)

def pf_of(vals):
    vals=np.asarray(vals,dtype=float)
    w=float(vals[vals>0].sum()) if len(vals) else 0.0
    l=float(-vals[vals<0].sum()) if len(vals) else 0.0
    return (w/l) if l>0 else (math.inf if w>0 else math.nan)

def load_ranges(path:Path):
    raw=defaultdict(list)
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if str(r.get('enabled','true')).strip().lower() in ('false','0','no','off'): continue
            try: lo=float(r['lower']); hi=float(r['upper'])
            except: continue
            if lo<=0 or hi<=0: continue
            p=str(r.get('priority','normal')).strip().lower()
            if p not in ('high','normal'): continue
            raw[str(r['date']).strip()].append((min(lo,hi),max(lo,hi),p))
    out={}
    for day,arr in raw.items():
        arr=sorted(arr)
        pre=[[lo,hi,p,f'R{i}'] for i,(lo,hi,p) in enumerate(arr,1)]
        merged=[]
        for lo,hi,p,zid in pre:
            if not merged: merged.append([lo,hi,p,zid]); continue
            if lo-merged[-1][1] < MERGE_GAP:
                merged[-1][1]=max(merged[-1][1],hi)
                if p=='high': merged[-1][2]='high'
                merged[-1][3]+='&'+zid
            else: merged.append([lo,hi,p,zid])
        out[day]=[Zone(day,zid,lo,hi,p,i) for i,(lo,hi,p,zid) in enumerate(merged)]
    return out

def load_summary(path:Path):
    rows=[]; schedules={}; actual_pb=[]
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            try: r['_dt']=parse_dt(r['server_time'])
            except: continue
            rows.append(r)
            if r.get('event')=='SESSION_SCHEDULE':
                m=re.search(r'day=([A-Z]+).*?raw_from=(\d\d:\d\d:\d\d).*?raw_to=(\d\d:\d\d:\d\d)',r.get('note',''))
                if m:schedules[m.group(1)]=(m.group(2),m.group(3))
    closes={}
    for r in rows:
        if r.get('event')=='POSITION_CLOSED' and str(r.get('signal','')).startswith('PB-'):
            try: closes[int(float(r.get('position_ticket') or 0))]=float(r.get('net_pnl') or 0)
            except: pass
    for r in rows:
        if r.get('event')=='ORDER_FILLED' and str(r.get('signal','')).startswith('PB-'):
            try:t=int(float(r.get('position_ticket') or 0))
            except:t=0
            actual_pb.append(dict(day=r['_dt'].strftime('%Y.%m.%d'),zone_id=r['zone_id'],
                                  signal=r['signal'],parent_id=r.get('parent_breakout_id',''),
                                  pnl=closes.get(t,0.0),fill_time=r['_dt']))
    return rows,schedules,actual_pb

def load_bars(path:Path):
    rows=[]
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            st=parse_dt(r['server_time']).replace(tzinfo=None)
            ut=parse_dt(r['utc_time'])
            if ut.tzinfo is None: ut=ut.replace(tzinfo=timezone.utc)
            rows.append((st,int(ut.timestamp()*1000),float(r['open']),float(r['high']),float(r['low']),float(r['close'])))
    rows.sort(key=lambda x:x[1])
    st=[r[0] for r in rows]; ms=np.array([r[1] for r in rows],dtype=np.int64)
    hi=np.array([r[3] for r in rows],dtype=float); lo=np.array([r[4] for r in rows],dtype=float)
    # Offset: treating server wall clock as UTC epoch and comparing true UTC timestamp.
    server_epoch=st[0].replace(tzinfo=timezone.utc).timestamp()*1000
    offset_ms=int(round(server_epoch-ms[0]))
    return st,ms,hi,lo,offset_ms

def precompute_structure(hi,lo):
    n=len(hi); buy=np.full(n,np.nan); sell=np.full(n,np.nan)
    swing_lo=np.zeros(n,dtype=bool); swing_hi=np.zeros(n,dtype=bool)
    if n>=3:
        swing_lo[1:-1]=(lo[1:-1]<lo[:-2])&(lo[1:-1]<lo[2:])
        swing_hi[1:-1]=(hi[1:-1]>hi[:-2])&(hi[1:-1]>hi[2:])
    lows=[]; highs=[]
    for j in range(n):
        k=j-2
        if k>=1:
            if swing_lo[k]: lows.append(k)
            if swing_hi[k]: highs.append(k)
        if len(lows)>=2:
            a,b=lows[-1],lows[-2]
            if lo[a]>lo[b]: buy[j]=lo[a]
        if len(highs)>=2:
            a,b=highs[-1],highs[-2]
            if hi[a]<hi[b]: sell[j]=hi[a]
    return buy,sell

def discover_cache(root:Path):
    cands=[]
    env=os.environ.get('LOCALAPPDATA')
    if env:
        base=Path(env)/'XAUUSD_PY_RESEARCH_CACHE'
        if base.exists(): cands += [p for p in base.iterdir() if p.is_dir()]
    # Optional local fallback for copied cache.
    if (root/'cache').is_dir(): cands.append(root/'cache')
    good=[]
    for p in cands:
        if (p/'m15_bars_server.csv.gz').exists() and (p/'ticks').is_dir():
            good.append(p)
    if not good: raise RuntimeError('No valid XAUUSD_PY_RESEARCH_CACHE found. Do not redownload; point LOCALAPPDATA to the existing user cache.')
    good.sort(key=lambda p:p.stat().st_mtime,reverse=True)
    return good[0]

def weekday_name(dt): return dt.strftime('%A').upper()
def sec(s):
    h,m,x=map(int,s.split(':')); return h*3600+m*60+x

def risk_model(zones,zi,buy,entry):
    if buy:
        if zi<=0:return None
        sl=max(zones[zi-1].high,entry-R_CAP); r0=entry-sl
        if r0<=0:return None
        tp=None
        for j in range(zi+1,len(zones)):
            if zones[j].low-entry >= r0-1e-9: tp=zones[j].low; break
    else:
        if zi+1>=len(zones):return None
        sl=min(zones[zi+1].low,entry+R_CAP); r0=sl-entry
        if r0<=0:return None
        tp=None
        for j in range(zi-1,-1,-1):
            if entry-zones[j].high >= r0-1e-9: tp=zones[j].high; break
    if tp is None:return None
    return float(sl),float(tp),float(r0)

def simulate_window(N, zones_by_day, breakouts_by_day, cache, bar_st, bar_ms, hi, lo, offset_ms, schedules):
    buy_struct,sell_struct=precompute_structure(hi,lo)
    trades=[]; rejected=0; missing_days=[]
    for day in sorted(zones_by_day):
        tf=cache/'ticks'/f"ticks_server_{day.replace('.','')}.npz"
        if not tf.exists(): missing_days.append(day); continue
        a=np.load(tf,mmap_mode=None); tms=a['time_msc'].astype(np.int64,copy=False); bid=a['bid'].astype(float,copy=False); ask=a['ask'].astype(float,copy=False)
        if len(tms)==0: continue
        zs=zones_by_day[day]; zmap={z.id:i for i,z in enumerate(zs)}
        cycles={}; positions=[]
        bos=breakouts_by_day.get(day,[]); bp=0
        last_bi=None; session_done=False
        # derive cutoff from broker schedule; fallback only to evidenced 23:00 schedule minus 5m if schedule row absent.
        # This fallback is diagnostic, not a universal market constant.
        sample_server=datetime.fromtimestamp((int(tms[0])+offset_ms)/1000,tz=timezone.utc).replace(tzinfo=None)
        sch=schedules.get(weekday_name(sample_server),('00:00:00','23:00:00'))
        cutoff_sec=sec(sch[1])-CUT_MINUTES*60
        for k in range(len(tms)):
            tm=int(tms[k]); b=float(bid[k]); aask=float(ask[k])
            server_dt=datetime.fromtimestamp((tm+offset_ms)/1000,tz=timezone.utc).replace(tzinfo=None)
            ssec=server_dt.hour*3600+server_dt.minute*60+server_dt.second
            bi=int(np.searchsorted(bar_ms,tm,'right')-1)
            if bi<0: continue
            # New-bar processing ages existing cycles BEFORE breakout-derived new cycle creation.
            if last_bi is None: last_bi=bi
            elif bi>last_bi:
                for _ in range(last_bi+1,bi+1):
                    dead=[]
                    for key,c in cycles.items():
                        if c.valid_bar_no>=N: dead.append(key)
                        else:c.valid_bar_no+=1
                    for key in dead: cycles.pop(key,None)
                last_bi=bi
            # Session-safety ALL_FLAT first. No new PB activity after cutoff.
            if ssec>=cutoff_sec:
                if not session_done:
                    cycles.clear()
                    for p in positions:
                        px=b if p.buy else aask
                        fav=(b-p.fill) if p.buy else (p.fill-aask)
                        adv=(p.fill-b) if p.buy else (aask-p.fill)
                        p.mfe=max(p.mfe,fav); p.mae=max(p.mae,adv)
                        pnl=(px-p.fill) if p.buy else (p.fill-px)
                        trades.append((p,px,pnl,'ALL_FLAT'))
                    positions=[]; session_done=True
                continue
            # Server-side exits for positions already open.
            survivors=[]
            for p in positions:
                fav=(b-p.fill) if p.buy else (p.fill-aask); adv=(p.fill-b) if p.buy else (aask-p.fill)
                p.mfe=max(p.mfe,fav); p.mae=max(p.mae,adv)
                close=None; reason=''
                if p.buy:
                    if b<=p.sl: close=b; reason='SL'
                    elif b>=p.tp: close=b; reason='TP'
                else:
                    if aask>=p.sl: close=aask; reason='SL'
                    elif aask<=p.tp: close=aask; reason='TP'
                if close is not None:
                    pnl=(close-p.fill) if p.buy else (p.fill-close); trades.append((p,close,pnl,reason))
                else: survivors.append(p)
            positions=survivors
            # Existing pending stops can fill on this tick. Reversal signals do NOT
            # globally block Pullback entries in the frozen EA; b-31 is scoped to
            # Reversal + M15 candle + Zone + direction only.
            fill_keys=[]
            for key,c in list(cycles.items()):
                if not c.pending: continue
                trig=(aask>=c.requested) if c.buy else (b<=c.requested)
                if trig:
                    fill=aask if c.buy else b
                    positions.append(Position(c.day,c.zone_id,c.buy,c.parent_id,c.valid_bar_no,c.requested,fill,c.sl,c.tp,c.r0,tm))
                    fill_keys.append(key)
            for key in fill_keys: cycles.pop(key,None)
            # Process all breakout signals stamped at/before current tick after aging.
            while bp<len(bos) and bos[bp]['utc_ms']<=tm:
                bo=bos[bp]; bp+=1
                key=(bo['zone_id'],bo['buy'])
                if key in cycles: continue
                if bo['zone_id'] not in zmap: continue
                cycles[key]=Cycle(day,bo['zone_id'],bo['buy'],bo['id'])
            # Conservative PB penetration + exact pending placement.
            for key,c in list(cycles.items()):
                zi=zmap.get(c.zone_id)
                if zi is None: continue
                z=zs[zi]
                if not c.penetration:
                    pen=(b<=z.high-PENETRATION) if c.buy else (b>=z.low+PENETRATION)
                    if pen:c.penetration=True
                if c.penetration and not c.pending:
                    req=z.high if c.buy else z.low
                    can=(req>aask) if c.buy else (req<b)
                    if not can: continue
                    rm=risk_model(zs,zi,c.buy,req)
                    if rm is None:
                        cycles.pop(key,None); rejected+=1; continue
                    c.requested=req; c.sl,c.tp,c.r0=rm; c.pending=True
            # Profit protection occurs after PB cycle management on OnTick.
            for p in positions:
                favorable=(b-p.requested) if p.buy else (p.requested-aask)
                if favorable<0:favorable=0.0
                if p.stage<1 and favorable>=p.r0: p.stage=1
                if p.stage<2 and favorable>=1.5*p.r0: p.stage=2
                if p.stage<3 and favorable>=2.0*p.r0: p.stage=3
                desired=None
                if p.stage>=3 and bi<len(buy_struct):
                    piv=buy_struct[bi] if p.buy else sell_struct[bi]
                    if np.isfinite(piv):
                        improves=(piv>p.sl+1e-9) if p.buy else (piv<p.sl-1e-9)
                        valid=(piv<b) if p.buy else (piv>aask)
                        if improves and valid: desired=float(piv)
                if desired is None and p.stage>=2:
                    d=p.requested+(0.5*p.r0 if p.buy else -0.5*p.r0)
                    improves=(d>p.sl+1e-9) if p.buy else (d<p.sl-1e-9)
                    valid=(d<b) if p.buy else (d>aask)
                    if improves and valid: desired=float(d)
                if desired is None and p.stage>=1:
                    d=p.fill
                    improves=(d>p.sl+1e-9) if p.buy else (d<p.sl-1e-9)
                    valid=(d<b) if p.buy else (d>aask)
                    if improves and valid: desired=float(d)
                if desired is not None:p.sl=desired
        # Defensive end-of-day close if no cutoff tick was available.
        if positions:
            b=float(bid[-1]); aask=float(ask[-1])
            for p in positions:
                px=b if p.buy else aask; pnl=(px-p.fill) if p.buy else (p.fill-px)
                trades.append((p,px,pnl,'DAY_END_FALLBACK'))
    out=[]
    for p,exit_px,pnl,reason in trades:
        out.append(dict(window=N,day=p.day,zone_id=p.zone_id,signal='PB-B' if p.buy else 'PB-S',parent_breakout_id=p.parent_id,
                        age=p.age,requested=p.requested,fill=p.fill,exit=exit_px,sl_initial=None,tp=p.tp,r0=p.r0,pnl=pnl,mfe=max(0,p.mfe),mae=max(0,p.mae),close_reason=reason))
    return out,rejected,missing_days

def main():
    root=Path(__file__).resolve().parent
    ref=root/'pb_window_reference'; summary=ref/'R2_ALLFLAT_H4S15_100K_summary.csv'; ranges=ref/'ranges.csv'
    if not summary.exists() or not ranges.exists(): raise RuntimeError('Patch reference files are missing.')
    cache=discover_cache(root)
    bar_st,bar_ms,hi,lo,offset_ms=load_bars(cache/'m15_bars_server.csv.gz')
    rows,schedules,actual=load_summary(summary); zones=load_ranges(ranges)
    # Breakouts are fixed baseline inputs: PB lifecycle does not create Breakout signals.
    # Important frozen-EA day-boundary ordering:
    # ProcessNewBar() processes the just-closed bar BEFORE HandleDayChange(). Therefore,
    # on the first tick of a new calendar day it can log one or more BREAKOUT_SIGNAL rows
    # with the previous day's g_day_key / zone state. HandleDayChange() immediately cancels
    # those cycles and resets g_breakout_seq=0. The first usable breakout for the new day
    # therefore starts at BO#01. Replay must ignore any leading same-calendar-day breakout
    # rows that appear before that day's first BO#01.
    raw_bos=defaultdict(list)
    for r in rows:
        if r.get('event')!='BREAKOUT_SIGNAL' or r.get('signal') not in ('BO-B','BO-S'): continue
        d=r['_dt'].strftime('%Y.%m.%d'); utc_ms=int(r['_dt'].replace(tzinfo=timezone.utc).timestamp()*1000)-offset_ms
        raw_bos[d].append(dict(utc_ms=utc_ms,zone_id=r.get('zone_id',''),buy=r.get('signal')=='BO-B',id=r.get('breakout_id','')))
    bos=defaultdict(list); day_boundary_ignored=[]
    for d,items in raw_bos.items():
        items.sort(key=lambda x:x['utc_ms'])
        first_reset=next((i for i,x in enumerate(items) if x['id']=='BO#01'),None)
        if first_reset is None:
            # No post-reset breakout exists on this day; all logged calendar-day breakouts
            # are treated as unusable day-boundary artifacts for PB replay.
            day_boundary_ignored.extend((d,x['zone_id'],x['id']) for x in items)
            continue
        if first_reset>0:
            day_boundary_ignored.extend((d,x['zone_id'],x['id']) for x in items[:first_reset])
        bos[d]=items[first_reset:]
    days=sorted(zones); train=set(days[:15]); forward=set(days[15:])
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S'); outdir=root/'evidence'/f'PB_WINDOW_REPLAY_{stamp}'; outdir.mkdir(parents=True,exist_ok=True)
    alltr=[]; diag=[]
    for N in WINDOWS:
        tr,rej,miss=simulate_window(N,zones,bos,cache,bar_st,bar_ms,hi,lo,offset_ms,schedules)
        alltr.extend(tr); diag.append(dict(window=N,rejected_c1=rej,day_boundary_breakouts_ignored=len(day_boundary_ignored),missing_tick_days='|'.join(miss)))
    # Metrics by window/scope and age.
    matrix=[]; age_rows=[]
    for N in WINDOWS:
        d=[x for x in alltr if x['window']==N]
        for scope,ds in [('TRAIN',train),('FORWARD',forward),('ALL',set(days))]:
            g=[x for x in d if x['day'] in ds]; pnl=[x['pnl'] for x in g]
            matrix.append(dict(window=N,scope=scope,trades=len(g),net_pnl=sum(pnl),pf=pf_of(pnl),expectancy=(sum(pnl)/len(g) if g else math.nan),
                               mean_mfe=(sum(x['mfe'] for x in g)/len(g) if g else math.nan),mean_mae=(sum(x['mae'] for x in g)/len(g) if g else math.nan)))
        for age in range(1,N+1):
            g=[x for x in d if x['age']==age]; pnl=[x['pnl'] for x in g]
            age_rows.append(dict(window=N,age=age,trades=len(g),net_pnl=sum(pnl),pf=pf_of(pnl),expectancy=(sum(pnl)/len(g) if g else math.nan),
                                 mean_mfe=(sum(x['mfe'] for x in g)/len(g) if g else math.nan),mean_mae=(sum(x['mae'] for x in g)/len(g) if g else math.nan)))
    # N5 equivalence gate against actual R2 ALL_FLAT PB branch.
    n5=[x for x in alltr if x['window']==5]
    actual_keys={(x['day'],x['zone_id'],x['signal'],x['parent_id']) for x in actual}
    sim_keys={(x['day'],x['zone_id'],x['signal'],x['parent_breakout_id']) for x in n5}
    inter=len(actual_keys & sim_keys); key_ratio=inter/max(1,len(actual_keys))
    n5_pnl=sum(x['pnl'] for x in n5); n5_pf=pf_of([x['pnl'] for x in n5])
    gate=(key_ratio>=0.999 and len(n5)==BASELINE_TRADES and abs(n5_pnl-BASELINE_PNL)<=0.05 and (math.isfinite(n5_pf) and abs(n5_pf-BASELINE_PF)<=0.005))
    # Write files only after calculations are complete.
    def write_csv(name,rows):
        p=outdir/name
        keys=list(rows[0].keys()) if rows else []
        with p.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=keys); w.writeheader(); w.writerows(rows)
    write_csv('PB_WINDOW_REPLAY_MATRIX.csv',matrix); write_csv('PB_WINDOW_REPLAY_BY_AGE.csv',age_rows); write_csv('PB_WINDOW_REPLAY_TRADES.csv',alltr); write_csv('PB_WINDOW_REPLAY_DIAGNOSTICS.csv',diag)
    gate_lines=[f'PB_WINDOW_REPLAY_GATE={"PASS" if gate else "FAIL"}',f'N5_ACTUAL_KEY_MATCH={inter}/{len(actual_keys)}',f'N5_ACTUAL_KEY_MATCH_RATIO={key_ratio:.6f}',
                f'N5_SIM_TRADES={len(n5)}',f'N5_REFERENCE_TRADES={BASELINE_TRADES}',f'N5_SIM_PNL={n5_pnl:.2f}',f'N5_REFERENCE_PNL={BASELINE_PNL:.2f}',f'N5_SIM_PF={n5_pf:.6f}',f'N5_REFERENCE_PF={BASELINE_PF:.6f}',
                f'SERVER_UTC_OFFSET_HOURS={offset_ms/3600000:+.2f}',f'CACHE_DIR={cache}',
                'NOTE=Only rank N3/N7/N9 if this replay gate PASSes. N5 is the equivalence control.',
                f'DAY_BOUNDARY_BREAKOUTS_IGNORED={len(day_boundary_ignored)}',
                'NOTE2=Frozen EA b-31 is Reversal-only (M15 candle + Zone + direction); it does not globally suppress PB fills.',
                'NOTE3=Leading calendar-day breakout rows before BO#01 are ignored because frozen ProcessNewBar logs them before HandleDayChange cancels cycles/resets sequence.',
                'NOTE4=PB-only PnL remains a branch screen, not a causal combined-strategy replay. Finalist still requires MT5 Every Tick Based on Real Ticks.']
    (outdir/'PB_WINDOW_REPLAY_GATE.txt').write_text('\n'.join(gate_lines),encoding='utf-8')
    (outdir/'PB_WINDOW_REPLAY_META.json').write_text(json.dumps(dict(python=sys.version,numpy=np.__version__,cache=str(cache),windows=WINDOWS,train_days=sorted(train),forward_days=sorted(forward),day_boundary_breakouts_ignored=day_boundary_ignored),indent=2),encoding='utf-8')
    zpath=root/'evidence'/f'PB_WINDOW_REPLAY_{stamp}.zip'
    with zipfile.ZipFile(zpath,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(outdir.iterdir()): z.write(p,p.name)
    print('\n'.join(gate_lines)); print(f'EVIDENCE_ZIP={zpath}')
    if not gate:
        print('REPLAY VALIDATION FAILED: do not rank challenger windows. Send the evidence ZIP; no MT5 rerun is required.')
        return 2
    # concise ranking after equivalence passes
    print('WINDOW_RANKING_READY=YES')
    for r in matrix:
        if r['scope']=='FORWARD': print(f"N={r['window']} FORWARD trades={r['trades']} pnl={r['net_pnl']:.2f} pf={r['pf']:.3f} exp={r['expectancy']:.3f}")
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e:
        print(f'ERROR: {e}',file=sys.stderr)
        raise

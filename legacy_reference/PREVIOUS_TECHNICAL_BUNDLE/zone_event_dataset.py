from __future__ import annotations
import argparse, csv, gzip, math, re, json, sys
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import numpy as np
import polars as pl

HORIZONS=(1,2,3,5,8)
MERGE_GAP=1.5
FIXED_SPACE_CONTROL=15.0

@dataclass
class Zone:
    day:str; id:str; low:float; high:float; priority:str; index:int
    lower_gap:float|None=None; upper_gap:float|None=None
    @property
    def width(self): return self.high-self.low

def args():
    p=argparse.ArgumentParser()
    p.add_argument('--cache-dir',required=True)
    p.add_argument('--ranges',required=True)
    p.add_argument('--summary',required=True)
    p.add_argument('--output-dir',required=True)
    return p.parse_args()

def parse_dt(s:str)->datetime:
    s=s.strip().replace('T',' ')
    if s.endswith('Z'): s=s[:-1]+'+00:00'
    try: return datetime.fromisoformat(s)
    except Exception:
        for f in ('%Y.%m.%d %H:%M:%S.%f','%Y.%m.%d %H:%M:%S','%Y-%m-%d %H:%M:%S.%f','%Y-%m-%d %H:%M:%S'):
            try:return datetime.strptime(s,f)
            except:pass
    raise ValueError(s)

def load_bars(path:Path):
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    bars=[]
    for r in rows:
        st=parse_dt(r['server_time']).replace(tzinfo=None)
        ut=parse_dt(r['utc_time'])
        if ut.tzinfo is None: ut=ut.replace(tzinfo=timezone.utc)
        bars.append(dict(server_time=st, utc_time=ut, utc_ms=int(ut.timestamp()*1000),
                         open=float(r['open']),high=float(r['high']),low=float(r['low']),close=float(r['close'])))
    bars.sort(key=lambda x:x['utc_ms'])
    n=len(bars)
    utc_ms=np.array([b['utc_ms'] for b in bars],dtype=np.int64)
    high=np.array([b['high'] for b in bars],dtype=float)
    low=np.array([b['low'] for b in bars],dtype=float)
    close=np.array([b['close'] for b in bars],dtype=float)
    ref_hi=np.full(n,np.nan); ref_lo=np.full(n,np.nan)
    tr=np.full(n,np.nan); mtr20=np.full(n,np.nan)
    prev_close=np.r_[np.nan,close[:-1]]
    tr=np.maximum(high-low,np.maximum(np.abs(high-prev_close),np.abs(low-prev_close)))
    tr[0]=high[0]-low[0]
    for i in range(n):
        if i>=3:
            ref_hi[i]=np.max(high[i-3:i]); ref_lo[i]=np.min(low[i-3:i])
        if i>=1:
            lo_i=max(0,i-20)
            vals=tr[lo_i:i]
            vals=vals[np.isfinite(vals)]
            if len(vals): mtr20[i]=float(np.median(vals))
    day_bar_ord={}
    day_first_open={}; day_last_close={}
    count=defaultdict(int)
    for i,b in enumerate(bars):
        d=b['server_time'].strftime('%Y.%m.%d')
        count[d]+=1; day_bar_ord[i]=count[d]
        day_first_open.setdefault(d,b['open']); day_last_close[d]=b['close']
    # previous session close and opening gap
    days=[]
    for b in bars:
        d=b['server_time'].strftime('%Y.%m.%d')
        if not days or days[-1]!=d: days.append(d)
    opening_gap={}
    prev=None
    for d in days:
        opening_gap[d]=(day_first_open[d]-prev) if prev is not None else math.nan
        prev=day_last_close[d]
    # Dataset-only CloseTrend candidate: completed-close break of prior-3 range, session reset.
    close_state=np.zeros(n,dtype=np.int8)
    state=0; curday=None
    for i,b in enumerate(bars):
        d=b['server_time'].strftime('%Y.%m.%d')
        if d!=curday: state=0; curday=d
        # at bar i, only closes through i-1 are completed. Use close[i-1] vs ref of bar i-1.
        if i>=1 and np.isfinite(ref_hi[i-1]):
            if close[i-1]>ref_hi[i-1]: state=1
            elif close[i-1]<ref_lo[i-1]: state=-1
        close_state[i]=state
    return bars,utc_ms,ref_hi,ref_lo,mtr20,day_bar_ord,opening_gap,close_state

def load_zones(path:Path):
    raw=defaultdict(list)
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            en=str(r.get('enabled','true')).strip().lower()
            if en in ('false','0','no','off'): continue
            d=str(r['date']).strip(); p=str(r['priority']).strip().lower()
            if p not in ('high','normal'): continue
            try:a=float(r['lower']); b=float(r['upper'])
            except:continue
            if a<=0 or b<=0: continue
            raw[d].append((min(a,b),max(a,b),p))
    out={}
    for d,arr in raw.items():
        arr=sorted(arr,key=lambda x:x[0])
        pre=[]
        for j,(lo,hi,p) in enumerate(arr,1): pre.append([lo,hi,p,f'R{j}'])
        merged=[]
        for lo,hi,p,zid in pre:
            if not merged: merged.append([lo,hi,p,zid]); continue
            gap=lo-merged[-1][1]
            if gap<MERGE_GAP:
                merged[-1][1]=max(merged[-1][1],hi)
                if p=='high': merged[-1][2]='high'
                merged[-1][3]=merged[-1][3]+'&'+zid
            else: merged.append([lo,hi,p,zid])
        zs=[]
        for i,(lo,hi,p,zid) in enumerate(merged): zs.append(Zone(d,zid,lo,hi,p,i))
        for i,z in enumerate(zs):
            if i>0:z.lower_gap=max(0.0,z.low-zs[i-1].high)
            if i+1<len(zs):z.upper_gap=max(0.0,zs[i+1].low-z.high)
        out[d]=zs
    return out

def load_summary(path:Path):
    events=[]; schedules={}
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            try:dt=parse_dt(r['server_time']).replace(tzinfo=None)
            except:continue
            r['_dt']=dt
            if r.get('event')=='SESSION_SCHEDULE':
                note=r.get('note','')
                m=re.search(r'day=([A-Z]+).*?raw_from=(\d\d:\d\d:\d\d).*?raw_to=(\d\d:\d\d:\d\d)',note)
                if m:schedules[m.group(1)]=(m.group(2),m.group(3))
            events.append(r)
    return events,schedules

def trend_name(x): return 'UP' if x==1 else 'DOWN' if x==-1 else 'NONE'

def close_trend_name(x): return 'UP' if x==1 else 'DOWN' if x==-1 else 'NONE'

def day_name(dt): return dt.strftime('%A').upper()

def session_label(st:datetime,schedules):
    sch=schedules.get(day_name(st))
    if not sch:return 'NO_SCHEDULE'
    fr,to=sch
    sec=st.hour*3600+st.minute*60+st.second+st.microsecond/1e6
    def sec_of(x):
        h,m,s=map(int,x.split(':')); return h*3600+m*60+s
    a,b=sec_of(fr),sec_of(to)
    if sec<a or sec>=b:return 'OUTSIDE_SESSION'
    if sec<a+45*60:return 'OPENING_45M'
    if sec>=b-5*60:return 'PRECLOSE_5M'
    return 'REGULAR'

def bar_stage(ordn):
    return 'OPEN_1' if ordn==1 else 'OPEN_2' if ordn==2 else 'OPEN_3' if ordn==3 else 'STEADY'

def summary_index(events,bars_utc_ms,offset_ms):
    # Actual signals indexed by server date + bar UTC index + zone.
    idx=defaultdict(list); breakouts=defaultdict(list)
    for r in events:
        zid=r.get('zone_id','').strip()
        if not zid: continue
        st=r['_dt']; utc_ms=int(st.replace(tzinfo=timezone.utc).timestamp()*1000)-offset_ms
        bi=int(np.searchsorted(bars_utc_ms,utc_ms,'right')-1)
        if bi<0:continue
        d=st.strftime('%Y.%m.%d'); key=(d,bi,zid)
        ev=r.get('event',''); sig=r.get('signal','')
        if ev in ('BREAKOUT_SIGNAL','ORDER_FILLED','PULLBACK_CYCLE_CREATED','PENDING_PLACED','TRADE_REJECTED_NO_STOP_ZONE','TRADE_REJECTED_NO_1R_TARGET'):
            idx[key].append(f'{ev}:{sig}' if sig else ev)
        if ev=='BREAKOUT_SIGNAL' and sig in ('BO-B','BO-S'):
            breakouts[(d,zid,sig)].append((bi,st,r.get('breakout_id','')))
    for k in breakouts: breakouts[k].sort()
    return idx,breakouts

def get_retest_age(d,zid,approach,bi,breakouts):
    bo_sig='BO-B' if approach=='ABOVE_TO_ZONE' else 'BO-S'
    arr=breakouts.get((d,zid,bo_sig),[])
    prev=[x for x in arr if x[0]<bi]
    if not prev:return math.nan,''
    x=prev[-1]
    return bi-x[0],x[2]

def excursions(tms,bid,event_idx,event_bar_idx,bars_utc_ms,approach):
    out={}
    px=float(bid[event_idx])
    for h in HORIZONS:
        end_bi=event_bar_idx+h
        if end_bi < len(bars_utc_ms): end_ms=int(bars_utc_ms[end_bi])
        else: end_ms=int(tms[-1])+1
        hi=int(np.searchsorted(tms,end_ms,'left'))
        if hi<=event_idx: seg=np.array([px])
        else: seg=bid[event_idx:hi]
        mx=float(np.max(seg)); mn=float(np.min(seg))
        up=mx-px; down=px-mn
        if approach=='BELOW_TO_ZONE': # natural reversal direction = SELL
            mfe=down; mae=up
        else:
            mfe=up; mae=down
        out[f'max_up_{h}bar']=up; out[f'max_down_{h}bar']=down
        out[f'mfe_reversal_{h}bar']=mfe; out[f'mae_reversal_{h}bar']=mae
        out[f'horizon_{h}bar_complete']=bool(end_ms <= int(tms[-1])+1)
    return out

def main():
    a=args(); cache=Path(a.cache_dir); out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    bars_path=cache/'m15_bars_server.csv.gz'
    if not bars_path.exists(): raise RuntimeError(f'M15 cache missing: {bars_path}')
    tickdir=cache/'ticks'
    if not tickdir.exists(): raise RuntimeError(f'Tick cache directory missing: {tickdir}')
    bars,bar_ms,ref_hi,ref_lo,mtr20,bar_ord,opening_gap,close_state=load_bars(bars_path)
    # infer server-UTC offset from bar columns, never hard-code.
    first=bars[0]
    server_epoch=first['server_time'].replace(tzinfo=timezone.utc).timestamp()
    utc_epoch=first['utc_time'].timestamp()
    offset_ms=int(round((server_epoch-utc_epoch)*1000))
    zones=load_zones(Path(a.ranges))
    events,schedules=load_summary(Path(a.summary))
    actual_idx,breakouts=summary_index(events,bar_ms,offset_ms)

    all_rows=[]; diagnostics=[]; prior_trend=0; prior_bid=None
    zone_id_set={(d,z.id) for d,zs in zones.items() for z in zs}
    signal_zone_pairs={(r['_dt'].strftime('%Y.%m.%d'),r.get('zone_id','').strip()) for r in events if r.get('zone_id','').strip()}
    unmatched_signal_zones=sorted(signal_zone_pairs-zone_id_set)

    for d in sorted(zones):
        tickfile=tickdir/f"ticks_server_{d.replace('.','')}.npz"
        if not tickfile.exists():
            diagnostics.append({'day':d,'ticks':0,'touches':0,'multi_gap_skipped':0,'note':'tick cache missing'})
            continue
        zf=np.load(tickfile,mmap_mode=None)
        tms=zf['time_msc'].astype(np.int64,copy=False); bid=zf['bid'].astype(np.float64,copy=False)
        if len(tms)==0:
            diagnostics.append({'day':d,'ticks':0,'touches':0,'multi_gap_skipped':0,'note':'no ticks'})
            continue
        prev=np.empty_like(bid); prev[0]=bid[0] if prior_bid is None else prior_bid; prev[1:]=bid[:-1]
        bi=np.searchsorted(bar_ms,tms,'right')-1
        valid=(bi>=0)&(bi<len(bar_ms))
        rhi=np.full(len(tms),np.inf); rlo=np.full(len(tms),-np.inf)
        vv=np.where(valid)[0]
        rhi[vv]=ref_hi[bi[vv]]; rlo[vv]=ref_lo[bi[vv]]
        raw=np.zeros(len(tms),dtype=np.int8)
        raw[(bid>rhi)&np.isfinite(rhi)]=1
        raw[(bid<rlo)&np.isfinite(rlo)]=-1
        last=np.maximum.accumulate(np.where(raw!=0,np.arange(len(raw),dtype=np.int64),-1))
        live=np.empty(len(raw),dtype=np.int8); has=last>=0
        live[has]=raw[last[has]]; live[~has]=prior_trend
        if len(live):prior_trend=int(live[-1])
        prior_bid=float(bid[-1])

        zs=zones[d]; lows=np.array([z.low for z in zs]); highs=np.array([z.high for z in zs])
        cand=[]
        for zi,z in enumerate(zs):
            up=np.where((prev<z.low)&(bid>=z.low))[0]
            dn=np.where((prev>z.high)&(bid<=z.high))[0]
            # one event per bar+zone+approach to remove micro recross noise
            for arr,approach in ((up,'BELOW_TO_ZONE'),(dn,'ABOVE_TO_ZONE')):
                seen=set()
                for k in arr.tolist():
                    if k<0 or bi[k]<0: continue
                    key=int(bi[k])
                    if key in seen: continue
                    seen.add(key); cand.append((int(tms[k]),k,zi,approach))
        cand.sort()
        multi=0; ord_all=defaultdict(int); ord_dir=defaultdict(int); kept=0
        for _,k,zi,approach in cand:
            p=float(prev[k]); q=float(bid[k])
            cross_count=int(np.sum((p<lows)&(q>=lows))+np.sum((p>highs)&(q<=highs)))
            if cross_count>1:
                multi+=1; continue
            z=zs[zi]; kept+=1
            ord_all[z.id]+=1; ord_dir[(z.id,approach)]+=1
            gbi=int(bi[k]); b=bars[gbi]
            st=datetime.fromtimestamp((int(tms[k])+offset_ms)/1000,tz=timezone.utc).replace(tzinfo=None)
            lower=z.lower_gap; upper=z.upper_gap
            nearest=min([x for x in (lower,upper) if x is not None],default=math.nan)
            reaction='SELL' if approach=='BELOW_TO_ZONE' else 'BUY'
            free=lower if reaction=='SELL' else upper
            mtr=float(mtr20[gbi]) if np.isfinite(mtr20[gbi]) else math.nan
            age,boid=get_retest_age(d,z.id,approach,gbi,breakouts)
            labels=actual_idx.get((d,gbi,z.id),[])
            row={
                'server_time':st.strftime('%Y.%m.%d %H:%M:%S.%f')[:-3],
                'server_day':d,'bar_server_time':b['server_time'].strftime('%Y.%m.%d %H:%M:%S'),
                'zone_id':z.id,'priority':z.priority,'zone_low':z.low,'zone_high':z.high,'zone_width':z.width,
                'approach_direction':approach,'natural_reversal_direction':reaction,
                'touch_ordinal':ord_all[z.id],'touch_ordinal_direction':ord_dir[(z.id,approach)],
                'touch_bid':float(bid[k]),'prev_bid':float(prev[k]),'live_trend':trend_name(int(live[k])),
                'close_trend_dataset_candidate':close_trend_name(int(close_state[gbi])),
                'opening_stage':bar_stage(bar_ord[gbi]),'session_bucket':session_label(st,schedules),
                'opening_gap_usd':opening_gap.get(d,math.nan),
                'lower_neighbor_gap':lower if lower is not None else math.nan,
                'upper_neighbor_gap':upper if upper is not None else math.nan,
                'nearest_neighbor_gap':nearest,
                'reaction_free_space_usd':free if free is not None else math.nan,
                'free_space_ge_15_control':bool(free is not None and free>=FIXED_SPACE_CONTROL),
                'mtr20_usd':mtr,
                'free_space_over_mtr20':(free/mtr) if free is not None and np.isfinite(mtr) and mtr>0 else math.nan,
                'free_space_over_zone_width':(free/z.width) if free is not None and z.width>0 else math.nan,
                'retest_age_bars':age,'parent_breakout_id_latest':boid,
                'actual_events_same_bar':'|'.join(sorted(set(labels))),
                'actual_reversal_fill_same_bar':any('ORDER_FILLED:R-' in x for x in labels),
                'actual_pullback_fill_same_bar':any('ORDER_FILLED:PB-' in x for x in labels),
                'actual_breakout_same_bar':any('BREAKOUT_SIGNAL:BO-' in x for x in labels),
                'multi_zone_tick_gap':False,
            }
            row.update(excursions(tms,bid,k,gbi,bar_ms,approach))
            all_rows.append(row)
        diagnostics.append({'day':d,'ticks':len(tms),'touches':kept,'multi_gap_skipped':multi,'note':''})

    if not all_rows: raise RuntimeError('No valid Zone touch events were generated.')
    df=pl.DataFrame(all_rows).sort('server_time')
    dataset=out/'ZONE_REACTION_EVENT_DATASET.csv.gz'
    with gzip.open(dataset,'wt',encoding='utf-8',newline='') as f: df.write_csv(f)
    # Compact summaries
    summary=(df.group_by(['priority','approach_direction']).agg([
        pl.len().alias('events'),
        pl.col('touch_ordinal').median().alias('median_touch_ordinal'),
        pl.col('nearest_neighbor_gap').median().alias('median_nearest_gap'),
        pl.col('mfe_reversal_3bar').mean().alias('mean_mfe_3bar'),
        pl.col('mae_reversal_3bar').mean().alias('mean_mae_3bar'),
        pl.col('mfe_reversal_8bar').mean().alias('mean_mfe_8bar'),
        pl.col('mae_reversal_8bar').mean().alias('mean_mae_8bar'),
        pl.col('actual_reversal_fill_same_bar').sum().alias('actual_reversal_fills'),
        pl.col('actual_pullback_fill_same_bar').sum().alias('actual_pullback_fills'),
        pl.col('actual_breakout_same_bar').sum().alias('actual_breakouts'),
    ]).sort(['priority','approach_direction']))
    summary.write_csv(out/'ZONE_EVENT_SUMMARY.csv')
    pl.DataFrame(diagnostics).write_csv(out/'ZONE_EVENT_DAY_COVERAGE.csv')

    day_count=df.select(pl.col('server_day').n_unique()).item()
    high_count=df.filter(pl.col('priority')=='high').height
    normal_count=df.filter(pl.col('priority')=='normal').height
    # Gate focuses on completeness/data integrity, not profitability.
    signal_pair_total=max(1,len(signal_zone_pairs))
    signal_zone_match_ratio=1.0-len(unmatched_signal_zones)/signal_pair_total
    gate_ok=(df.height>=100 and day_count>=20 and signal_zone_match_ratio>=0.99)
    gate=[
        f'ZONE_EVENT_DATASET_GATE={"PASS" if gate_ok else "FAIL"}',
        f'EVENT_ROWS={df.height}',f'DAYS_WITH_EVENTS={day_count}',
        f'HIGH_EVENTS={high_count}',f'NORMAL_EVENTS={normal_count}',
        f'UNMATCHED_ACTUAL_SIGNAL_ZONE_PAIRS={len(unmatched_signal_zones)}',
        f'ACTUAL_SIGNAL_ZONE_MATCH_RATIO={signal_zone_match_ratio:.6f}',
        f'SERVER_UTC_OFFSET_DERIVED_HOURS={offset_ms/3600000:+.2f}',
        'TOUCH_DEFINITION=first directional edge-cross per M15+Zone+approach; multi-zone single-tick gaps excluded',
        'CLOSETREND_NOTE=dataset-only candidate field; not a promoted trading rule',
        'MFE_MAE_NOTE=TP/SL-independent bid excursions in natural reversal direction over 1/2/3/5/8 M15-bar horizons; completion flags expose session/day truncation',
    ]
    if unmatched_signal_zones:
        gate.append('UNMATCHED='+repr(unmatched_signal_zones[:20]))
    (out/'ZONE_EVENT_DATASET_GATE.txt').write_text('\n'.join(gate),encoding='utf-8')
    meta={'python':sys.version,'numpy':np.__version__,'polars':pl.__version__,'cache_dir':str(cache),'ranges':str(a.ranges),'summary':str(a.summary)}
    (out/'ZONE_EVENT_DATASET_META.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print('\n'.join(gate))
    return 0 if gate_ok else 2

if __name__=='__main__': raise SystemExit(main())

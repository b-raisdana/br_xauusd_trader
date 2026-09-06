from __future__ import annotations
import csv, gzip, json, math, os, re, sys, zipfile
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
import numpy as np

MERGE_GAP=1.5
PENETRATION=0.20
R_CAP=6.0
CUT_MINUTES=5
BASELINE_TRADES=288
BASELINE_PNL=30.01
BASELINE_PF=1.0339633318243346
N1_TRADES=134
N1_PNL=36.27

@dataclass
class Zone:
    day:str; id:str; low:float; high:float; priority:str; index:int

@dataclass
class Cycle:
    day:str; zone_id:str; buy:bool; parent_id:str; valid_bar_no:int=1
    penetration:bool=False; pending:bool=False
    requested:float=0.0; sl:float=0.0; tp:float=0.0; r0:float=0.0; target_index:int=-1
    bo_free_space:float=math.nan; bo_mtr20:float=math.nan; bo_space_score:float=math.nan

@dataclass
class Fill:
    scenario:str; day:str; zone_id:str; priority:str; buy:bool; parent_id:str
    age:int; use_ordinal:int; requested:float; fill:float; sl:float; tp:float; r0:float
    entry_ms:int; target_index:int; bo_free_space:float; bo_mtr20:float; bo_space_score:float

@dataclass
class VPos:
    fill:Fill; mode:str; sl:float; target:float|None; target_index:int
    active:bool=True; stage:int=0; runner:bool=False; best:float=0.0
    checkpoint:float|None=None; mfe:float=0.0; mae:float=0.0


def parse_dt(s:str)->datetime:
    s=str(s).strip().replace('T',' ')
    for f in ('%Y.%m.%d %H:%M:%S.%f','%Y.%m.%d %H:%M:%S','%Y-%m-%d %H:%M:%S.%f','%Y-%m-%d %H:%M:%S'):
        try:return datetime.strptime(s,f)
        except:pass
    try:return datetime.fromisoformat(s)
    except:raise ValueError(s)

def pf_of(vals):
    vals=np.asarray(list(vals),dtype=float)
    if len(vals)==0:return math.nan
    w=float(vals[vals>0].sum()); l=float(-vals[vals<0].sum())
    return w/l if l>0 else (math.inf if w>0 else math.nan)

def load_ranges(path:Path):
    raw=defaultdict(list)
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if str(r.get('enabled','true')).strip().lower() in ('false','0','no','off'):continue
            try:lo=float(r['lower']);hi=float(r['upper'])
            except:continue
            if lo<=0 or hi<=0:continue
            p=str(r.get('priority','normal')).strip().lower()
            if p not in ('high','normal'):continue
            raw[str(r['date']).strip()].append((min(lo,hi),max(lo,hi),p))
    out={}
    for day,arr in raw.items():
        arr=sorted(arr);pre=[[lo,hi,p,f'R{i}'] for i,(lo,hi,p) in enumerate(arr,1)];merged=[]
        for lo,hi,p,zid in pre:
            if not merged:merged.append([lo,hi,p,zid]);continue
            if lo-merged[-1][1] < MERGE_GAP:
                merged[-1][1]=max(merged[-1][1],hi)
                if p=='high':merged[-1][2]='high'
                merged[-1][3]+='&'+zid
            else:merged.append([lo,hi,p,zid])
        out[day]=[Zone(day,zid,lo,hi,p,i) for i,(lo,hi,p,zid) in enumerate(merged)]
    return out

def load_summary(path:Path,offset_ms:int):
    rows=[];schedules={}
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            try:r['_dt']=parse_dt(r['server_time'])
            except:continue
            r['_utc_ms']=int(r['_dt'].replace(tzinfo=timezone.utc).timestamp()*1000)-offset_ms
            rows.append(r)
            if r.get('event')=='SESSION_SCHEDULE':
                m=re.search(r'day=([A-Z]+).*?raw_from=(\d\d:\d\d:\d\d).*?raw_to=(\d\d:\d\d:\d\d)',r.get('note',''))
                if m:schedules[m.group(1)]=(m.group(2),m.group(3))
    return rows,schedules

def load_bars(path:Path):
    rows=[]
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            st=parse_dt(r['server_time']).replace(tzinfo=None);ut=parse_dt(r['utc_time'])
            if ut.tzinfo is None:ut=ut.replace(tzinfo=timezone.utc)
            rows.append((st,int(ut.timestamp()*1000),float(r['open']),float(r['high']),float(r['low']),float(r['close'])))
    rows.sort(key=lambda x:x[1])
    st=[r[0] for r in rows];ms=np.array([r[1] for r in rows],dtype=np.int64)
    op=np.array([r[2] for r in rows]);hi=np.array([r[3] for r in rows]);lo=np.array([r[4] for r in rows]);cl=np.array([r[5] for r in rows])
    server_epoch=st[0].replace(tzinfo=timezone.utc).timestamp()*1000;offset_ms=int(round(server_epoch-ms[0]))
    tr=np.empty(len(hi),dtype=float);tr[0]=hi[0]-lo[0]
    if len(hi)>1:
        pc=cl[:-1];tr[1:]=np.maximum(hi[1:]-lo[1:],np.maximum(np.abs(hi[1:]-pc),np.abs(lo[1:]-pc)))
    mtr20=np.full(len(tr),np.nan)
    for i in range(20,len(tr)+1):
        if i<len(tr):mtr20[i]=float(np.median(tr[i-20:i]))
    return st,ms,op,hi,lo,cl,mtr20,offset_ms

def precompute_structure(hi,lo):
    n=len(hi);buy=np.full(n,np.nan);sell=np.full(n,np.nan)
    swing_lo=np.zeros(n,dtype=bool);swing_hi=np.zeros(n,dtype=bool)
    if n>=3:
        swing_lo[1:-1]=(lo[1:-1]<lo[:-2])&(lo[1:-1]<lo[2:]);swing_hi[1:-1]=(hi[1:-1]>hi[:-2])&(hi[1:-1]>hi[2:])
    lows=[];highs=[]
    for j in range(n):
        k=j-2
        if k>=1:
            if swing_lo[k]:lows.append(k)
            if swing_hi[k]:highs.append(k)
        if len(lows)>=2 and lo[lows[-1]]>lo[lows[-2]]:buy[j]=lo[lows[-1]]
        if len(highs)>=2 and hi[highs[-1]]<hi[highs[-2]]:sell[j]=hi[highs[-1]]
    return buy,sell

def precompute_close_trend(hi,lo,cl):
    # Experimental CloseTrend operationalization: completed M15 close vs previous 3 completed-bar range,
    # sticky state, no intrabar flip. State updated after bar j closes and consumed during bar j+1.
    n=len(cl);out=np.zeros(n,dtype=np.int8);state=0
    for j in range(n):
        out[j]=state
        if j>=3:
            rh=float(np.max(hi[j-3:j]));rl=float(np.min(lo[j-3:j]));c=float(cl[j])
            if c>rh:state=1
            elif c<rl:state=-1
    return out

def discover_cache(root:Path):
    cands=[];explicit=os.environ.get('XAUUSD_PY_RESEARCH_CACHE_DIR')
    if explicit:cands.append(Path(explicit))
    env=os.environ.get('LOCALAPPDATA')
    if env:
        base=Path(env)/'XAUUSD_PY_RESEARCH_CACHE'
        if base.exists():cands += [p for p in base.iterdir() if p.is_dir()]
    if (root/'cache').is_dir():cands.append(root/'cache')
    good=[p for p in cands if (p/'m15_bars_server.csv.gz').exists() and (p/'ticks').is_dir()]
    if not good:raise RuntimeError('No valid XAUUSD_PY_RESEARCH_CACHE found. Reuse existing cache; do not redownload ticks.')
    good.sort(key=lambda p:p.stat().st_mtime,reverse=True);return good[0]

def weekday_name(dt):return dt.strftime('%A').upper()
def sec(s):
    h,m,x=map(int,s.split(':'));return h*3600+m*60+x

def risk_model(zones,zi,buy,entry):
    if buy:
        if zi<=0:return None
        sl=max(zones[zi-1].high,entry-R_CAP);r0=entry-sl
        if r0<=0:return None
        tp=None;tidx=-1
        for j in range(zi+1,len(zones)):
            if zones[j].low-entry>=r0-1e-9:tp=zones[j].low;tidx=j;break
    else:
        if zi+1>=len(zones):return None
        sl=min(zones[zi+1].low,entry+R_CAP);r0=sl-entry
        if r0<=0:return None
        tp=None;tidx=-1
        for j in range(zi-1,-1,-1):
            if entry-zones[j].high>=r0-1e-9:tp=zones[j].high;tidx=j;break
    if tp is None:return None
    return float(sl),float(tp),float(r0),int(tidx)

def directional_space(zs,zi,buy):
    if buy:
        if zi+1>=len(zs):return math.inf
        return max(0.0,float(zs[zi+1].low-zs[zi].high))
    if zi<=0:return math.inf
    return max(0.0,float(zs[zi].low-zs[zi-1].high))

def scenario_defs():
    # Selected from PB_CONTEXT_BATCH with enough breadth to test threshold stability without a giant grid.
    return [
      dict(name='CTRL_N5',nmax=5,nc=None,hc=None,min_space=None,min_score=None),
      dict(name='N5_N1_HINF',nmax=5,nc=1,hc=None,min_space=None,min_score=None),
      dict(name='N5_N1_HINF_SPACE10',nmax=5,nc=1,hc=None,min_space=10.0,min_score=None),
      dict(name='N5_N1_HINF_SPACE15',nmax=5,nc=1,hc=None,min_space=15.0,min_score=None),
      dict(name='N5_N1_HINF_SCORE1P5',nmax=5,nc=1,hc=None,min_space=None,min_score=1.5),
      dict(name='N5_N1_HINF_SCORE2',nmax=5,nc=1,hc=None,min_space=None,min_score=2.0),
      dict(name='N5_N1_HINF_SPACE15_SCORE2',nmax=5,nc=1,hc=None,min_space=15.0,min_score=2.0),
      dict(name='N3_N1_HINF_SPACE15',nmax=3,nc=1,hc=None,min_space=15.0,min_score=None),
    ]

EXIT_MODES=[
 'BASELINE',
 'NEXTZONE_L05','NEXTZONE_L10',
 'LADDER_L05','LADDER_L10',
 'STRUCT_L05','STRUCT_L10',
 'VOL075_L05','VOL100_L05','VOL125_L05',
]

def context_ok(sc,z,fs,score):
    if sc['min_space'] is not None and (not (np.isfinite(fs) or math.isinf(fs)) or fs+1e-12<sc['min_space']):return False
    if sc['min_score'] is not None and (not (np.isfinite(score) or math.isinf(score)) or score+1e-12<sc['min_score']):return False
    return True

def cap_reached(sc,z,use_count):
    cap=sc['hc'] if z.priority=='high' else sc['nc']
    return cap is not None and int(use_count[z.id])>=int(cap)

def prepare_breakouts(rows,offset_ms):
    raw=defaultdict(list)
    for r in rows:
        if r.get('event')!='BREAKOUT_SIGNAL' or r.get('signal') not in ('BO-B','BO-S'):continue
        d=r['_dt'].strftime('%Y.%m.%d')
        raw[d].append(dict(utc_ms=r['_utc_ms'],zone_id=r.get('zone_id',''),buy=r.get('signal')=='BO-B',id=r.get('breakout_id','')))
    bos=defaultdict(list);ignored=[]
    for d,items in raw.items():
        items.sort(key=lambda x:x['utc_ms']);first=next((i for i,x in enumerate(items) if x['id']=='BO#01'),None)
        if first is None:ignored.extend((d,x['zone_id'],x['id']) for x in items);continue
        ignored.extend((d,x['zone_id'],x['id']) for x in items[:first]);bos[d]=items[first:]
    return bos,ignored

def causal_entry_replay(zones_by_day,bos,cache,bar_ms,mtr20,offset_ms,schedules,scens):
    fills=[];missing=[];diag=[]
    for day in sorted(zones_by_day):
        tf=cache/'ticks'/f"ticks_server_{day.replace('.','')}.npz"
        if not tf.exists():missing.append(day);continue
        dat=np.load(tf);tms=dat['time_msc'].astype(np.int64,copy=False);bid=dat['bid'].astype(float,copy=False);ask=dat['ask'].astype(float,copy=False)
        if len(tms)==0:continue
        zs=zones_by_day[day];zmap={z.id:i for i,z in enumerate(zs)};daybos=bos.get(day,[])
        sample_server=datetime.fromtimestamp((int(tms[0])+offset_ms)/1000,tz=timezone.utc).replace(tzinfo=None)
        cutoff_sec=sec(schedules.get(weekday_name(sample_server),('00:00:00','23:00:00'))[1])-CUT_MINUTES*60
        states={sc['name']:dict(cycles={},use=defaultdict(int),bp=0,last_bi=None,done=False,sc=sc) for sc in scens}
        for k in range(len(tms)):
            tm=int(tms[k]);b=float(bid[k]);aa=float(ask[k]);server_dt=datetime.fromtimestamp((tm+offset_ms)/1000,tz=timezone.utc).replace(tzinfo=None);ssec=server_dt.hour*3600+server_dt.minute*60+server_dt.second
            bi=int(np.searchsorted(bar_ms,tm,'right')-1)
            if bi<0:continue
            for st in states.values():
                sc=st['sc'];cycles=st['cycles'];use=st['use']
                if st['last_bi'] is None:st['last_bi']=bi
                elif bi>st['last_bi']:
                    for _new in range(st['last_bi']+1,bi+1):
                        dead=[]
                        for key,c in cycles.items():
                            if c.valid_bar_no>=sc['nmax']:dead.append(key)
                            else:c.valid_bar_no+=1
                        for key in dead:cycles.pop(key,None)
                    st['last_bi']=bi
                if ssec>=cutoff_sec:
                    if not st['done']:cycles.clear();st['done']=True
                    continue
                # 1) Native pending activation for cycles that already existed before this tick.
                # This ordering is required by the proven N5 replay: a cycle created/placed on a
                # Breakout tick cannot also fill retroactively on that same tick.
                fill_keys=[]
                for key,c in list(cycles.items()):
                    if not c.pending:continue
                    zi=zmap.get(c.zone_id)
                    if zi is None:continue
                    z=zs[zi]
                    if cap_reached(sc,z,use):cycles.pop(key,None);continue
                    trig=(aa>=c.requested) if c.buy else (b<=c.requested)
                    if trig:
                        use[c.zone_id]+=1;fill=aa if c.buy else b
                        fills.append(Fill(sc['name'],day,c.zone_id,z.priority,c.buy,c.parent_id,c.valid_bar_no,int(use[c.zone_id]),c.requested,fill,c.sl,c.tp,c.r0,tm,c.target_index,c.bo_free_space,c.bo_mtr20,c.bo_space_score))
                        fill_keys.append(key)
                for key in fill_keys:cycles.pop(key,None)

                # 2) Register independent Breakouts after pending activation, matching the control replay.
                while st['bp']<len(daybos) and daybos[st['bp']]['utc_ms']<=tm:
                    bo=daybos[st['bp']];st['bp']+=1
                    if bo['zone_id'] not in zmap:continue
                    key=(bo['zone_id'],bo['buy'])
                    if key in cycles:continue
                    zi=zmap[bo['zone_id']];z=zs[zi]
                    if cap_reached(sc,z,use):continue
                    fs=directional_space(zs,zi,bo['buy']);mbi=int(np.searchsorted(bar_ms,bo['utc_ms'],'right')-1)
                    mv=float(mtr20[mbi]) if 0<=mbi<len(mtr20) and np.isfinite(mtr20[mbi]) else math.nan
                    score=(fs/mv) if np.isfinite(fs) and np.isfinite(mv) and mv>0 else (math.inf if math.isinf(fs) else math.nan)
                    if not context_ok(sc,z,fs,score):continue
                    cycles[key]=Cycle(day,bo['zone_id'],bo['buy'],bo['id'],bo_free_space=fs,bo_mtr20=mv,bo_space_score=score)

                # 3) Penetration/placement. Newly placed Stop orders become eligible on later ticks.
                for key,c in list(cycles.items()):
                    zi=zmap.get(c.zone_id)
                    if zi is None:continue
                    z=zs[zi]
                    if cap_reached(sc,z,use):cycles.pop(key,None);continue
                    if not c.penetration:
                        if ((b<=z.high-PENETRATION) if c.buy else (b>=z.low+PENETRATION)):c.penetration=True
                    if c.penetration and not c.pending:
                        req=z.high if c.buy else z.low;can=(req>aa) if c.buy else (req<b)
                        if not can:continue
                        rm=risk_model(zs,zi,c.buy,req)
                        if rm is None:cycles.pop(key,None);continue
                        c.requested=req;c.sl,c.tp,c.r0,c.target_index=rm;c.pending=True
        for st in states.values():
            diag.append(dict(day=day,scenario=st['sc']['name'],fills=sum(1 for x in fills if x.day==day and x.scenario==st['sc']['name'])))
    return fills,missing,diag

def lock_price(f:Fill,ratio:float):return f.requested+(ratio*f.r0 if f.buy else -ratio*f.r0)
def aligned(ct:int,buy:bool):return ct==(1 if buy else -1)

def next_zone_target(zs,idx,buy):
    j=idx+1 if buy else idx-1
    if j<0 or j>=len(zs):return None,-1
    return (float(zs[j].low) if buy else float(zs[j].high)),j

def tighten_sl(v:VPos,new:float,bid:float,ask:float):
    if v.fill.buy:
        if new>v.sl+1e-9 and new<bid:return new
    else:
        if new<v.sl-1e-9 and new>ask:return new
    return v.sl

def mode_lock(mode):return 1.0 if '_L10' in mode else 0.5

def mode_volk(mode):
    if mode.startswith('VOL075'):return 0.75
    if mode.startswith('VOL100'):return 1.00
    if mode.startswith('VOL125'):return 1.25
    return None

def parse_reversal_events(rows):
    close_pnl={}
    for r in rows:
        if r.get('event')=='POSITION_CLOSED' and r.get('signal') in ('R-B','R-S'):
            try:close_pnl[int(float(r.get('position_ticket') or 0))]=float(r.get('net_pnl') or 0)
            except:pass
    primary=[]
    for r in rows:
        if r.get('event')=='ORDER_FILLED' and r.get('signal') in ('R-B','R-S'):
            try:t=int(float(r.get('position_ticket') or 0))
            except:t=0
            primary.append(dict(utc_ms=r['_utc_ms'],day=r['_dt'].strftime('%Y.%m.%d'),zone_id=r.get('zone_id',''),signal=r.get('signal',''),kind='PRIMARY',pnl=close_pnl.get(t,0.0),ticket=t))
    shadows=[]
    for r in rows:
        if r.get('event')=='SECONDARY_REVERSAL_CANDIDATE' and r.get('signal') in ('R-B','R-S'):
            shadows.append(dict(utc_ms=r['_utc_ms'],day=r['_dt'].strftime('%Y.%m.%d'),zone_id=r.get('zone_id',''),signal=r.get('signal',''),kind='SHADOW',pnl=0.0,ticket=0))
    out=primary+shadows;out.sort(key=lambda x:x['utc_ms']);return out,primary

def simulate_exits_and_conflicts(fills,zones_by_day,cache,bar_ms,hi,lo,mtr20,close_trend,offset_ms,schedules,rev_events):
    buy_struct,sell_struct=precompute_structure(hi,lo);results=[];conflicts=[]
    fills_by_day=defaultdict(list);rev_by_day=defaultdict(list)
    for f in fills:fills_by_day[f.day].append(f)
    for r in rev_events:rev_by_day[r['day']].append(r)
    for day in sorted(zones_by_day):
        tf=cache/'ticks'/f"ticks_server_{day.replace('.','')}.npz"
        if not tf.exists():continue
        dat=np.load(tf);tms=dat['time_msc'].astype(np.int64,copy=False);bid=dat['bid'].astype(float,copy=False);ask=dat['ask'].astype(float,copy=False)
        if len(tms)==0:continue
        zs=zones_by_day[day];dayfills=sorted(fills_by_day.get(day,[]),key=lambda x:x.entry_ms);revs=sorted(rev_by_day.get(day,[]),key=lambda x:x['utc_ms'])
        fp=0;rp=0;active=[];sample_server=datetime.fromtimestamp((int(tms[0])+offset_ms)/1000,tz=timezone.utc).replace(tzinfo=None)
        cutoff_sec=sec(schedules.get(weekday_name(sample_server),('00:00:00','23:00:00'))[1])-CUT_MINUTES*60;session_done=False
        def close_v(v,px,reason,tm):
            f=v.fill;pnl=(px-f.fill) if f.buy else (f.fill-px);v.active=False
            results.append(dict(scenario=f.scenario,exit_mode=v.mode,day=f.day,zone_id=f.zone_id,priority=f.priority,signal='PB-B' if f.buy else 'PB-S',parent_breakout_id=f.parent_id,age=f.age,use_ordinal=f.use_ordinal,entry_ms=f.entry_ms,exit_ms=tm,requested=f.requested,fill=f.fill,exit=px,r0=f.r0,pnl=pnl,mfe=max(0.0,v.mfe),mae=max(0.0,v.mae),bo_free_space=f.bo_free_space,bo_mtr20=f.bo_mtr20,bo_space_score=f.bo_space_score,close_reason=reason,runner_activated=v.runner))
        for k in range(len(tms)):
            tm=int(tms[k]);b=float(bid[k]);aa=float(ask[k]);server_dt=datetime.fromtimestamp((tm+offset_ms)/1000,tz=timezone.utc).replace(tzinfo=None);ssec=server_dt.hour*3600+server_dt.minute*60+server_dt.second;bi=int(np.searchsorted(bar_ms,tm,'right')-1)
            if bi<0:continue
            ct=int(close_trend[bi]) if bi<len(close_trend) else 0
            # Existing positions: native exits first, matching control ordering.
            for v in list(active):
                if not v.active:continue
                f=v.fill;fav=(b-f.fill) if f.buy else (f.fill-aa);adv=(f.fill-b) if f.buy else (aa-f.fill);v.mfe=max(v.mfe,fav);v.mae=max(v.mae,adv)
                hit_sl=(b<=v.sl) if f.buy else (aa>=v.sl)
                if hit_sl:
                    close_v(v,b if f.buy else aa,'SL',tm);continue
                if v.target is not None:
                    hit_t=(b>=v.target) if f.buy else (aa<=v.target)
                    if hit_t:
                        if v.mode=='BASELINE':close_v(v,b if f.buy else aa,'TP',tm);continue
                        if not v.runner:
                            if not aligned(ct,f.buy):close_v(v,b if f.buy else aa,'CHECKPOINT_NOT_ALIGNED',tm);continue
                            v.runner=True;v.checkpoint=float(v.target);v.sl=tighten_sl(v,lock_price(f,mode_lock(v.mode)),b,aa)
                            if v.mode.startswith('NEXTZONE') or v.mode.startswith('LADDER'):
                                nt,ni=next_zone_target(zs,v.target_index,f.buy)
                                if nt is None:
                                    close_v(v,b if f.buy else aa,'NO_NEXT_ZONE',tm);continue
                                v.target=nt;v.target_index=ni
                            else:v.target=None
                        else:
                            if v.mode.startswith('NEXTZONE'):
                                close_v(v,b if f.buy else aa,'NEXT_ZONE_FINAL',tm);continue
                            if v.mode.startswith('LADDER'):
                                if not aligned(ct,f.buy):close_v(v,b if f.buy else aa,'LADDER_TREND_EXIT',tm);continue
                                oldcp=float(v.target);nt,ni=next_zone_target(zs,v.target_index,f.buy)
                                if nt is None:close_v(v,b if f.buy else aa,'LADDER_LAST_ZONE',tm);continue
                                v.sl=tighten_sl(v,oldcp,b,aa);v.checkpoint=oldcp;v.target=nt;v.target_index=ni
            active=[v for v in active if v.active]
            if ssec>=cutoff_sec:
                if not session_done:
                    for v in list(active):
                        if v.active:close_v(v,b if v.fill.buy else aa,'ALL_FLAT',tm)
                    active=[];session_done=True
                continue
            # Activate fills up to this tick.
            while fp<len(dayfills) and dayfills[fp].entry_ms<=tm:
                f=dayfills[fp];fp+=1
                for mode in EXIT_MODES:active.append(VPos(f,mode,f.sl,f.tp,f.target_index,best=f.fill))
            # Conflict census after fills are active, before end-of-tick management.
            while rp<len(revs) and revs[rp]['utc_ms']<=tm:
                rv=revs[rp];rp+=1
                for sc in sorted({f.scenario for f in dayfills}):
                    for mode in EXIT_MODES:
                        qq=[v for v in active if v.active and v.fill.scenario==sc and v.mode==mode and v.fill.zone_id==rv['zone_id'] and (('R-S'==rv['signal'] and v.fill.buy) or ('R-B'==rv['signal'] and not v.fill.buy)) and aligned(ct,v.fill.buy)]
                        if qq:
                            conflicts.append(dict(scenario=sc,exit_mode=mode,day=day,rev_kind=rv['kind'],rev_signal=rv['signal'],zone_id=rv['zone_id'],rev_utc_ms=rv['utc_ms'],active_pb_count=len(qq),blocked_primary_rev_pnl=float(rv['pnl']) if rv['kind']=='PRIMARY' else 0.0,close_trend=ct))
            # Management after fill, matching baseline b29 ordering; runner adds protection after activation.
            for v in list(active):
                if not v.active:continue
                f=v.fill;fav=(b-f.requested) if f.buy else (f.requested-aa);fav=max(0.0,fav);v.best=max(v.best,b if f.buy else aa)
                if v.stage<1 and fav>=f.r0:v.stage=1
                if v.stage<2 and fav>=1.5*f.r0:v.stage=2
                if v.stage<3 and fav>=2.0*f.r0:v.stage=3
                desired=None
                if v.stage>=3 and bi<len(buy_struct):
                    piv=buy_struct[bi] if f.buy else sell_struct[bi]
                    if np.isfinite(piv):desired=float(piv)
                if desired is not None:v.sl=tighten_sl(v,desired,b,aa)
                if v.stage>=2:v.sl=tighten_sl(v,lock_price(f,0.5),b,aa)
                if v.stage>=1:v.sl=tighten_sl(v,f.fill,b,aa)
                if v.runner:
                    if not aligned(ct,f.buy):
                        close_v(v,b if f.buy else aa,'CLOSETREND_FLIP',tm);continue
                    vk=mode_volk(v.mode)
                    if vk is not None and bi<len(mtr20) and np.isfinite(mtr20[bi]) and mtr20[bi]>0:
                        trail=(b-vk*mtr20[bi]) if f.buy else (aa+vk*mtr20[bi]);v.sl=tighten_sl(v,float(trail),b,aa)
            active=[v for v in active if v.active]
        if active:
            b=float(bid[-1]);aa=float(ask[-1]);tm=int(tms[-1])
            for v in list(active):
                if v.active:close_v(v,b if v.fill.buy else aa,'DAY_END_FALLBACK',tm)
    return results,conflicts

def metrics(rows):
    p=[float(x['pnl']) for x in rows];by=defaultdict(float)
    for x in rows:by[x['day']]+=float(x['pnl'])
    days=list(by.values());equity=0.0;peak=0.0;maxdd=0.0
    for d in sorted(by):equity+=by[d];peak=max(peak,equity);maxdd=max(maxdd,peak-equity)
    return dict(trades=len(rows),net_pnl=sum(p),pf=pf_of(p),expectancy=(sum(p)/len(p) if p else math.nan),positive_days=sum(v>0 for v in days),negative_days=sum(v<0 for v in days),worst_day=(min(days) if days else math.nan),best_day=(max(days) if days else math.nan),daily_max_dd=maxdd,mean_mfe=(sum(float(x['mfe']) for x in rows)/len(rows) if rows else math.nan),mean_mae=(sum(float(x['mae']) for x in rows)/len(rows) if rows else math.nan))

def actual_reversal_metrics(primary,days):
    rr=[dict(day=x['day'],pnl=float(x['pnl'])) for x in primary if x['day'] in days];return metrics([dict(x,mfe=0.0,mae=0.0) for x in rr])

def write_csv(path,rows):
    keys=list(rows[0].keys()) if rows else []
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def main():
    root=Path(__file__).resolve().parent;ref=root/'pb_finalist_reference';summary=ref/'R2_ALLFLAT_H4S15_100K_summary.csv';ranges=ref/'ranges.csv'
    if not summary.exists() or not ranges.exists():raise RuntimeError('Self-contained reference files missing.')
    cache=discover_cache(root);st,bar_ms,op,hi,lo,cl,mtr20,offset_ms=load_bars(cache/'m15_bars_server.csv.gz');rows,schedules=load_summary(summary,offset_ms);zones=load_ranges(ranges);bos,ignored=prepare_breakouts(rows,offset_ms);scens=scenario_defs();ct=precompute_close_trend(hi,lo,cl)
    print(f'CACHE_DIR={cache}');print(f'SERVER_UTC_OFFSET_HOURS={offset_ms/3600000:+.2f}');print(f'ENTRY_SCENARIOS={len(scens)}');print(f'EXIT_MODES={len(EXIT_MODES)}')
    fills,missing,entry_diag=causal_entry_replay(zones,bos,cache,bar_ms,mtr20,offset_ms,schedules,scens)
    rev_events,primary_rev=parse_reversal_events(rows);trades,conflicts=simulate_exits_and_conflicts(fills,zones,cache,bar_ms,hi,lo,mtr20,ct,offset_ms,schedules,rev_events)
    days=sorted(zones);train=set(days[:15]);forward=set(days[15:]);allset=set(days)
    matrix=[];comb=[];confm=[]
    for sc in [x['name'] for x in scens]:
      for mode in EXIT_MODES:
        rr=[x for x in trades if x['scenario']==sc and x['exit_mode']==mode]
        cc=[x for x in conflicts if x['scenario']==sc and x['exit_mode']==mode]
        for scope,ds in [('TRAIN',train),('FORWARD',forward),('ALL',allset)]:
            g=[x for x in rr if x['day'] in ds];mm=metrics(g);matrix.append(dict(scenario=sc,exit_mode=mode,scope=scope,**mm))
            rm=actual_reversal_metrics(primary_rev,ds);combined=mm['net_pnl']+rm['net_pnl'];prim=[x for x in cc if x['day'] in ds and x['rev_kind']=='PRIMARY'];shadow=[x for x in cc if x['day'] in ds and x['rev_kind']=='SHADOW'];blocked=sum(float(x['blocked_primary_rev_pnl']) for x in prim)
            comb.append(dict(scenario=sc,exit_mode=mode,scope=scope,pb_trades=mm['trades'],pb_pnl=mm['net_pnl'],pb_pf=mm['pf'],reversal_trades=rm['trades'],reversal_pnl=rm['net_pnl'],combined_pnl=combined,primary_conflicts=len(prim),shadow_conflicts=len(shadow),blocked_primary_rev_pnl=blocked,pb_priority_static_combined_pnl=combined-blocked))
        for kind in ('PRIMARY','SHADOW'):
            q=[x for x in cc if x['rev_kind']==kind];confm.append(dict(scenario=sc,exit_mode=mode,rev_kind=kind,conflicts=len(q),forward_conflicts=sum(x['day'] in forward for x in q),blocked_primary_rev_pnl=sum(float(x['blocked_primary_rev_pnl']) for x in q)))
    # hard controls
    ctrl=[x for x in matrix if x['scenario']=='CTRL_N5' and x['exit_mode']=='BASELINE' and x['scope']=='ALL'][0]
    n1=[x for x in matrix if x['scenario']=='N5_N1_HINF' and x['exit_mode']=='BASELINE' and x['scope']=='ALL'][0]
    ctrl_fill=sum(1 for f in fills if f.scenario=='CTRL_N5');n1_fill=sum(1 for f in fills if f.scenario=='N5_N1_HINF')
    gate=(not missing and ctrl_fill==BASELINE_TRADES and ctrl['trades']==BASELINE_TRADES and abs(ctrl['net_pnl']-BASELINE_PNL)<=0.05 and abs(ctrl['pf']-BASELINE_PF)<=0.005 and n1_fill==N1_TRADES and n1['trades']==N1_TRADES and abs(n1['net_pnl']-N1_PNL)<=0.05)
    # robust shortlist: positive train+forward, >=20 forward PB trades, PF>1.10 both; rank on min(train_pf,forward_pf), then forward pnl.
    lookup={(x['scenario'],x['exit_mode'],x['scope']):x for x in matrix};short=[]
    for sc in [x['name'] for x in scens]:
      for mode in EXIT_MODES:
        tr=lookup[(sc,mode,'TRAIN')];fw=lookup[(sc,mode,'FORWARD')]
        if tr['net_pnl']>0 and fw['net_pnl']>0 and fw['trades']>=20 and tr['pf']>1.10 and fw['pf']>1.10:
            short.append(dict(scenario=sc,exit_mode=mode,train_trades=tr['trades'],train_pnl=tr['net_pnl'],train_pf=tr['pf'],forward_trades=fw['trades'],forward_pnl=fw['net_pnl'],forward_pf=fw['pf'],robust_pf=min(tr['pf'],fw['pf']),forward_worst_day=fw['worst_day'],forward_daily_dd=fw['daily_max_dd']))
    short.sort(key=lambda x:(x['robust_pf'],x['forward_pnl']),reverse=True)
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S');outdir=root/'evidence'/f'PB_FINALIST_BATCH_{stamp}';outdir.mkdir(parents=True,exist_ok=True)
    write_csv(outdir/'PB_FINALIST_ENTRY_FILLS.csv',[f.__dict__ for f in fills]);write_csv(outdir/'PB_FINALIST_MATRIX.csv',matrix);write_csv(outdir/'PB_FINALIST_COMBINED.csv',comb);write_csv(outdir/'PB_FINALIST_CONFLICTS.csv',conflicts);write_csv(outdir/'PB_FINALIST_CONFLICT_SUMMARY.csv',confm);write_csv(outdir/'PB_FINALIST_SHORTLIST.csv',short);write_csv(outdir/'PB_FINALIST_ENTRY_DIAGNOSTICS.csv',entry_diag)
    meta=dict(python=sys.version,numpy=np.__version__,cache=str(cache),train_days=sorted(train),forward_days=sorted(forward),entry_scenarios=scens,exit_modes=EXIT_MODES,day_boundary_breakouts_ignored=ignored,close_trend_definition='Completed M15 close vs prior 3 completed-bar High/Low range; sticky state; consumed from next bar; no intrabar flips.',runner_definition='First qualifying Zone is checkpoint. Continue only when CloseTrend aligned. Profit lock before continuation. NEXTZONE, LADDER, STRUCT and MTR20 volatility trail variants tested.',pb_priority_definition='Strict same-zone active filled PB + opposite proposed Reversal + CloseTrend aligned. Primary-Reversal PnL removal is static diagnostic only; no rule promotion from it.')
    (outdir/'PB_FINALIST_META.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    lines=[f'PB_FINALIST_BATCH_GATE={"PASS" if gate else "FAIL"}',f'CTRL_N5_FILL_COUNT={ctrl_fill}',f'CTRL_N5_TRADES={ctrl["trades"]}',f'CTRL_N5_PNL={ctrl["net_pnl"]:.2f}',f'CTRL_N5_PF={ctrl["pf"]:.6f}',f'N5_N1_HINF_FILL_COUNT={n1_fill}',f'N5_N1_HINF_PNL={n1["net_pnl"]:.2f}',f'ENTRY_SCENARIOS={len(scens)}',f'EXIT_MODES={len(EXIT_MODES)}',f'SCENARIO_EXIT_COMBINATIONS={len(scens)*len(EXIT_MODES)}',f'ROBUST_SHORTLIST={len(short)}',f'REVERSAL_PRIMARY_TRADES={len(primary_rev)}',f'DAY_BOUNDARY_BREAKOUTS_IGNORED={len(ignored)}',f'CACHE_DIR={cache}',f'SERVER_UTC_OFFSET_HOURS={offset_ms/3600000:+.2f}','NOTE=PB runner/context are causal entry+exit research replays. PB_PRIORITY realized-PnL effect remains static diagnostic because blocking a Reversal can alter later Reversal consumption. Final MT5 Real Tick validation remains mandatory.']
    (outdir/'PB_FINALIST_GATE.txt').write_text('\n'.join(lines),encoding='utf-8')
    zpath=root/'evidence'/f'PB_FINALIST_BATCH_{stamp}.zip'
    with zipfile.ZipFile(zpath,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(outdir.iterdir()):z.write(p,p.name)
    print('\n'.join(lines));
    for r in short[:15]:print(f"SHORTLIST {r['scenario']} + {r['exit_mode']} | train {r['train_pnl']:.2f}/PF{r['train_pf']:.3f} | forward {r['forward_pnl']:.2f}/PF{r['forward_pf']:.3f} | n={r['forward_trades']}")
    print(f'EVIDENCE_ZIP={zpath}')
    if not gate:return 2
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e:
        print(f'ERROR: {e}',file=sys.stderr);raise

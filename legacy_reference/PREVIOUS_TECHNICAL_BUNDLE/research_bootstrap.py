from __future__ import annotations
import argparse, json, os, platform, sys, hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
import numpy as np
import polars as pl
import csv, gzip

SERVER_FROM = datetime(2026,7,29,0,0,0)
SERVER_TO   = datetime(2026,8,29,0,0,0)  # exclusive; includes zone day 2026-08-28
SYMBOL='XAUUSD'
CAL_DAY='2026.07.29'

def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument('--terminal',required=True)
    p.add_argument('--cache-dir',required=True)
    p.add_argument('--evidence-dir',required=True)
    p.add_argument('--reference-fills',required=True)
    p.add_argument('--ranges',required=True)
    return p.parse_args()

def utc(dt_naive): return dt_naive.replace(tzinfo=timezone.utc)

def nearest_match(tms,bid,ask,target_ms,fill_price,window_ms=5000):
    i=int(np.searchsorted(tms,target_ms))
    lo=int(np.searchsorted(tms,target_ms-window_ms,'left'))
    hi=int(np.searchsorted(tms,target_ms+window_ms,'right'))
    if hi<=lo: return None
    tb=tms[lo:hi]; bb=bid[lo:hi]; aa=ask[lo:hi]
    err=np.minimum(np.abs(bb-fill_price),np.abs(aa-fill_price))
    # prioritize price, then time among nearly same price
    j=int(np.argmin(err + np.abs(tb-target_ms)*1e-9))
    return dict(idx=lo+j, time_msc=int(tb[j]), bid=float(bb[j]), ask=float(aa[j]), price_error=float(err[j]), time_error_ms=int(abs(int(tb[j])-target_ms)))

def fetch_ticks(mt5, start_utc, end_utc):
    arr=mt5.copy_ticks_range(SYMBOL,start_utc,end_utc,mt5.COPY_TICKS_ALL)
    if arr is None:
        raise RuntimeError(f'copy_ticks_range returned None: {mt5.last_error()}')
    return arr

def infer_offset(mt5, refs:list[dict], evidence:Path):
    dayrefs=[r for r in refs if str(r['server_time']).startswith(CAL_DAY)]
    if len(dayrefs)<5: raise RuntimeError('Need >=5 first-day reference fills for offset calibration')
    # Memory-safe discovery: probe only tiny +/-5 second tick windows for candidate offsets.
    # No broker UTC offset is hard-coded.
    candidates=np.arange(-12.0,14.0001,0.5)
    anchor_idx=np.unique(np.linspace(0,len(dayrefs)-1,min(3,len(dayrefs)),dtype=int))
    anchors=[dayrefs[int(i)] for i in anchor_idx]
    coarse=[]
    for off in candidates:
        errs=[]; terr=[]; matched=0
        for r in anchors:
            st=datetime.strptime(r['server_time'],'%Y.%m.%d %H:%M:%S.%f')
            target_utc=utc(st-timedelta(hours=float(off)))
            a=fetch_ticks(mt5,target_utc-timedelta(seconds=5),target_utc+timedelta(seconds=5))
            if len(a)==0: continue
            m=nearest_match(a['time_msc'].astype(np.int64),a['bid'].astype(np.float64),a['ask'].astype(np.float64),int(target_utc.timestamp()*1000),float(r['fill_price']),5000)
            if m is None: continue
            matched+=1; errs.append(m['price_error']); terr.append(m['time_error_ms'])
        med=float(np.median(errs)) if errs else 9999.0
        score=(len(anchors)-matched)*1000.0 + med*100.0 + (float(np.median(terr)) if terr else 999999)/100000.0
        coarse.append((score,float(off),matched,med))
    coarse.sort()
    # Validate only the three best offsets against up to 20 real fills.
    sample=dayrefs[:20]
    scores=[]
    cache_windows={}
    for _,off,_,_ in coarse[:3]:
        errs=[]; terr=[]; matched=0
        for r in sample:
            st=datetime.strptime(r['server_time'],'%Y.%m.%d %H:%M:%S.%f')
            target_utc=utc(st-timedelta(hours=float(off)))
            key=(r['server_time'],off)
            a=fetch_ticks(mt5,target_utc-timedelta(seconds=5),target_utc+timedelta(seconds=5))
            if len(a)==0: continue
            m=nearest_match(a['time_msc'].astype(np.int64),a['bid'].astype(np.float64),a['ask'].astype(np.float64),int(target_utc.timestamp()*1000),float(r['fill_price']),5000)
            if m is None: continue
            cache_windows[key]=m
            matched+=1; errs.append(m['price_error']); terr.append(m['time_error_ms'])
        med=float(np.median(errs)) if errs else 9999.0
        p90=float(np.percentile(errs,90)) if errs else 9999.0
        score=(len(sample)-matched)*1000.0 + med*100.0 + p90*10.0 + (float(np.median(terr)) if terr else 999999)/100000.0
        scores.append((score,off,matched,med,p90))
    scores.sort()
    best=scores[0]
    off=float(best[1])
    rows=[]; good=0
    for r in sample:
        st=datetime.strptime(r['server_time'],'%Y.%m.%d %H:%M:%S.%f')
        target_utc=utc(st-timedelta(hours=off))
        m=cache_windows.get((r['server_time'],off))
        if m is None:
            a=fetch_ticks(mt5,target_utc-timedelta(seconds=5),target_utc+timedelta(seconds=5))
            if len(a):
                m=nearest_match(a['time_msc'].astype(np.int64),a['bid'].astype(np.float64),a['ask'].astype(np.float64),int(target_utc.timestamp()*1000),float(r['fill_price']),5000)
        row={'server_time':r['server_time'],'signal':r['signal'],'zone_id':r['zone_id'],'fill_price':float(r['fill_price']),'inferred_server_utc_offset_hours':off}
        if m:
            row.update(m)
            row['matched_utc']=datetime.fromtimestamp(m['time_msc']/1000,tz=timezone.utc).isoformat()
            row['good_price_match']=m['price_error']<=0.25
            good+=int(row['good_price_match'])
        else:
            row.update({'matched_utc':'','bid':np.nan,'ask':np.nan,'price_error':np.nan,'time_error_ms':np.nan,'good_price_match':False})
        rows.append(row)
    pl.DataFrame(rows).write_csv(evidence/'DATA_TIME_ALIGNMENT.csv')
    (evidence/'OFFSET_CANDIDATES_TOP.csv').write_text('score,offset_hours,matched,median_price_error,p90_price_error\n'+'\n'.join(f'{a:.8f},{b:.2f},{c},{d:.8f},{e:.8f}' for a,b,c,d,e in scores),encoding='utf-8')
    good_ratio=good/len(sample)
    if good_ratio<0.80 or best[2]<int(0.8*len(sample)):
        raise RuntimeError(f'UTC/server-time alignment failed: offset={off}, good_ratio={good_ratio:.2%}, matched={best[2]}/{len(sample)}')
    print(f'Inferred broker server UTC offset: {off:+.2f}h; good reference price matches={good}/{len(sample)}')
    return off, good_ratio

def cache_ticks(mt5, cache:Path, offset_h:float, evidence:Path):
    tickdir=cache/'ticks'; tickdir.mkdir(parents=True,exist_ok=True)
    rows=[]
    day=SERVER_FROM
    while day<SERVER_TO:
        nextday=day+timedelta(days=1)
        u0=utc(day-timedelta(hours=offset_h)); u1=utc(nextday-timedelta(hours=offset_h))
        fname=tickdir/f"ticks_server_{day:%Y%m%d}.npz"
        source='cache'
        if fname.exists():
            try:
                z=np.load(fname)
                tms=z['time_msc']; bid=z['bid']; ask=z['ask']
            except Exception:
                fname.unlink(missing_ok=True); tms=np.array([],dtype=np.int64)
        else: tms=np.array([],dtype=np.int64)
        if not fname.exists():
            source='mt5'
            print(f'Caching ticks for server day {day:%Y-%m-%d} ...')
            a=fetch_ticks(mt5,u0,u1)
            tms=a['time_msc'].astype(np.int64)
            bid=a['bid'].astype(np.float64); ask=a['ask'].astype(np.float64)
            # Uncompressed on purpose: much faster to create/read; cache stays local and is never uploaded.
            np.savez(fname,time_msc=tms,bid=bid,ask=ask)
        n=len(tms)
        rows.append({'server_day':day.strftime('%Y.%m.%d'),'utc_from':u0.isoformat(),'utc_to':u1.isoformat(),'ticks':n,'source':source,'first_time_msc':int(tms[0]) if n else '', 'last_time_msc':int(tms[-1]) if n else ''})
        day=nextday
    cov=pl.DataFrame(rows)
    cov.write_csv(evidence/'TICK_CACHE_COVERAGE.csv')
    return cov

def cache_bars(mt5, cache:Path, offset_h:float, evidence:Path):
    u0=utc(SERVER_FROM-timedelta(hours=offset_h)-timedelta(hours=1))
    u1=utc(SERVER_TO-timedelta(hours=offset_h)+timedelta(hours=1))
    rates=mt5.copy_rates_range(SYMBOL,mt5.TIMEFRAME_M15,u0,u1)
    if rates is None or len(rates)<100:
        raise RuntimeError(f'M15 copy_rates_range failed/short: {mt5.last_error()} count={0 if rates is None else len(rates)}')
    records=[]
    for r in rates:
        ut=datetime.fromtimestamp(int(r['time']),tz=timezone.utc)
        st=(ut+timedelta(hours=offset_h)).replace(tzinfo=None)
        if st<SERVER_FROM or st>=SERVER_TO:
            continue
        records.append({
            'server_time':st.isoformat(sep=' '), 'utc_time':ut.isoformat(),
            'open':float(r['open']),'high':float(r['high']),'low':float(r['low']),'close':float(r['close']),
            'tick_volume':int(r['tick_volume']),'spread':int(r['spread']),'real_volume':int(r['real_volume'])
        })
    df=pl.DataFrame(records)
    barpath=cache/'m15_bars_server.csv.gz'
    with gzip.open(barpath,'wt',encoding='utf-8',newline='') as f:
        df.write_csv(f)
    df.head(80).write_csv(evidence/'M15_SAMPLE.csv')
    return df.height,barpath

def main():
    a=parse_args(); evidence=Path(a.evidence_dir); evidence.mkdir(parents=True,exist_ok=True); cache=Path(a.cache_dir); cache.mkdir(parents=True,exist_ok=True)
    try:
        import MetaTrader5 as mt5
    except Exception as e:
        raise RuntimeError(f'MetaTrader5 import failed: {e}')
    refs=pl.read_csv(a.reference_fills, schema_overrides={'server_time':pl.Utf8}).to_dicts()
    for r in refs:
        x=str(r['server_time'])
        r['server_time']=x if '.' in x.split(' ')[-1] else x+'.000'
    if not mt5.initialize(path=a.terminal):
        raise RuntimeError(f'MetaTrader5.initialize failed: {mt5.last_error()}')
    try:
        if not mt5.symbol_select(SYMBOL,True): raise RuntimeError(f'symbol_select({SYMBOL}) failed: {mt5.last_error()}')
        ti=mt5.terminal_info(); ai=mt5.account_info(); si=mt5.symbol_info(SYMBOL)
        if si is None: raise RuntimeError('symbol_info(XAUUSD) returned None')
        specs={
            'python':sys.version,'python_64bit':sys.maxsize>2**32,'platform':platform.platform(),
            'numpy_version':np.__version__,'polars_version':pl.__version__,
            'mt5_package_version':getattr(mt5,'__version__','unknown'),
            'terminal_path':a.terminal,'terminal_build':getattr(ti,'build',None),'terminal_name':getattr(ti,'name',None),
            'account_server':getattr(ai,'server',None),'account_currency':getattr(ai,'currency',None),'account_leverage':getattr(ai,'leverage',None),
            'symbol':SYMBOL,'digits':si.digits,'point':si.point,'trade_tick_size':si.trade_tick_size,'trade_tick_value':si.trade_tick_value,
            'volume_min':si.volume_min,'volume_step':si.volume_step,'volume_max':si.volume_max,'trade_stops_level':si.trade_stops_level,
            'server_from':SERVER_FROM.isoformat(),'server_to_exclusive':SERVER_TO.isoformat(),
            'ranges_sha256':hashlib.sha256(Path(a.ranges).read_bytes()).hexdigest(),
            'reference_fills_sha256':hashlib.sha256(Path(a.reference_fills).read_bytes()).hexdigest(),
            'local_cache_dir':str(cache),
        }
        (evidence/'SYMBOL_ENVIRONMENT.json').write_text(json.dumps(specs,indent=2,default=str),encoding='utf-8')
        off,good=infer_offset(mt5,refs,evidence)
        cov=cache_ticks(mt5,cache,off,evidence)
        bars,barpath=cache_bars(mt5,cache,off,evidence)
        zone_days=pl.read_csv(a.ranges)
        # ranges field naming varies; coverage gate is based on required server date span + non-weekend tick presence.
        required_days=(SERVER_TO-SERVER_FROM).days
        nonzero=int(cov.select((pl.col('ticks')>0).sum()).item())
        total_ticks=int(cov.select(pl.col('ticks').sum()).item())
        gate_ok = good>=0.80 and total_ticks>100000 and bars>1000 and nonzero>=20
        txt=[
            f'PY_DATA_EQUIVALENCE_GATE={"PASS" if gate_ok else "FAIL"}',
            f'INFERRED_SERVER_UTC_OFFSET_HOURS={off:+.2f}',
            f'REFERENCE_GOOD_MATCH_RATIO={good:.6f}',
            f'CACHED_SERVER_DAYS={required_days}',f'NONZERO_TICK_DAYS={nonzero}',f'TOTAL_TICKS={total_ticks}',f'M15_BARS={bars}',
            f'CACHE_DIR={cache}',f'M15_CACHE={barpath}',
            'NOTE=Raw tick cache remains local; upload only the evidence ZIP.'
        ]
        (evidence/'PY_DATA_GATE.txt').write_text('\n'.join(txt),encoding='utf-8')
        print('\n'.join(txt))
        if not gate_ok: return 2
        return 0
    finally:
        mt5.shutdown()

if __name__=='__main__':
    raise SystemExit(main())

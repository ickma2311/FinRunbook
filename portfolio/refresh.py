#!/usr/bin/env python3
"""Read-only account projection + bounded shared prices. Never researches or trades."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import fcntl
import hashlib
from html import escape
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.parse import quote
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
SYMBOL = re.compile(r'^[A-Z][A-Z0-9.\-^=]{0,14}$')


def utcnow():
    return datetime.now(timezone.utc)


def stamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone required')
    return result.astimezone(timezone.utc)


def decimal(value):
    if isinstance(value, bool):
        raise ValueError('Boolean is not an amount')
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError('Non-finite amount')
    return result


def read(path):
    return json.loads(Path(path).read_text())


def amount(value):
    return format(decimal(value),'f')


def atomic(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name+'.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(data if isinstance(data,str) else json.dumps(data,indent=2,allow_nan=False)+'\n')
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)


def source_path(relative):
    p = (REPO/relative).resolve()
    if REPO.resolve() not in p.parents:
        raise ValueError('Account/report must be inside repository')
    return p


def acquisition_history(account):
    """Display-only weighted-average acquisition accounting; never a tax-lot ledger."""
    lots={}; trades=[]; error=None
    try:
        for event in account['ledger']:
            if event.get('type') not in {'funding','sealed_decision','execution_policy_amendment',
                                         'settlement','deposit','withdrawal','external_cash_flow',
                                         'replace_intent','execution_status'}:
                raise ValueError('Unsupported ledger event; acquisition basis requires reconciliation')
            if event.get('type')!='settlement': continue
            for fill in event.get('fills',[]):
                symbol=fill['symbol']; n=fill['shares']; price=decimal(fill['fill_price']); fees=decimal(fill['fees'])
                if type(n) is not int or n<=0 or price<=0 or fees<0 or fill['side'] not in ('buy','sell'):
                    raise ValueError('Invalid execution fill')
                lot=lots.setdefault(symbol,{'shares':0,'fill_cost':Decimal(0),'cost':Decimal(0),'decision_ids':[]})
                if fill['side']=='buy':
                    lot['shares']+=n;lot['fill_cost']+=n*price;lot['cost']+=n*price+fees
                    if event.get('decision_id') and event['decision_id'] not in lot['decision_ids']:
                        lot['decision_ids'].append(event['decision_id'])
                else:
                    if n>lot['shares']: raise ValueError('Sell exceeds reconstructed holding')
                    remaining=lot['shares']-n
                    lot['fill_cost']=lot['fill_cost']*remaining/lot['shares']
                    lot['cost']=lot['cost']*remaining/lot['shares'];lot['shares']=remaining
                    if not remaining:lot['decision_ids']=[]
                trades.append({k:fill[k] for k in ('symbol','side','shares','fill_price','fees')})
                trades[-1].update(filled_at=event.get('filled_at'),decision_id=event.get('decision_id'))
        if {s:x['shares'] for s,x in lots.items() if x['shares']}!=account['positions']:
            raise ValueError('Execution fills do not reconcile to current shares')
    except (ValueError,KeyError,TypeError,InvalidOperation) as exc:
        error=str(exc)
    basis={}
    for symbol in account['positions']:
        item={'average_buy_price':None,'cost_basis':None,'cost_basis_status':'unavailable',
              'unrealized_profit_loss':None,'unrealized_return_pct':None,'decision_ids':[]}
        if error:item['cost_basis_error']=error
        else:
            lot=lots[symbol]
            item.update(average_buy_price=amount(lot['fill_cost']/lot['shares']),cost_basis=amount(lot['cost']),
                        cost_basis_status='reconciled',decision_ids=lot['decision_ids'])
        basis[symbol]=item
    return basis,trades


def decision_history(account):
    results=[]
    for decision in account.get('decisions',[]):
        candidate=decision.get('candidate',{}); review=decision.get('review',{})
        row={key:candidate.get(key) for key in ('action','rationale','target_weights','evidence_cutoff')}
        row.update(decision_id=decision['decision_id'],sealed_at=decision.get('sealed_at'),
                   status=decision.get('status'),review_status=review.get('status'),
                   warnings=review.get('warnings',[])+[f['notes'] for f in review.get('findings',[])
                       if f.get('status') in ('WARN','FAIL') and isinstance(f.get('notes'),str)],
                   execution_changes=[x for x in account['ledger'] if x.get('type')=='execution_policy_amendment'
                                      and x.get('decision_id')==decision['decision_id']],
                   _record=decision)
        results.append(row)
    return results


def publish_decision_evidence(rows, output):
    """Pin exact sealed artifacts by their hash, not a potentially newer HTML report."""
    for row in rows:
        for decision in row.get('decisions',[]):
            record=decision.pop('_record'); candidate=record.get('candidate',{})
            for kind in ('report','evidence'):
                decision[kind+'_url']=None
                try:
                    expected=candidate.get(kind+'_hash')
                    raw=source_path(candidate[kind+'_path']).read_bytes()
                    actual=hashlib.sha256(raw).hexdigest()
                    if not expected or actual!=expected:raise ValueError('Sealed hash mismatch')
                    json.loads(raw)  # These bound research/evidence artifacts must be JSON.
                    relative='evidence/'+actual+'.json'
                    atomic(output/relative,raw.decode())
                    decision[kind+'_url']=relative;decision[kind+'_status']='sealed_hash_verified'
                except (KeyError,ValueError,OSError,TypeError,UnicodeError) as exc:
                    decision[kind+'_status']='unavailable: '+str(exc)
            receipt={'decision':record,'execution_changes':decision['execution_changes'],
                     'account_source':row.get('source'),'artifact_checks':{
                         key:decision[key] for key in ('report_status','evidence_status')}}
            raw=json.dumps(receipt,sort_keys=True,indent=2,allow_nan=False)+'\n'
            relative='decisions/'+hashlib.sha256(raw.encode()).hexdigest()+'.json'
            atomic(output/relative,raw);decision['record_url']=relative


def research_reader(content, title, digest):
    """Lossless, escaped reading view of a pinned research artifact; no inference."""
    def render(value, depth=2):
        if isinstance(value, dict):
            return ''.join('<section><h{0}>{1}</h{0}>{2}</section>'.format(
                min(depth, 6), escape(str(k).replace('_', ' ')), render(v, depth+1))
                for k, v in value.items())
        if isinstance(value, list):
            return '<ol>'+''.join('<li>'+render(v, depth)+'</li>' for v in value)+'</ol>'
        return '<p>'+escape(str(value) if value is not None else 'Not specified')+'</p>'
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>'+escape(title)+'</title><style>'
            'body{max-width:920px;margin:40px auto;padding:0 24px;color:#20302b;'
            'background:#fff;font:15px/1.7 system-ui}h1{font-size:28px}h2{font-size:21px;'
            'border-top:1px solid #d6dfda;padding-top:22px}h3,h4,h5,h6{font-size:16px}'
            'p{white-space:pre-wrap;overflow-wrap:anywhere}li{margin:12px 0}'
            'a{color:#165e4e}small{color:#52665e;overflow-wrap:anywhere}</style>'
            '<a href="../../#research">← Research library</a><h1>'+escape(title)+'</h1>'
            '<small>Archived research content · exact recorded text, not new analysis. '
            'Metadata and original draft labels are preserved. '
            '<a href="../../evidence/'+digest+'.json">Source JSON</a></small>'
            +render(content)+'</html>')


def publish_research_history(rows, output):
    """Index existing reports by content hash; never bind old decisions to latest HTML."""
    for row in rows:
        history=[]; seen=set()
        def add(path, expected, at, status, source, identity, decision=None):
            existing=next((r for r in history if expected and r.get('content_hash')==expected and r.get('report_url')),None)
            if existing:
                if decision is not None:
                    decision['reading_url']=existing['report_url']
                    existing['decision_ids'].append(decision['decision_id'])
                return
            entry={'research_id':identity,'decision_id':decision.get('decision_id') if decision else None,
                   'decision_ids':[decision['decision_id']] if decision else [],
                   'title':row.get('name', 'Expert')+' research','at':at,'status':status,
                   'timestamp_basis':'decision_sealed_at' if decision else 'attempt_recorded_at',
                   'source':source,'report_url':None,'artifact_url':None,'content_hash':expected}
            try:
                raw=path.read_bytes()
                if not expected or hashlib.sha256(raw).hexdigest()!=expected:
                    raise ValueError('Research hash mismatch')
                content=json.loads(raw)
                if not isinstance(content,dict):raise ValueError('Research must be an object')
                meta=content.get('meta',{})
                entry['title']=str(meta.get('title') or content.get('title') or entry['title'])
                executive=content.get('executive_view',{})
                if isinstance(executive,dict):
                    for key in ('headline','summary'):
                        if isinstance(executive.get(key),str):entry[key]=executive[key]
                if isinstance(meta.get('coverage_universe'),str):entry['universe']=meta['coverage_universe']
                entry['artifact_url']='evidence/'+expected+'.json'
                entry['report_url']='research/'+expected+'/index.html'
                atomic(output/entry['artifact_url'],raw.decode())
                if not (output/entry['report_url']).exists():
                    atomic(output/entry['report_url'],research_reader(content,entry['title'],expected))
                if decision is not None:decision['reading_url']=entry['report_url']
                seen.add(expected)
            except (OSError,ValueError,TypeError,UnicodeError) as exc:
                entry['availability_error']=str(exc)
            history.append(entry)
        for d in row.get('decisions',[]):
            url=d.get('report_url')
            digest=Path(url).stem if url else None
            add(output/url if url else output/'missing-report',digest,d.get('sealed_at'),
                d.get('review_status'),'sealed_decision','decision:'+d['decision_id'],d)
        for a in row.get('runtime',{}).get('schedule',{}).get('attempts',[]) or []:
            report=a.get('report')
            if not isinstance(report,dict) or not report.get('path') or report.get('sha256') in seen:continue
            try:path=source_path(report['path'])
            except (ValueError,TypeError):continue
            add(path,report.get('sha256'),a.get('finished_at') or a.get('started_at'),
                a.get('outcome','unknown'),'research_attempt','attempt:'+str(a.get('id')))
        def ordering(record):
            try:return stamp(record['at']).timestamp()
            except (ValueError,KeyError,TypeError,AttributeError):return float('-inf')
        row['research_history']=sorted(history,key=ordering,reverse=True)


def load_accounts(registry, now):
    if registry.get('schema_version') != 1 or registry.get('currency') != 'USD':
        raise ValueError('Unsupported registry')
    ids=[x['id'] for x in registry['experts']]
    if len(ids)!=len(set(ids)):
        raise ValueError('Duplicate expert IDs')
    results=[]; seen=set()
    for entry in registry['experts']:
        row={'expert_id':entry['id'],'name':entry['name'],'status':'not_started',
             'cash':None,'holdings':{},'account_id':None,'error':None}
        try:
            if entry.get('account'):
                path=source_path(entry['account']); raw=path.read_bytes(); account=json.loads(raw)
                if account.get('schema_version')!=1 or account.get('expert_id')!=entry['id'] or account.get('account_id')!=entry['account_id']:
                    raise ValueError('Account identity/schema mismatch')
                if entry['account_id'] in seen: raise ValueError('Duplicate account registration')
                seen.add(entry['account_id'])
                cash=decimal(account['cash']); initial=decimal(account['initial_capital']); holdings=account['positions']
                if cash<0 or initial<=0 or not isinstance(holdings,dict): raise ValueError('Invalid cash/capital/holdings')
                for s,n in holdings.items():
                    if not SYMBOL.fullmatch(s) or type(n) is not int or n<=0: raise ValueError('Only positive whole-share US holdings supported')
                asof=stamp(account['observed_at'])
                if asof>now: raise ValueError('Future account timestamp')
                revision=account['revision']
                if type(revision) is not int or revision<0: raise ValueError('Invalid account revision')
                external=[x for x in account['ledger'] if x.get('type') in ('deposit','withdrawal','external_cash_flow')]
                row.update(status='loaded',account_id=account['account_id'],cash=amount(cash),holdings=holdings,
                           initial_capital=amount(initial),account_as_of=asof.isoformat(),revision=revision,
                           pending_intent_id=account['pending_intent_id'],
                           source={'path':str(path.relative_to(REPO.resolve())),'sha256':hashlib.sha256(raw).hexdigest()},
                           simple_return_supported=not external,
                           fill_count=sum(len(x.get('fills',[])) for x in account['ledger'] if x.get('type')=='settlement'))
                row['_acquisition'],row['trades']=acquisition_history(account)
                row['decisions']=decision_history(account)
                pending=next((i for i in account.get('intents',[]) if i.get('intent_id')==account['pending_intent_id']),None)
                row['pending_decision_id']=pending.get('decision_id') if pending else None
            if entry.get('report'):
                row['report_path']=str(source_path(entry['report']).relative_to(REPO.resolve()))
        except (ValueError,KeyError,OSError,TypeError,AttributeError,InvalidOperation) as exc:
            row.update(status='account_error',cash=None,holdings={},error=str(exc))
        # Research progress is separate from account valuation and never a trade instruction.
        if entry.get('research_status') in {'queued','researching','reviewing','blocked','completed'}:
            row['research_status']=entry['research_status']
            row['research_note']=str(entry.get('research_note',''))
        for key in ('description', 'cadence_description'):
            if isinstance(entry.get(key), str): row[key]=entry[key]
        decisions=row.get('decisions', [])
        if decisions and entry.get('decision_summary_id')==decisions[-1]['decision_id']:
            row['decision_summary']=str(entry.get('decision_summary',''))
        # Scheduler metadata is not a process heartbeat or financial approval.
        row['runtime']={'liveness':'not_measured','observed_at':now.isoformat()}
        if entry.get('schedule_state'):
            try:
                schedule_path=source_path(entry['schedule_state'])
                own=read(schedule_path)['experts'][entry['id']]
                if not isinstance(own,dict):raise ValueError('Invalid expert schedule')
                row['runtime']['schedule']={k:own.get(k) for k in (
                    'last_attempt_at','last_successful_research_at','last_decision_at',
                    'next_review_at','active_attempt','attempts')}
                row['runtime']['_schedule_path']=str(schedule_path)
            except (OSError,ValueError,KeyError,TypeError) as exc:
                row['runtime']['error']='Recorded schedule unavailable: '+str(exc)
        results.append(row)
    return results


def market_context(now):
    import exchange_calendars as xc
    import pandas as pd
    cal=xc.get_calendar('XNYS')
    day=pd.Timestamp(now.date())
    sessions=cal.sessions_in_range(day-pd.Timedelta(days=14),day)
    current=sessions[-1]
    opened=cal.session_open(current).to_pydatetime(); closed=cal.session_close(current).to_pydatetime()
    if now<opened:
        current=sessions[-2]; opened=cal.session_open(current).to_pydatetime(); closed=cal.session_close(current).to_pydatetime()
    is_open=opened<=now<closed
    return {'is_open':is_open,'session':str(current.date()),'open_at':opened.isoformat(),
            'close_at':closed.isoformat(),'calendar':'XNYS regular session; US-equity valuation reference',
            'minimum_price_as_of':(now-timedelta(minutes=10) if is_open else closed-timedelta(minutes=5)).isoformat()}


def fetch_one(symbol, since, market):
    """A unique held ticker is fetched once per batch, shared across experts."""
    import yfinance as yf
    now=utcnow()
    args={'auto_adjust':False,'back_adjust':False,'repair':False,'actions':True,'keepna':True,'rounding':False,'prepost':False,'timeout':8}
    t=yf.Ticker(symbol)
    frame=t.history(period='5d',interval='1m',**args)
    meta=t.history_metadata or {}
    if meta.get('currency')!='USD' or meta.get('exchangeTimezoneName')!='America/New_York' or meta.get('exchangeName') not in ('PCX','NYQ','NMS','NGM','NCM','ASE','BTS'):
        raise ValueError('Unsupported or missing US security metadata')
    if frame.empty: raise ValueError('No minute prices')
    # Restrict to the latest reference regular session; omit unfinished bars.
    eligible=frame[(frame.index>=stamp(market['open_at'])) &
                   (frame.index+timedelta(minutes=1)<=min(now,stamp(market['close_at'])))]
    if eligible.empty: raise ValueError('No completed regular-session bar')
    start, end, values = newest_valid_bar(eligible, market)
    action_start=(stamp(since)-timedelta(days=7)).date().isoformat()
    daily=t.history(start=action_start,end=(now+timedelta(days=1)).date().isoformat(),interval='1d',**args)
    if daily.empty or any(k not in daily for k in ('Dividends','Stock Splits')) or daily[['Dividends','Stock Splits']].isna().any().any():
        raise ValueError('Corporate-action fields unavailable')
    if daily.index.min().date()>stamp(since).date(): raise ValueError('Action coverage does not reach account basis date')
    events=[{'date':str(idx.date()),'dividend':float(r['Dividends']),'split':float(r['Stock Splits'])}
            for idx,r in daily.iterrows() if r['Dividends']!=0 or r['Stock Splits']!=0]
    return {'symbol':symbol,'price':amount(values['Close']),'currency':'USD','price_as_of':end.isoformat(),
            'bar_start':start.isoformat(),'retrieved_at':utcnow().isoformat(),'basis':'completed_1m_close',
            'provider':'Yahoo Finance','client':'yfinance '+yf.__version__,'source_url':'https://finance.yahoo.com/quote/'+quote(symbol,safe='')+'/history/',
            'bar':values,'parameters':{'minute':{'period':'5d','interval':'1m',**args},'actions':{'start':action_start,'interval':'1d',**args}},
            'action_coverage_since':since,'actions':events,'exchange':meta.get('exchangeName')}


def newest_valid_bar(eligible, market):
    """Inactive final bars must not hide an earlier fresh, completed observation."""
    for idx, bar in eligible.iloc[::-1].iterrows():
        start=idx.to_pydatetime(); end=start+timedelta(minutes=1)
        if end < stamp(market['minimum_price_as_of']):
            break
        try:
            values={k:float(bar[k]) for k in ('Open','High','Low','Close','Volume')}
            if all(math.isfinite(v) for v in values.values()) and values['Volume']>0 and 0<values['Low']<=min(values['Open'],values['Close'])<=max(values['Open'],values['Close'])<=values['High']:
                return start, end, values
        except (TypeError, ValueError):
            continue
    raise ValueError('No valid active completed price bar within freshness limit')


def project_operations(rows, output, now):
    """Read durable operations, never infer agent liveness or approval from prose."""
    folder = REPO / 'runs/arena-controller'
    receipts = sorted((folder/'receipts').glob('*.json'))
    state = {}
    error = None
    if receipts:
        try:
            receipt=read(receipts[-1]); state=receipt['state']
            encoded=json.dumps(state,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
            if hashlib.sha256(encoded).hexdigest()!=receipt['state_sha256']:
                raise ValueError('Controller receipt hash mismatch')
        except (OSError,ValueError,KeyError) as exc:
            state={}; error=str(exc)
    queue_path=folder/'execution-queue.json'
    try:
        queue=read(queue_path) if queue_path.exists() else {}
    except (OSError,ValueError):
        queue={}; error='Execution queue unavailable'
    checks={r['expert_id']:r for r in (state.get('last_check') or {}).get('experts',[])}
    for row in rows:
        jobs=[j for j in state.get('jobs',{}).values() if j['expert_id']==row['expert_id']]
        own=max(jobs,key=lambda j:j['created_at']) if jobs else None
        check=checks.get(row['expert_id'],{})
        ops={'last_check_at':(state.get('last_check') or {}).get('checked_at'),
             'eligibility':'due' if check.get('due') else 'not_due' if check else 'unknown',
             'eligibility_reasons':check.get('reasons',[]), 'next_eligible_at':check.get('next_eligible_at'),
             'presentation':{'status':'unverified'}, 'job_id':None,
             'receipt_url':os.path.relpath(receipts[-1],output) if receipts else None,
             'error':error}
        if own:
            ops.update(job_id=own['id'],status=own['status'],stages=own['stages'],presentation=own.get('presentation',{'status':'unverified'}))
            research=own['stages']['research']
            observed_stage=own['stages']['review'] if research['status']=='completed' else research
            observation=observed_stage.get('native_observation')
            ops['worker_liveness']=(observation['status'] if observation and 0<=(now-stamp(observation['observed_at'])).total_seconds()<=300 else 'unknown')
            artifact=research['artifacts'].get('html')
            if artifact:
                try:
                    if hashlib.sha256(Path(artifact['path']).read_bytes()).hexdigest()!=artifact['sha256']:
                        raise ValueError('Report changed after research completion')
                    row['report_path']=str(Path(artifact['path']).relative_to(REPO))
                except (OSError,ValueError) as exc:
                    ops['presentation']={'status':'unavailable','error':str(exc)}
            # Legacy registry notes cannot override a durable active job.
            row.pop('research_note',None)
            row['research_status']='completed' if own['stages']['approval']['status']=='completed' else 'reviewing' if research['status']=='completed' else {'pending':'queued','retryable':'queued','running':'researching','blocked':'blocked','cancelled':'blocked'}.get(research['status'],'queued')
        items=[i for i in queue.get('items',{}).values() if i['expert_id']==row['expert_id']]
        if items:
            ops['execution_queue']=items
        row['operations']=ops
    return {'last_check_at':(state.get('last_check') or {}).get('checked_at'),
            'source_health':state.get('source_health'), 'service':state.get('service',{}), 'error':error}


def worker():
    request=json.load(sys.stdin)
    def one(item):
        symbol,since=item
        try: return symbol,{'quote':fetch_one(symbol,since,request['market'])}
        except Exception as exc: return symbol,{'error':type(exc).__name__+': '+str(exc)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(one,item) for item in request['symbols'].items()]):
            symbol,result=future.result()
            print(json.dumps({'symbol':symbol,**result}),flush=True)


def fetch_shared(symbols,market,deadline):
    if not symbols: return {},{},False
    request=json.dumps({'symbols':symbols,'market':market})
    timed_out=False
    try:
        result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--fetch-worker'],input=request,
                              capture_output=True,text=True,timeout=deadline)
        output=result.stdout
    except subprocess.TimeoutExpired as exc:
        timed_out=True; output=exc.stdout or ''
        if isinstance(output,bytes):output=output.decode()
    quotes={};errors={}
    for line in output.splitlines():
        try:
            item=json.loads(line);symbol=item['symbol']
            if symbol not in symbols: continue
            if 'quote' in item: quotes[symbol]=item['quote']
            else: errors[symbol]=item['error']
        except (ValueError,KeyError,TypeError):continue
    for s in symbols:
        if s not in quotes and s not in errors: errors[s]='Price worker timed out' if timed_out else 'Price worker returned no observation'
    return quotes,errors,timed_out


def project(accounts,quotes,errors,market,now):
    rows=[]
    for original in accounts:
        row=dict(original);row.update(positions=[],holdings_value=None,total_value=None,profit_loss=None,return_pct=None,warnings=[])
        acquisition=row.pop('_acquisition',{})
        if row['status']!='loaded':rows.append(row);continue
        total=Decimal(0);valid=True;price_times=[];stale=False
        for symbol,shares in row['holdings'].items():
            q=quotes.get(symbol);item={'symbol':symbol,'shares':shares,'price':None,'market_value':None,'price_as_of':None,'status':'unavailable'}
            item.update(acquisition.get(symbol,{}))
            try:
                if not q: raise ValueError(errors.get(symbol,'No saved price'))
                price=decimal(q['price']);asof=stamp(q['price_as_of']);retrieved=stamp(q['retrieved_at'])
                if price<=0 or q['currency']!='USD' or asof>retrieved or retrieved>now or asof<stamp(row['account_as_of']):raise ValueError('Invalid price identity/timestamps')
                if stamp(q['action_coverage_since'])>stamp(row['account_as_of']):raise ValueError('Action history does not cover account basis')
                changed=[x for x in q['actions'] if x['date']>stamp(row['account_as_of']).astimezone(ZoneInfo('America/New_York')).date().isoformat()]
                if changed: raise ValueError('Corporate action requires ledger reconciliation before valuation')
                value=shares*price;total+=value;price_times.append(asof)
                is_stale=asof<stamp(market['minimum_price_as_of']) or symbol in errors
                stale=stale or is_stale
                item.update(price=amount(price),market_value=amount(value),price_as_of=asof.isoformat(),
                            status='stale' if is_stale else ('fresh' if market['is_open'] else 'market_closed'),
                            source_url=q['source_url'],basis=q['basis'],age_seconds=(now-asof).total_seconds())
                if symbol in errors: row['warnings'].append(symbol+': '+errors[symbol]+'; showing last saved observation')
            except (KeyError,ValueError,TypeError,InvalidOperation) as exc:
                valid=False;item['error']=str(exc);row['warnings'].append(symbol+': '+str(exc))
            if item.get('cost_basis') is not None and item['market_value'] is not None:
                cost=decimal(item['cost_basis']);pnl=decimal(item['market_value'])-cost
                item.update(unrealized_profit_loss=amount(pnl),unrealized_return_pct=amount(100*pnl/cost) if cost else None)
            row['positions'].append(item)
        row['status']='cash_only' if not row['holdings'] else ('unavailable' if not valid else 'stale' if stale else 'fresh' if market['is_open'] else 'market_closed')
        if valid:
            nav=decimal(row['cash'])+total
            row.update(holdings_value=amount(total),total_value=amount(nav),valuation_as_of=min(price_times).isoformat() if price_times else now.isoformat())
            if row['simple_return_supported']:
                pnl=nav-decimal(row['initial_capital']);row.update(profit_loss=amount(pnl),return_pct=amount(100*pnl/decimal(row['initial_capital'])))
            else:row['warnings'].append('External cash flows present; simple return withheld')
        rows.append(row)
    return rows


def validate_snapshot(snapshot):
    """Small stdlib enforcement of the published v1 balance/valuation contract."""
    if snapshot['schema_version']!=1 or snapshot['currency']!='USD' or snapshot['mode']!='valuation_only':
        raise ValueError('Invalid snapshot header')
    ids=set()
    allowed={'not_started','account_error','account_changed','cash_only','fresh','market_closed','stale','unavailable'}
    for row in snapshot['experts']:
        if row['expert_id'] in ids or row['status'] not in allowed:raise ValueError('Invalid snapshot expert/status')
        ids.add(row['expert_id'])
        for item in row['positions']:
            for key in ('average_buy_price','cost_basis','unrealized_profit_loss','unrealized_return_pct'):
                value=item.get(key)
                if value is not None and (not isinstance(value,str) or not re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?',value)):
                    raise ValueError('Acquisition amount must be a decimal string or null')
            if item.get('unrealized_profit_loss') is not None:
                if item.get('cost_basis') is None or item['market_value'] is None or decimal(item['market_value'])-decimal(item['cost_basis'])!=decimal(item['unrealized_profit_loss']):
                    raise ValueError('Unrealized P/L does not reconcile')
        for key in ('cash','holdings_value','total_value','profit_loss','return_pct'):
            if row[key] is not None and (not isinstance(row[key],str) or not re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?',row[key])):
                raise ValueError('Amount must be a plain decimal string or null: '+key)
        if row['total_value'] is not None:
            values=[]
            for item in row['positions']:
                if row['holdings'][item['symbol']]!=item['shares'] or decimal(item['price'])*item['shares']!=decimal(item['market_value']):
                    raise ValueError('Holding valuation does not reconcile')
                values.append(decimal(item['market_value']))
            if sum(values,Decimal(0))!=decimal(row['holdings_value']) or decimal(row['cash'])+decimal(row['holdings_value'])!=decimal(row['total_value']):
                raise ValueError('Account total does not reconcile')
            if row['profit_loss'] is not None and decimal(row['total_value'])-decimal(row['initial_capital'])!=decimal(row['profit_loss']):
                raise ValueError('P/L does not reconcile')


def run(registry_path,output,offline=False,deadline=35):
    started=time.monotonic(); now=utcnow();output.mkdir(parents=True,exist_ok=True)
    with (output/'.refresh.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {'status':'skipped_already_running','elapsed_seconds':round(time.monotonic()-started,3)}
        registry=read(registry_path);accounts=load_accounts(registry,now)
        source_paths={source_path(x['account']) for x in registry['experts'] if x.get('account')}
        if any((output/name).resolve() in source_paths for name in ('portfolio.json','prices.json','index.html')):raise ValueError('Output would overwrite an account')
        symbols={}
        for a in accounts:
            if a['status']=='loaded':
                for s in a['holdings']:symbols[s]=min(symbols.get(s,a['account_as_of']),a['account_as_of'])
        market=market_context(now)
        cache=read(output/'prices.json') if (output/'prices.json').exists() else {'quotes':{}}
        quotes=cache['quotes']; fresh,errors,timed_out=({}, {}, False) if offline else fetch_shared(symbols,market,deadline)
        quotes={**quotes,**fresh};now=utcnow();market=market_context(now)
        # A concurrent trade is not overwritten. Defer that expert rather than mix revisions.
        for a in accounts:
            if a['status']=='loaded':
                try:
                    changed=hashlib.sha256(source_path(a['source']['path']).read_bytes()).hexdigest()!=a['source']['sha256']
                except OSError:
                    changed=True
                if changed:a.update(status='account_changed',error='Account changed during refresh; rerun to value its new revision')
        rows=project(accounts,quotes,errors,market,now)
        snapshot={'schema_version':1,'snapshot_id':now.strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8],'generated_at':now.isoformat(),
                  'currency':'USD','mode':'valuation_only','market':market,'experts':rows,
                  'price_observations':{s:quotes[s] for s in symbols if s in quotes},
                  'refresh':{'elapsed_seconds':round(time.monotonic()-started,3),'unique_symbols':sorted(symbols),
                             'provider_fetch_count':0 if offline else len(symbols),'offline':offline,'worker_timed_out':timed_out,
                             'errors':errors,'suggested_interval_seconds':300},
                  'limitations':['Read-only projection; execution ledgers remain authoritative.',
                                  'Yahoo minute-close observations are not guaranteed real-time quotes.',
                                  'Provider-reported actions only; dividends/splits require ledger reconciliation.',
                                  'Refresh does not research, trade, fund accounts or start a schedule.']}
        snapshot['operations']=project_operations(rows,output,now)
        for row in rows:
            schedule_path=row.get('runtime',{}).pop('_schedule_path',None)
            if schedule_path:row['runtime']['schedule_url']=os.path.relpath(schedule_path,output)
            if row.get('source'):row['account_url']=os.path.relpath(source_path(row['source']['path']),output)
            if row.get('report_path'):row['report_url']=os.path.relpath(source_path(row['report_path']),output)
        publish_decision_evidence(rows,output)
        publish_research_history(rows,output)
        validate_snapshot(snapshot)
        atomic(output/'prices.json',{'schema_version':1,'quotes':quotes})
        atomic(output/'index.html',(REPO/'portfolio/dashboard.html').read_text())
        atomic(output/'history'/now.strftime('%Y-%m-%d')/(snapshot['snapshot_id']+'.json'),snapshot)
        atomic(output/'portfolio.json',snapshot)  # Single authoritative dashboard snapshot, published last.
        degraded=any(x['status'] in ('stale','unavailable','account_error','account_changed') for x in rows)
        return {'status':'degraded' if degraded else 'ok','output':str(output/'portfolio.json'),**snapshot['refresh']}


def main():
    if '--fetch-worker' in sys.argv:worker();return 0
    p=argparse.ArgumentParser(description=__doc__)
    local_registry=REPO/'portfolio/experts.json'
    p.add_argument('--registry',type=Path,default=local_registry if local_registry.exists() else REPO/'portfolio/experts.example.json')
    p.add_argument('--output',type=Path,default=REPO/'runs/live-portfolio')
    p.add_argument('--offline',action='store_true',help='Rebuild from saved prices, making no network calls')
    p.add_argument('--deadline',type=float,default=35,help='Hard market-data worker deadline in seconds')
    args=p.parse_args()
    if not 1<=args.deadline<=120:p.error('deadline must be between 1 and 120 seconds')
    try:
        result=run(args.registry.resolve(),args.output.resolve(),args.offline,args.deadline)
        print(json.dumps(result));return 2 if result['status']=='degraded' else 0
    except (ValueError,KeyError,OSError,TypeError,InvalidOperation) as exc:
        print(json.dumps({'status':'error','error':str(exc)}));return 1


if __name__=='__main__':raise SystemExit(main())

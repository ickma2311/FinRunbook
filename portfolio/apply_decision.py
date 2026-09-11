#!/usr/bin/env python3
"""Apply one approved decision to a local paper ledger. No broker or model calls."""
import argparse
import copy
import importlib.util
import json
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path
import sys

import refresh as prices

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('account_records',ROOT/'skills/finrunbook-investor/scripts/forward_account.py')
records=importlib.util.module_from_spec(spec);spec.loader.exec_module(records)
D=prices.decimal

def check(ok,message):
    if not ok: raise ValueError(message)

def key(account,decision_id):
    return 'reference-ledger-'+records.digest([account['account_id'],decision_id])[:24]

def approved(account,decision_id,now=None,root=None):
    record=next((x for x in account['decisions'] if x['decision_id']==decision_id),None)
    check(record is not None,'Decision not found')
    for field in ('candidate','validation','review'):
        check(records.digest(record[field])==record[field+'_hash'],'Sealed '+field+' changed')
    c=record['candidate']
    check(c['expert_id']==account['expert_id'] and c['account_id']==account['account_id'],'Identity mismatch')
    check(c['action']=='rebalance','Only an approved rebalance can change cash or holdings')
    checked_at=now or prices.utcnow()
    records.review_status(record['review'],c,checked_at.isoformat())
    check(prices.stamp(record['sealed_at'])<=checked_at,'Decision seal is in the future')
    check(record['validation']['status']=='PASS','Deterministic validation missing')
    check(c['skill_hash']==account['skill_hash']==records.file_hash(account['skill_path']),'Method changed')
    for kind in ('report','evidence'):
        path=prices.source_path(c[kind+'_path']) if root is None else (Path(root)/c[kind+'_path']).resolve()
        if root is not None:check(Path(root).resolve() in path.parents,'Artifact outside repository')
        check(records.file_hash(path)==c[kind+'_hash'],kind+' binding changed')
    check(account['pending_intent_id']==record['intent_id'],'Decision is not the active unapplied intent')
    intent=next((i for i in account['intents'] if i['intent_id']==record['intent_id']),None)
    check(intent is not None and intent['status']=='pending','Intent is no longer pending')
    # A later no_change retains this intent. Replacement changes pending_intent_id.
    check(c['execution_policy'] in ('next_regular_session_open','fresh_reference_price_ledger'),'Unsupported execution policy')
    rules=record['execution_rules']
    check(rules['paper_only'] and rules['long_only'] and rules['whole_shares'] and not rules['leverage'],'Unsupported account rules')
    check(D(rules['fees'])==0 and rules['basket_atomic'],'Unsupported fees or basket policy')
    return record

def apply_observed(account,record,quotes,market,now,started,authorization):
    """Pure transaction: validate and calculate on a copy; errors change nothing."""
    event_id=key(account,record['decision_id'])
    if event_id in account['settlements']:
        return account,account['settlements'][event_id]['receipt']
    check(authorization.strip(),'Explicit timing authorization required')
    check(market['is_open'] and prices.stamp(market['open_at'])<=now<prices.stamp(market['close_at']),
          'Regular market is closed; no fresh-price ledger entry was recorded')
    c=record['candidate'];rules=record['execution_rules'];weights={s:D(w) for s,w in c['target_weights'].items()}
    cap=D(rules['max_security_weight']);slip=D(rules['adverse_slippage_bps'])/10000
    check(0<=slip<1 and all(s in account['universe'] and 0<=w<=cap for s,w in weights.items()) and sum(weights.values())<=1,'Invalid target weights/risk rules')
    symbols=set(weights)|set(account['positions']);check(symbols==set(quotes),'Incomplete price basket')
    check(all(type(n) is int and n>0 for n in account['positions'].values()),'Invalid whole-share holdings')
    cash=D(account['cash']);check(cash>=0,'Invalid cash')
    raw={}
    for s in symbols:
        q=quotes[s];t=prices.stamp(q['price_as_of']);retrieved=prices.stamp(q['retrieved_at'])
        check(q['symbol']==s and q['currency']=='USD' and q['basis']=='completed_1m_close','Wrong price identity/basis')
        check(started<=retrieved<=now and prices.stamp(record['sealed_at'])<t<=retrieved and 0<=(now-t).total_seconds()<=180,'Price is stale, future, or predates decision')
        check(prices.stamp(market['open_at'])<t<=prices.stamp(market['close_at']),'Price outside regular session')
        check(prices.stamp(q['action_coverage_since'])<=prices.stamp(account['observed_at']),'Missing corporate-action coverage')
        since=prices.stamp(account['observed_at']).astimezone(prices.ZoneInfo('America/New_York')).date().isoformat()
        check(not any(x['date']>=since for x in q['actions']),'Corporate action needs reconciliation')
        raw[s]=D(q['price']);check(raw[s]>0,'Invalid price')
    nav=cash+sum(n*raw[s] for s,n in account['positions'].items());check(nav>0,'Invalid NAV')
    targets={s:int((nav*weights.get(s,D(0))/raw[s]).to_integral_value(rounding=ROUND_FLOOR)) for s in symbols}
    fills=[]
    # Whole-share target sizing on the same reference basket; preserve approved slippage.
    for s in sorted(symbols):
        delta=targets[s]-account['positions'].get(s,0)
        if not delta:continue
        side='buy' if delta>0 else 'sell';n=abs(delta);fill=raw[s]*(1+slip if delta>0 else 1-slip)
        limit=c['price_limits'][s]
        check(D(limit['min'])<=fill<=D(limit['max']),'Price limit failed: '+s)
        cash-=delta*fill
        fills.append({'symbol':s,'side':side,'shares':n,'observed_price':str(raw[s]),'fill_price':str(fill),'fees':'0',
                      'slippage_cost':str(n*raw[s]*slip),'price_basis':'completed_1m_close','price_as_of':quotes[s]['price_as_of']})
    holdings={s:n for s,n in targets.items() if n};after=cash+sum(n*raw[s] for s,n in holdings.items())
    check(cash>=0 and after>0,'Insufficient cash after costs; nothing applied')
    check(all(n*raw[s]<=cap*after for s,n in holdings.items()),'Security weight cap exceeded after costs')
    result=copy.deepcopy(account);stamp=now.isoformat()
    change={'type':'execution_policy_amendment','at':stamp,'decision_id':record['decision_id'],
            'old_policy':c['execution_policy'],'new_policy':'fresh_reference_price_ledger','authorization':authorization,
            'note':'User-authorized direct Python paper-ledger update. Original research stays unchanged. No broker execution.',
            'sizing':'floor(current marked NAV * target weight / fresh reference price)',
            'adverse_slippage_bps':rules['adverse_slippage_bps']}
    receipt={'status':'filled','mode':'paper_ledger','event_id':event_id,'execution_key':event_id,
             'decision_id':record['decision_id'],'intent_id':record['intent_id'],'filled_at':stamp,'recorded_at':stamp,
             'fills':fills,'cash':str(cash),'positions':holdings,'nav':str(after),'observations':quotes,
             'session':market,'authorization':authorization,'runtime_sha256':records.file_hash(__file__),
             'account_before_sha256':records.digest(account),
             'note':'Recorded now using dated reference observations, not exchange fills. Prices may be delayed.'}
    result.update(cash=str(cash),positions=holdings,marks={s:str(raw[s]) for s in holdings},
                  observed_at=min((q['price_as_of'] for q in quotes.values()),default=stamp),pending_intent_id=None)
    next(i for i in result['intents'] if i['intent_id']==record['intent_id'])['status']='filled'
    changes=[] if c['execution_policy']=='fresh_reference_price_ledger' else [change]
    result['ledger'].extend(changes+[{'type':'settlement',**copy.deepcopy(receipt)}]);result['revision']+=len(changes)+1
    result['settlements'][event_id]={'observation_hash':records.digest(quotes),'receipt':receipt}
    return result,receipt

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--expert',required=True);p.add_argument('--decision',required=True)
    p.add_argument('--authorization',required=True);a=p.parse_args()
    registry=prices.read(ROOT/'portfolio/experts.json')
    entry=next(x for x in registry['experts'] if x['id']==a.expert)
    path=prices.source_path(entry['account']);output=ROOT/'runs/live-portfolio/applications'/a.expert
    with records.locked(path):
        account=prices.read(path);check(account['account_id']==entry['account_id'] and account['expert_id']==a.expert,'Registry identity mismatch')
        event_id=key(account,a.decision)
        if event_id in account['settlements']:
            receipt=account['settlements'][event_id]['receipt']
            print(json.dumps({'status':'already_applied','receipt':receipt}));return
        decision=approved(account,a.decision);started=prices.utcnow();market=prices.market_context(started)
        check(market['is_open'],'Market closed: no ledger update. Run explicitly when fresh regular-session prices are available.')
        symbols=set(decision['candidate']['target_weights'])|set(account['positions'])
        quotes,errors,timed_out=prices.fetch_shared({s:account['observed_at'] for s in symbols},market,35)
        observed=prices.utcnow()
        record_path=output/(observed.strftime('%Y%m%dT%H%M%S%f')+'-observations.json')
        prices.atomic(record_path,{'quotes':quotes,'errors':errors,'market':market,'retrieved_at':observed.isoformat(),'timed_out':timed_out})
        check(not errors and not timed_out,'Price collection failed; observations saved, account unchanged')
        updated,receipt=apply_observed(account,decision,quotes,market,observed,started,a.authorization)
        # One authoritative atomic commit includes the receipt/idempotency key.
        records.atomic_write(path,updated)
        prices.atomic(output/(event_id+'.json'),receipt)
        print(json.dumps(receipt,indent=2))

if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,StopIteration,OSError,records.Invalid) as exc:
        print(json.dumps({'status':'not_applied','error':str(exc)}));sys.exit(2)

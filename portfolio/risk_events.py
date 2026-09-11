"""Neutral events from already approved numeric limits and fresh saved observations."""
from pathlib import Path
import hashlib
import json
from decimal import Decimal
from datetime import timedelta

import refresh

COVERAGE = [
    {'trigger':'SEC filings','implementation':'official collector','coverage':'source-dependent; HTTP errors remain uncovered'},
    {'trigger':'Fed/BLS releases','implementation':'official collector','coverage':'source-dependent; HTTP errors remain uncovered'},
    {'trigger':'security weight cap','implementation':'saved fresh portfolio + sealed execution rule','coverage':'enrolled own holdings only'},
    {'trigger':'approved order price limit','implementation':'saved fresh observation + pending decision','coverage':'observed symbols only; no quote means uncovered'},
    {'trigger':'volatility / correlation / valuation / news / social','implementation':None,'coverage':'not implemented; no invented thresholds'},
]


def inspect(root, registry, now):
    root=Path(root)
    path=root/'runs/live-portfolio/portfolio.json'
    if not path.exists(): return [], {}, COVERAGE
    snapshot=refresh.read(path)
    if not 0 <= (now-refresh.stamp(snapshot['generated_at'])).total_seconds() <= 600:
        return [], {}, COVERAGE
    entries={e['id']:e for e in registry['experts']}
    events=[]; evidence={}
    for row in snapshot.get('experts',[]):
        entry=entries.get(row['expert_id'],{})
        if not entry.get('account') or not row.get('source'): continue
        raw=(root/entry['account']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['source']['sha256']: continue
        account=json.loads(raw)
        if not account.get('decisions') or row.get('status') not in ('fresh','cash_only'): continue
        record=account['decisions'][-1]
        cap=record.get('execution_rules',{}).get('max_security_weight')
        breaches=[]
        if cap is not None and row.get('total_value') and Decimal(row['total_value'])>0:
            for p in row.get('positions',[]):
                if p.get('status')=='fresh' and p.get('market_value') is not None and Decimal(p['market_value'])/Decimal(row['total_value'])>Decimal(cap):
                    breaches.append(('security_weight',p['symbol'],{'cap':cap,'market_value':p['market_value'],'nav':row['total_value']}))
        pending=next((d for d in account['decisions'] if d.get('intent_id')==account.get('pending_intent_id') and d.get('intent_id')),None)
        if pending:
            for symbol,limit in pending['candidate']['price_limits'].items():
                q=snapshot.get('price_observations',{}).get(symbol)
                if q and 0 <= (now-refresh.stamp(q['price_as_of'])).total_seconds() <= 180:
                    if not Decimal(limit['min'])<=Decimal(q['price'])<=Decimal(limit['max']):
                        breaches.append(('order_reference_price',symbol,{'price':q['price'],'min':limit['min'],'max':limit['max']}))
        for kind,symbol,values in breaches:
            identity=[account['account_id'],account['revision'],kind,symbol]
            event_id='numeric-'+hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
            events.append({'id':event_id,'type':'risk_limit_breach','available_at':now.isoformat(),'expert_ids':[row['expert_id']]})
            evidence[event_id]={'kind':kind,'symbol':symbol,'values':values,'snapshot_path':str(path),
                                'snapshot_id':snapshot['snapshot_id'],'account_sha256':row['source']['sha256'],
                                'price_timestamp':snapshot.get('price_observations',{}).get(symbol,{}).get('price_as_of')}
    return events,evidence,COVERAGE

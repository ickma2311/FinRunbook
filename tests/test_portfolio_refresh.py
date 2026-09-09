import copy
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('portfolio_refresh',REPO/'portfolio/refresh.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
NOW=datetime(2026,9,9,18,30,tzinfo=timezone.utc)
MARKET={'is_open':True,'minimum_price_as_of':'2026-09-09T18:20:00Z','open_at':'2026-09-09T13:30:00Z','close_at':'2026-09-09T20:00:00Z'}

def account(identity='trend',holdings=None):
    return {'schema_version':1,'account_id':identity+'-paper','expert_id':identity,'cash':'85000','initial_capital':'100000',
            'positions':{'GLD':37} if holdings is None else holdings,'observed_at':'2026-09-09T18:13:00Z','revision':3,
            'pending_intent_id':None,'ledger':[{'type':'funding'}]}

def quote():
    return {'symbol':'GLD','price':'405','currency':'USD','price_as_of':'2026-09-09T18:29:00Z','retrieved_at':'2026-09-09T18:29:10Z',
            'action_coverage_since':'2026-09-09T18:13:00Z','actions':[],'source_url':'https://finance.yahoo.com/quote/GLD/history/','basis':'completed_1m_close'}

class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.original_repo=m.REPO;m.REPO=self.root
        (self.root/'portfolio').mkdir();(self.root/'portfolio/dashboard.html').write_text('<html>test</html>')
        self.path=self.root/'account.json';self.path.write_text(json.dumps(account()))
        self.registry={'schema_version':1,'currency':'USD','experts':[{'id':'trend','name':'Trend','account':'account.json','account_id':'trend-paper'}]}
    def tearDown(self):m.REPO=self.original_repo;self.tmp.cleanup()
    def rows(self):return m.load_accounts(self.registry,NOW)
    def test_malformed_decision_isolated_to_one_expert(self):
        broken=account();broken['decisions']=[{'decision_id':'bad','candidate':None}]
        self.path.write_text(json.dumps(broken))
        self.registry['experts'].append({'id':'quality','name':'Quality','account':None})
        rows=self.rows()
        self.assertEqual(rows[0]['status'],'account_error')
        self.assertIsNone(rows[0]['cash'])
        self.assertEqual(rows[1]['status'],'not_started')
    def test_schedule_metadata_is_not_liveness(self):
        path=self.root/'schedule.json'
        path.write_text(json.dumps({'experts':{'trend':{'active_attempt':'task-1','attempts':[]}}}))
        self.registry['experts'][0]['schedule_state']='schedule.json'
        row=self.rows()[0]
        self.assertEqual(row['runtime']['schedule']['active_attempt'],'task-1')
        self.assertEqual(row['runtime']['liveness'],'not_measured')
        self.assertNotIn('research_status',row)
    def test_missing_schedule_does_not_hide_account(self):
        self.registry['experts'][0]['schedule_state']='missing.json'
        row=self.rows()[0]
        self.assertEqual(row['status'],'loaded')
        self.assertIn('error',row['runtime'])
    def test_short_summary_is_bound_to_latest_decision(self):
        a=account();a['decisions']=[{'decision_id':'first','candidate':{'action':'no_change'}}]
        self.path.write_text(json.dumps(a))
        self.registry['experts'][0].update(description='A trend expert',decision_summary='Wait',decision_summary_id='first')
        self.assertEqual(self.rows()[0]['decision_summary'],'Wait')
        a['decisions'].append({'decision_id':'second','candidate':{'action':'rebalance'}})
        self.path.write_text(json.dumps(a))
        self.assertNotIn('decision_summary',self.rows()[0])
    def fills(self, fills, holdings):
        a=account(holdings=holdings)
        for side,n,price,fees,did in fills:
            a['ledger'].append({'type':'settlement','decision_id':did,'filled_at':NOW.isoformat(),
                                'fills':[{'symbol':'GLD','side':side,'shares':n,'fill_price':price,'fees':fees,'slippage_cost':'999'}]})
        self.path.write_text(json.dumps(a));return a
    def test_acquisition_fill_not_market_price_or_slippage_twice(self):
        self.fills([('buy',37,'405.7853848876953125','0','original')],{'GLD':37})
        p=m.project(self.rows(),{'GLD':quote()},{},MARKET,NOW)[0]['positions'][0]
        self.assertEqual(p['average_buy_price'],'405.7853848876953125')
        self.assertEqual(p['cost_basis'],'15014.0592408447265625')
        self.assertEqual(p['unrealized_profit_loss'],'-29.0592408447265625')
        self.assertEqual(p['decision_ids'],['original'])
    def test_multiple_buys_partial_sell_weighted_remaining_cost(self):
        a=self.fills([('buy',10,'100','10','first'),('buy',10,'200','10','second'),('sell',5,'180','3','sell')],{'GLD':15})
        basis,trades=m.acquisition_history(a);p=basis['GLD']
        self.assertEqual(p['average_buy_price'],'150');self.assertEqual(p['cost_basis'],'2265')
        self.assertEqual(p['decision_ids'],['first','second']);self.assertEqual(len(trades),3)
    def test_closed_and_reopened_position_resets_rationale(self):
        a=self.fills([('buy',10,'100','0','old'),('sell',10,'110','1','exit'),('buy',2,'200','2','new')],{'GLD':2})
        p=m.acquisition_history(a)[0]['GLD'];self.assertEqual(p['decision_ids'],['new']);self.assertEqual(p['cost_basis'],'402')
    def test_missing_fills_withholds_cost_not_market_valuation(self):
        p=m.project(self.rows(),{'GLD':quote()},{},MARKET,NOW)[0]['positions'][0]
        self.assertIsNone(p['cost_basis']);self.assertIsNone(p['unrealized_profit_loss']);self.assertEqual(p['market_value'],'14985')
    def test_missing_quote_preserves_known_cost(self):
        self.fills([('buy',37,'400','0','original')],{'GLD':37})
        p=m.project(self.rows(),{},{},MARKET,NOW)[0]['positions'][0]
        self.assertEqual(p['cost_basis'],'14800');self.assertIsNone(p['unrealized_profit_loss'])
    def test_unreconciled_and_unsupported_ledger_withhold_cost(self):
        a=self.fills([('buy',36,'400','0','original')],{'GLD':37})
        self.assertIsNone(m.acquisition_history(a)[0]['GLD']['cost_basis'])
        a['ledger'].append({'type':'split'});self.assertIn('Unsupported',m.acquisition_history(a)[0]['GLD']['cost_basis_error'])
    def test_evidence_bound_to_exact_decision_not_generic_report(self):
        content=self.root/'bound.json';content.write_text('{"original":true}')
        digest=m.hashlib.sha256(content.read_bytes()).hexdigest()
        a=account();a['decisions']=[{'decision_id':'first','candidate':{'rationale':'Original reason',
            'report_path':str(content),'report_hash':digest,'evidence_path':str(content),'evidence_hash':digest}}]
        rows=[{'decisions':m.decision_history(a),'source':{'sha256':'test'}}];out=self.root/'out'
        m.publish_decision_evidence(rows,out);d=rows[0]['decisions'][0]
        self.assertEqual(d['report_status'],'sealed_hash_verified')
        self.assertEqual((out/d['report_url']).read_bytes(),content.read_bytes())
        self.assertEqual(m.read(out/d['record_url'])['decision']['candidate']['rationale'],'Original reason')
        content.write_text('{"changed":true}')
        rows=[{'decisions':m.decision_history(a)}];m.publish_decision_evidence(rows,out)
        self.assertIsNone(rows[0]['decisions'][0]['report_url']);self.assertIn('mismatch',rows[0]['decisions'][0]['report_status'])
        self.assertEqual(m.read(out/d['report_url']),{'original':True})
    def test_timing_amendment_matches_decision_only(self):
        a=account();a['decisions']=[{'decision_id':'first','candidate':{'rationale':'Original'}}]
        a['ledger'] += [{'type':'execution_policy_amendment','decision_id':'first','new_policy':'intraday'},
                        {'type':'execution_policy_amendment','decision_id':'other','new_policy':'different'}]
        d=m.decision_history(a)[0];self.assertEqual(len(d['execution_changes']),1);self.assertEqual(d['rationale'],'Original')
    def test_research_history_preserves_each_decision_version(self):
        a=account();a['decisions']=[]
        for i in range(3):
            path=self.root/f'report-{i}.json';path.write_text(json.dumps({'meta':{'title':f'Report {i}'},'body':'<script>bad()</script>'}))
            digest=m.hashlib.sha256(path.read_bytes()).hexdigest()
            a['decisions'].append({'decision_id':str(i),'sealed_at':f'2026-09-0{i+1}T10:00:00Z',
                'candidate':{'report_path':str(path),'report_hash':digest}})
        rows=[{'name':'Trend','decisions':m.decision_history(a),'report_url':'wrong-latest.html'}]
        out=self.root/'out';m.publish_decision_evidence(rows,out);m.publish_research_history(rows,out)
        history=rows[0]['research_history']
        self.assertEqual([x['title'] for x in history],['Report 2','Report 1','Report 0'])
        self.assertEqual(len({x['report_url'] for x in history}),3)
        html=(out/history[0]['report_url']).read_text()
        self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html)
        self.assertNotIn('wrong-latest',html)
        self.assertEqual(rows[0]['decisions'][0]['reading_url'],history[-1]['report_url'])
    def test_research_history_includes_untraded_attempt_and_deduplicates(self):
        path=self.root/'research.json';path.write_text('{"title":"Research without a trade"}')
        digest=m.hashlib.sha256(path.read_bytes()).hexdigest()
        attempt={'id':'attempt1','outcome':'completed','report':{'path':str(path),'sha256':digest}}
        row={'name':'Trend','runtime':{'schedule':{'attempts':[attempt,attempt]}}}
        m.publish_research_history([row],self.root/'out')
        self.assertEqual(len(row['research_history']),1)
        self.assertIsNone(row['research_history'][0]['decision_id'])
    def test_research_history_hash_failure_is_not_report_success(self):
        path=self.root/'research.json';path.write_text('{"title":"Changed"}')
        row={'runtime':{'schedule':{'attempts':[{'id':'bad','report':{'path':str(path),'sha256':'0'*64}}]}}}
        m.publish_research_history([row],self.root/'out')
        item=row['research_history'][0]
        self.assertIsNone(item['report_url']);self.assertIn('mismatch',item['availability_error'])
    def test_shared_research_has_multiple_decision_references_not_duplicate_reports(self):
        path=self.root/'research.json';path.write_text('{"title":"Shared research"}')
        digest=m.hashlib.sha256(path.read_bytes()).hexdigest()
        a=account();a['decisions']=[{'decision_id':i,'candidate':{'report_path':str(path),'report_hash':digest}} for i in ('a','b')]
        row={'decisions':m.decision_history(a)};out=self.root/'out'
        m.publish_decision_evidence([row],out);m.publish_research_history([row],out)
        self.assertEqual(len(row['research_history']),1)
        self.assertEqual(row['research_history'][0]['decision_ids'],['a','b'])
        self.assertEqual(row['decisions'][0]['reading_url'],row['decisions'][1]['reading_url'])
    def test_account_projection_math(self):
        r=m.project(self.rows(),{'GLD':quote()},{},MARKET,NOW)[0]
        self.assertEqual(r['total_value'],'99985');self.assertEqual(r['holdings_value'],'14985');self.assertEqual(r['profit_loss'],'-15');self.assertEqual(r['status'],'fresh')
    def test_blocked_research_is_not_a_cash_decision(self):
        self.path.write_text(json.dumps(account(holdings={})))
        self.registry['experts'][0].update(research_status='blocked',research_note='Missing critical valuation inputs')
        r=m.project(self.rows(),{},{},MARKET,NOW)[0]
        self.assertEqual(r['status'],'cash_only');self.assertEqual(r['research_status'],'blocked')
        self.assertEqual(r['decisions'],[]);self.assertIsNone(r['pending_decision_id'])
    def test_pending_decision_is_linked_without_creating_a_fill(self):
        a=account(holdings={});a['pending_intent_id']='intent-1'
        a['intents']=[{'intent_id':'intent-1','decision_id':'decision-1'}]
        self.path.write_text(json.dumps(a));r=self.rows()[0]
        self.assertEqual(r['pending_decision_id'],'decision-1');self.assertEqual(r['fill_count'],0)
    def test_cash_only_no_quotes(self):
        self.path.write_text(json.dumps(account(holdings={})));r=m.project(self.rows(),{},{},MARKET,NOW)[0]
        self.assertEqual(r['status'],'cash_only');self.assertEqual(r['holdings_value'],'0');self.assertEqual(r['total_value'],'85000')
    def test_unstarted_not_funded(self):
        self.registry['experts'].append({'id':'macro','name':'Macro','account':None});r=m.project(self.rows(),{},{},MARKET,NOW)[1]
        self.assertEqual(r['status'],'not_started');self.assertIsNone(r['cash']);self.assertIsNone(r['total_value'])
    def test_missing_price_not_zero(self):
        r=m.project(self.rows(),{},{},MARKET,NOW)[0];self.assertIsNone(r['total_value']);self.assertEqual(r['status'],'unavailable')
    def test_stale_keeps_original_time(self):
        q=quote();q['price_as_of']='2026-09-09T18:15:00Z';r=m.project(self.rows(),{'GLD':q},{},MARKET,NOW)[0]
        self.assertEqual(r['status'],'stale');self.assertEqual(r['positions'][0]['price_as_of'],'2026-09-09T18:15:00+00:00')
    def test_failed_fetch_uses_labelled_cache(self):
        r=m.project(self.rows(),{'GLD':quote()},{'GLD':'timeout'},MARKET,NOW)[0];self.assertEqual(r['status'],'stale');self.assertTrue(r['warnings'])
    def test_future_quote_rejected(self):
        q=quote();q['price_as_of']='2026-09-10T18:29:00Z';r=m.project(self.rows(),{'GLD':q},{},MARKET,NOW)[0];self.assertIsNone(r['total_value'])
    def test_old_price_before_balance_rejected(self):
        q=quote();q['price_as_of']='2026-09-09T18:00:00Z';r=m.project(self.rows(),{'GLD':q},{},MARKET,NOW)[0];self.assertIsNone(r['total_value'])
    def test_foreign_currency_rejected(self):
        q=quote();q['currency']='EUR';r=m.project(self.rows(),{'GLD':q},{},MARKET,NOW)[0];self.assertEqual(r['status'],'unavailable')
    def test_split_withholds_total(self):
        q=quote();q['actions']=[{'date':'2026-09-10','split':2,'dividend':0}]
        r=m.project(self.rows(),{'GLD':q},{},MARKET,NOW)[0];self.assertIsNone(r['total_value'])
    def test_dividend_withholds_total(self):
        q=quote();q['actions']=[{'date':'2026-09-10','split':0,'dividend':1}]
        r=m.project(self.rows(),{'GLD':q},{},MARKET,NOW)[0];self.assertIsNone(r['total_value'])
    def test_external_flows_no_simple_return(self):
        a=account();a['ledger'].append({'type':'deposit'});self.path.write_text(json.dumps(a));r=m.project(self.rows(),{'GLD':quote()},{},MARKET,NOW)[0]
        self.assertIsNotNone(r['total_value']);self.assertIsNone(r['profit_loss'])
    def test_missing_account_isolated(self):
        self.registry['experts'].append({'id':'other','name':'Other','account':'missing.json','account_id':'other'});rows=self.rows()
        self.assertEqual(rows[0]['status'],'loaded');self.assertEqual(rows[1]['status'],'account_error')
    def test_mismatched_identity_rejected(self):
        self.registry['experts'][0]['account_id']='wrong';self.assertEqual(self.rows()[0]['status'],'account_error')
    def test_nan_balance_rejected(self):
        a=account();a['cash']='NaN';self.path.write_text(json.dumps(a));self.assertEqual(self.rows()[0]['status'],'account_error')
    def test_decimal_strings_no_exponent(self):
        a=account(holdings={});a.update(cash='100000.000000000000000000',initial_capital='1E+5');self.path.write_text(json.dumps(a))
        row=m.project(self.rows(),{},{},MARKET,NOW)[0]
        m.validate_snapshot({'schema_version':1,'currency':'USD','mode':'valuation_only','experts':[row]})
        self.assertNotIn('E',row['profit_loss']);self.assertEqual(m.decimal(row['profit_loss']),0)
    def test_inconsistent_snapshot_rejected(self):
        row=m.project(self.rows(),{'GLD':quote()},{},MARKET,NOW)[0];row['total_value']='1'
        with self.assertRaises(ValueError):m.validate_snapshot({'schema_version':1,'currency':'USD','mode':'valuation_only','experts':[row]})
    def test_duplicate_expert_config_rejected(self):
        self.registry['experts']*=2
        with self.assertRaises(ValueError):self.rows()
    def test_negative_shares_rejected(self):
        self.path.write_text(json.dumps(account(holdings={'GLD':-1})));self.assertEqual(self.rows()[0]['status'],'account_error')
    def test_closed_price_not_live(self):
        market={**MARKET,'is_open':False};r=m.project(self.rows(),{'GLD':quote()},{},market,NOW)[0];self.assertEqual(r['status'],'market_closed')
    def test_empty_fetch_no_subprocess(self):
        with patch.object(m.subprocess,'run') as p:self.assertEqual(m.fetch_shared({},MARKET,1),({},{},False));p.assert_not_called()
    def test_timeout_preserves_partial_results(self):
        partial=json.dumps({'symbol':'GLD','quote':quote()})+'\n'
        with patch.object(m.subprocess,'run',side_effect=subprocess.TimeoutExpired('worker',1,output=partial)):
            q,e,t=m.fetch_shared({'GLD':'a','SPY':'a'},MARKET,1)
        self.assertIn('GLD',q);self.assertIn('SPY',e);self.assertTrue(t)
    def test_end_to_end_readonly_shared_prices(self):
        second=self.root/'second.json';second.write_text(json.dumps(account('quality')))
        self.registry['experts'].append({'id':'quality','name':'Quality','account':'second.json','account_id':'quality-paper'})
        registry=self.root/'registry.json';registry.write_text(json.dumps(self.registry));before=self.path.read_bytes();out=self.root/'output'
        with patch.object(m,'utcnow',return_value=NOW),patch.object(m,'market_context',return_value=MARKET),patch.object(m,'fetch_shared',return_value=({'GLD':quote()},{},False)) as fetch:
            result=m.run(registry,out)
        self.assertEqual(fetch.call_args.args[0],{'GLD':'2026-09-09T18:13:00+00:00'});self.assertEqual(self.path.read_bytes(),before)
        saved=m.read(out/'portfolio.json');self.assertEqual(len(saved['experts']),2);self.assertEqual(result['status'],'ok');self.assertTrue((out/'index.html').exists())
    def test_account_change_during_fetch(self):
        registry=self.root/'registry.json';registry.write_text(json.dumps(self.registry))
        def fetch(*args):
            a=account();a['revision']+=1;self.path.write_text(json.dumps(a));return {'GLD':quote()},{},False
        with patch.object(m,'utcnow',return_value=NOW),patch.object(m,'market_context',return_value=MARKET),patch.object(m,'fetch_shared',side_effect=fetch):m.run(registry,self.root/'out')
        r=m.read(self.root/'out/portfolio.json')['experts'][0];self.assertEqual(r['status'],'account_changed');self.assertIsNone(r['total_value'])
    def test_overlapping_refresh_skips(self):
        out=self.root/'out';out.mkdir()
        with (out/'.refresh.lock').open('a') as f:
            m.fcntl.flock(f,m.fcntl.LOCK_EX|m.fcntl.LOCK_NB)
            self.assertEqual(m.run(self.root/'not-read.json',out)['status'],'skipped_already_running')
    def test_real_calendar_holiday_and_early_close(self):
        m.REPO=self.original_repo
        holiday=m.market_context(datetime(2026,9,7,18,tzinfo=timezone.utc));self.assertFalse(holiday['is_open']);self.assertEqual(holiday['session'],'2026-09-04')
        early=m.market_context(datetime(2026,11,27,19,tzinfo=timezone.utc));self.assertFalse(early['is_open']);self.assertEqual(m.stamp(early['close_at']).hour,18)

if __name__=='__main__':unittest.main()

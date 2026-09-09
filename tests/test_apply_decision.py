import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from datetime import datetime,timezone,timedelta

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'portfolio'))
import apply_decision as m

NOW=datetime(2026,9,9,19,55,tzinfo=timezone.utc)
MARKET={'is_open':True,'open_at':'2026-09-09T13:30:00Z','close_at':'2026-09-09T20:00:00Z'}

class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.a={'account_id':'test','expert_id':'test','cash':'100000','positions':{},'universe':['SPY','IEF'],
                'observed_at':'2026-09-09T18:00:00Z','intents':[{'intent_id':'i','status':'pending'}],
                'pending_intent_id':'i','settlements':{},'ledger':[],'revision':1}
        self.r={'decision_id':'d','intent_id':'i','sealed_at':'2026-09-09T19:00:00Z',
                'candidate':{'target_weights':{'SPY':'.10','IEF':'.10'},'execution_policy':'next_regular_session_open',
                             'price_limits':{'SPY':{'min':700,'max':800},'IEF':{'min':85,'max':100}}},
                'execution_rules':{'max_security_weight':'.30','adverse_slippage_bps':10}}
        self.q={s:{'symbol':s,'currency':'USD','basis':'completed_1m_close','price':str(p),
                    'price_as_of':'2026-09-09T19:54:00Z','retrieved_at':'2026-09-09T19:54:59Z',
                    'action_coverage_since':'2026-09-09T18:00:00Z','actions':[]} for s,p in [('SPY',765),('IEF',92)]}
    def apply(self,a=None):return m.apply_observed(a or self.a,self.r,self.q,MARKET,NOW,NOW-timedelta(seconds=5),'User authorized paper ledger')
    def test_atomic_purchases_and_cost(self):
        old=copy.deepcopy(self.a);a,r=self.apply()
        self.assertEqual(self.a,old);self.assertEqual(a['positions'],{'IEF':108,'SPY':13})
        self.assertEqual(m.D(a['cash']),m.D('80099.119'));self.assertIsNone(a['pending_intent_id'])
        self.assertEqual(len(r['fills']),2);self.assertEqual(a['revision'],3)
    def test_idempotent(self):
        a,r=self.apply();again,r2=self.apply(a);self.assertEqual(a,again);self.assertEqual(r,r2)
    def test_missing_price(self):
        del self.q['IEF']
        with self.assertRaises(ValueError):self.apply()
    def test_stale_and_future(self):
        for stamp in ['2026-09-09T19:40:00Z','2026-09-09T19:56:00Z']:
            self.q['SPY']['price_as_of']=stamp
            with self.assertRaises(ValueError):self.apply()
    def test_closed_market(self):
        with self.assertRaises(ValueError):m.apply_observed(self.a,self.r,self.q,{**MARKET,'is_open':False},NOW,NOW-timedelta(seconds=5),'yes')
    def test_price_limit_atomic(self):
        old=copy.deepcopy(self.a);self.r['candidate']['price_limits']['SPY']['max']=760
        with self.assertRaises(ValueError):self.apply()
        self.assertEqual(old,self.a)
    def test_split_blocks(self):
        self.q['IEF']['actions']=[{'date':'2026-09-09','split':2}]
        with self.assertRaises(ValueError):self.apply()
    def test_target_cap(self):
        self.r['candidate']['target_weights']['IEF']='.31'
        with self.assertRaises(ValueError):self.apply()
    def test_sell_and_buy(self):
        self.a.update(cash='50000',positions={'SPY':50})
        a,r=self.apply();self.assertTrue(any(x['side']=='sell' for x in r['fills']));self.assertGreater(m.D(a['cash']),0)
    def test_empty_targets_liquidate(self):
        self.a.update(cash='0',positions={'SPY':10});self.r['candidate']['target_weights']={};del self.q['IEF']
        a,r=self.apply();self.assertEqual(a['positions'],{});self.assertEqual(m.D(a['cash']),m.D('7642.350'))
    def test_empty_authorization(self):
        with self.assertRaises(ValueError):m.apply_observed(self.a,self.r,self.q,MARKET,NOW,NOW-timedelta(seconds=5),'')

if __name__=='__main__':unittest.main()

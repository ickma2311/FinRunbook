from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'portfolio'))
import risk_events as m


class RiskEventsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.now=datetime(2026,9,11,14,0,10,tzinfo=timezone.utc)
        self.account={'account_id':'defensive','expert_id':'defensive','revision':1,'pending_intent_id':None,
                      'decisions':[{'execution_rules':{'max_security_weight':'.30'}}]}
        self.ap=self.root/'account.json';self.ap.write_text(json.dumps(self.account))
        self.registry={'experts':[{'id':'defensive','account':'account.json'}]}
        self.path=self.root/'runs/live-portfolio/portfolio.json';self.path.parent.mkdir(parents=True)
        self.snap={'generated_at':(self.now-timedelta(seconds=2.5)).isoformat(),'snapshot_id':'test',
                   'experts':[{'expert_id':'defensive','status':'fresh','source':{'sha256':hashlib.sha256(self.ap.read_bytes()).hexdigest()},
                               'total_value':'100000','positions':[{'symbol':'SPY','status':'fresh','market_value':'31000'}]}]}
        self.path.write_text(json.dumps(self.snap))
    def tearDown(self):self.tmp.cleanup()
    def test_only_declared_limit_produces_event(self):
        events,evidence,coverage=m.inspect(self.root,self.registry,self.now)
        self.assertEqual(events[0]['type'],'risk_limit_breach')
        self.assertEqual(evidence[events[0]['id']]['values']['cap'],'.30')
        self.assertTrue(any(c['implementation'] is None for c in coverage))
    def test_stale_prices_never_trigger(self):
        self.assertEqual(m.inspect(self.root,self.registry,self.now+timedelta(minutes=11))[0],[])
    def test_changed_account_is_not_mixed_with_old_prices(self):
        self.ap.write_text('{}')
        self.assertEqual(m.inspect(self.root,self.registry,self.now)[0],[])
    def test_below_limit_is_not_event(self):
        self.snap['experts'][0]['positions'][0]['market_value']='29999';self.path.write_text(json.dumps(self.snap))
        self.assertEqual(m.inspect(self.root,self.registry,self.now)[0],[])


if __name__=='__main__': unittest.main()

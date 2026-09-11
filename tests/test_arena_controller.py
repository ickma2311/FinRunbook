import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'portfolio'))
import controller as m
import service


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.now=datetime(2026,9,11,14,0,tzinfo=timezone.utc)
        self.clock=lambda:self.now
        self.policy=self.root/'skills/finrunbook-investor/references/forward-profiles.json'
        profile={'id':'quality','regular_interval_hours':168,'min_interval_hours':12,'max_runs_per_day':2,'retry_cooldown_hours':6,'event_types':['earnings']}
        self.write(self.policy,{'schema_version':1,'timezone':'America/New_York','experts':[profile]})
        self.schedule=self.root/'schedule.json'
        self.write(self.schedule,{'schema_version':1,'experts':{'quality':m.schedule.empty_state()}})
        self.skill=self.root/'method.md';self.skill.write_text('Synthetic plumbing test, not expert research.')
        self.account=self.root/'account.json'
        self.write(self.account,m.accounts.init_account('quality','fixture',self.skill,'2026-09-11T13:00:00Z'))
        self.registry=self.root/'registry.json'
        self.write(self.registry,{'schema_version':1,'currency':'USD','experts':[{'id':'quality','account':'account.json','account_id':'fixture','schedule_state':'schedule.json'}]})
        self.c=m.Controller(self.root,self.registry,clock=self.clock)
        self.c.check()
        self.job=self.c.claim('quality','Synthetic isolated integration verification')['job_id']
    def tearDown(self): self.tmp.cleanup()
    def write(self,path,data): path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data));return str(path)
    def observation(self,worker,status='completed'):
        return {'worker_id':worker,'tool':'synthetic-test-only','observed_at':self.now.isoformat(),'status':status}
    def research(self,action='no_change'):
        output=Path(self.c.load()['jobs'][self.job]['output'])
        evidence=self.write(output/'evidence.json',{'sources':[{'available_at':'2026-09-11T13:10:00Z','retrieved_at':'2026-09-11T13:11:00Z'}]})
        report=self.write(output/'report.json',{'fixture':True})
        html=output/'report.html';html.write_text('<p>Synthetic test only</p>')
        account=m.accounts.read(self.account)
        candidate={'expert_id':'quality','account_id':'fixture','task_id':'author-fixture','skill_hash':account['skill_hash'],
                   'report_path':report,'report_hash':m.accounts.file_hash(report),'evidence_path':evidence,'evidence_hash':m.accounts.file_hash(evidence),
                   'evidence_cutoff':'2026-09-11T13:12:00Z','account_snapshot_hash':m.accounts.digest(m.accounts.snapshot(account)),
                   'action':action,'rationale':'Synthetic test only','next_review_condition':'Test only'}
        if action=='rebalance':
            candidate.update(execution_policy='fresh_reference_price_ledger',target_weights={'MSFT':'.10'},
                             price_limits={'MSFT':{'min':'50','max':'200'}},replaces_intent_id=None)
        candidate_path=self.write(output/'candidate.json',candidate)
        result={'status':'completed','native_observation':self.observation('author-fixture'),
                'artifacts':{'candidate':candidate_path,'report':report,'evidence':evidence,'html':str(html)}}
        self.c.record_result(self.job,'research',result)
        return candidate,result
    def review(self,candidate):
        out=Path(self.c.load()['jobs'][self.job]['output'])
        review={'candidate_hash':m.accounts.digest(candidate),'author_task_id':'author-fixture','reviewer_task_id':'reviewer-fixture',
                'parent_history_inherited':False,'reviewed_at':'2026-09-11T13:50:00Z',
                'findings':[{'id':k,'required':True,'status':'PASS'} for k in ('material_evidence','calculations','report_decision')]}
        path=self.write(out/'review.json',review)
        self.c.record_result(self.job,'review',{'status':'completed','native_observation':self.observation('reviewer-fixture'),'artifacts':{'review':path}})
    def test_duplicate_claim_reuses_attempt(self):
        self.assertEqual(self.job,self.c.claim('quality','test')['job_id'])
        self.assertEqual(len(m.accounts.read(self.schedule)['experts']['quality']['attempts']),1)
    def test_review_capacity_recovery_does_not_repeat_research(self):
        candidate,result=self.research()
        self.c.record_result(self.job,'review',{'status':'retryable','error_kind':'capacity','error':'No slot'})
        self.assertEqual(self.c.claim('quality','test')['stage'],'review')
        self.assertEqual(self.c.load()['jobs'][self.job]['stages']['research']['result_hash'],m.schedule.canonical_hash(result))
        self.review(candidate)
        with patch.object(m.refresh,'run',return_value={'status':'ok'}):self.c.finalize(self.job)
        self.assertEqual(len(m.accounts.read(self.account)['decisions']),1)
    def test_author_cannot_self_review(self):
        self.research()
        with self.assertRaisesRegex(ValueError,'Independent'):
            self.c.record_result(self.job,'review',{'status':'running','native_observation':self.observation('author-fixture','running')})
    def test_old_observation_is_unknown_not_cleared(self):
        self.c.record_result(self.job,'research',{'status':'running','native_observation':self.observation('author-fixture','running')})
        self.now+=timedelta(minutes=10)
        self.assertEqual(self.c.status()['jobs'][0]['stage_state']['liveness'],'unknown')
        self.assertEqual(m.accounts.read(self.schedule)['experts']['quality']['active_attempt'],self.job)
    def test_state_projection_loss_recovers_journal(self):
        state=self.c.load();self.c.path.unlink()
        self.assertEqual(self.c.load(),state)
    def test_crash_after_claim_journal_recovers_scheduler(self):
        # Model crash between prepared journal and scheduler write.
        self.write(self.schedule,{'schema_version':1,'experts':{'quality':m.schedule.empty_state()}})
        self.c.claim('quality','test')
        self.assertEqual(m.accounts.read(self.schedule)['experts']['quality']['active_attempt'],self.job)
    def test_seal_crash_recovers_without_duplicate(self):
        candidate,_=self.research();self.review(candidate)
        original=self.c.save
        def crash(state,event,detail=None):
            if event=='approval':raise OSError('crash after account write')
            return original(state,event,detail)
        with patch.object(self.c,'save',side_effect=crash):
            with self.assertRaises(OSError):self.c.finalize(self.job)
        self.assertEqual(len(m.accounts.read(self.account)['decisions']),1)
        with patch.object(m.refresh,'run',return_value={'status':'ok'}):self.c.finalize(self.job)
        self.assertEqual(len(m.accounts.read(self.account)['decisions']),1)
    def test_publication_failure_resumes_only_publication(self):
        candidate,_=self.research();self.review(candidate)
        with patch.object(m.refresh,'run',side_effect=OSError('renderer failed')):self.c.finalize(self.job)
        job=self.c.load()['jobs'][self.job]
        self.assertEqual(job['stages']['publication']['status'],'retryable')
        self.assertEqual(m.accounts.read(self.schedule)['experts']['quality']['active_attempt'],None)
        with patch.object(m.refresh,'run',return_value={'status':'ok'}):self.c.finalize(self.job)
        self.assertEqual(len(m.accounts.read(self.account)['decisions']),1)
    def test_changed_artifacts_block_sealing(self):
        candidate,_=self.research();self.review(candidate)
        Path(candidate['report_path']).write_text('changed')
        with self.assertRaisesRegex(ValueError,'changed'):self.c.finalize(self.job)
        self.assertEqual(m.accounts.read(self.account)['decisions'],[])
    def test_health_staleness(self):
        self.assertEqual(service.health(self.c)['status'],'degraded')
        with m.schedule.locked(self.c.path):
            state=self.c.load();state['service']={'finished_at':self.now.isoformat(),'valuation':{'status':'ok'}};self.c.save(state,'test')
        self.assertEqual(service.health(self.c)['status'],'ok')
        self.now+=timedelta(minutes=8)
        self.assertEqual(service.health(self.c)['status'],'degraded')

    def test_blocked_finish_crash_is_reconciled_on_identical_result(self):
        result={'status':'blocked','error':'Missing critical evidence'}
        with patch.object(self.c,'_finish_schedule',side_effect=OSError('crash')):
            with self.assertRaises(OSError):self.c.record_result(self.job,'research',result)
        self.c.record_result(self.job,'research',result)
        self.assertIsNone(m.accounts.read(self.schedule)['experts']['quality']['active_attempt'])

    def test_registry_stop_blocks_resume(self):
        registry=m.accounts.read(self.registry);registry['experts'][0]['stopped']=True
        self.write(self.registry,registry)
        with self.assertRaisesRegex(ValueError,'stopped'):self.c.claim('quality','test')

    def test_scheduler_stop_blocks_approval(self):
        candidate,_=self.research();self.review(candidate)
        state=m.accounts.read(self.schedule);state['experts']['quality']['stop_requested']=True
        self.write(self.schedule,state)
        with self.assertRaisesRegex(ValueError,'stopped'):self.c.finalize(self.job)
        self.assertEqual(m.accounts.read(self.account)['decisions'],[])

    def test_queued_rebalance_through_service_exactly_once(self):
        candidate,_=self.research('rebalance');self.review(candidate)
        with patch.object(m.refresh,'run',return_value={'status':'ok'}):self.c.finalize(self.job)
        initial=m.accounts.read(self.account)
        self.assertIsNotNone(initial['pending_intent_id'])
        self.now+=timedelta(minutes=2)
        quote={'symbol':'MSFT','price':'100','currency':'USD','basis':'completed_1m_close',
               'price_as_of':(self.now-timedelta(minutes=1)).isoformat(),'retrieved_at':self.now.isoformat(),
               'action_coverage_since':'2026-09-11T13:00:00Z','actions':[]}
        with patch.object(m.refresh,'fetch_shared',return_value=({'MSFT':quote},{},False)),patch.object(m.refresh,'run',return_value={'status':'ok'}):
            self.c.service_tick();self.c.service_tick()
        account=m.accounts.read(self.account)
        self.assertEqual(account['positions'],{'MSFT':100})
        self.assertEqual(len(account['settlements']),1)
        self.assertEqual(self.c.load()['jobs'][self.job]['stages']['execution']['status'],'applied')

    def test_execution_failure_does_not_stop_valuation(self):
        import execution_queue
        with patch.object(execution_queue,'tick',side_effect=ValueError('queue unavailable')),patch.object(m.refresh,'run',return_value={'status':'ok'}) as valuator:
            result=self.c.service_tick()
        valuator.assert_called_once()
        self.assertEqual(result['execution']['status'],'error')
        self.assertEqual(service.health(self.c)['status'],'degraded')


class BarTests(unittest.TestCase):
    def test_inactive_final_bar_and_stale_fallback(self):
        import pandas as pd
        from refresh import newest_valid_bar
        frame=pd.DataFrame([{'Open':100,'High':101,'Low':99,'Close':100,'Volume':100},
                            {'Open':100,'High':101,'Low':99,'Close':100,'Volume':0}],
                           index=pd.to_datetime(['2026-09-11T14:00Z','2026-09-11T14:01Z']))
        market={'minimum_price_as_of':'2026-09-11T13:59Z'}
        self.assertEqual(newest_valid_bar(frame,market)[1].minute,1)
        with self.assertRaises(ValueError):newest_valid_bar(frame,{'minimum_price_as_of':'2026-09-11T14:02Z'})


if __name__=='__main__': unittest.main()

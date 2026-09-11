#!/usr/bin/env python3
"""Durable Arena coordination. Dispatch native workers externally; never call a model."""
import argparse
import copy
from datetime import timedelta
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid

import refresh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/finrunbook-hourly/scripts'))
import check_due

schedule = check_due.schedule
spec = importlib.util.spec_from_file_location('arena_accounts', ROOT / 'skills/finrunbook-investor/scripts/forward_account.py')
accounts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(accounts)
STAGES = ('research', 'review', 'approval', 'execution', 'publication')


class Controller:
    def __init__(self, root=ROOT, registry=None, directory=None, clock=None):
        self.root = Path(root).resolve()
        self.registry = Path(registry or self.root / 'portfolio/experts.json').resolve()
        self.directory = Path(directory or self.root / 'runs/arena-controller').resolve()
        self.path = self.directory / 'state.json'
        self.clock = clock or schedule.now_utc

    def resolve(self, path):
        return check_due.resolve(self.root, path)

    def load(self):
        # Immutable revisions are the write-ahead log. Recover a lost projection.
        receipts = sorted((self.directory / 'receipts').glob('*.json'))
        if receipts:
            receipt = schedule.read_json(receipts[-1])
            if schedule.canonical_hash(receipt['state']) != receipt['state_sha256']:
                raise ValueError('Controller receipt checksum mismatch')
            return receipt['state']
        if self.path.exists():
            raise ValueError('Controller projection exists without its durable receipts')
        return {'schema_version': 1, 'revision': 0, 'jobs': {}, 'last_check': None,
                'service': {}, 'source_health': None}

    def save(self, state, event, detail=None):
        state['revision'] += 1
        state['updated_at'] = schedule.iso(self.clock())
        receipt = {'event': event, 'at': state['updated_at'], 'detail': detail,
                   'state': copy.deepcopy(state), 'state_sha256': schedule.canonical_hash(state)}
        destination = self.directory / 'receipts' / f"{state['revision']:012d}.json"
        schedule.write_json(destination, receipt, exclusive=True)
        schedule.write_json(self.path, state)
        return receipt

    def entry(self, expert):
        return next(x for x in schedule.read_json(self.registry)['experts'] if x['id'] == expert)

    def require_not_stopped(self, entry):
        own=schedule.state_at(self.resolve(entry['schedule_state']))['experts'][entry['id']]
        if entry.get('stopped') or entry.get('enabled') is False or any(own.get(k) for k in ('stopped','stop_requested','paused')):
            raise ValueError('Expert explicitly stopped')

    def _check(self, events=None, collect=False):
        policy = self.root / 'skills/finrunbook-investor/references/forward-profiles.json'
        collection = None
        if collect:
            from collect_events import collect as collect_sources
            try:
                config = schedule.read_json(self.root / 'skills/finrunbook-hourly/references/event-sources.json')
                collection = collect_sources(self.root, config, self.registry, policy,
                                             self.root / 'runs/hourly-event-cache/state.json')
                events = Path(collection['events_path'])
            except (ValueError, OSError, KeyError) as exc:
                collection = {'status': 'error', 'error': str(exc), 'sources': [], 'error_count': 1}
        check = check_due.check_registry(self.root, self.registry, policy, events, self.clock())
        check['collection'] = collection
        return check

    def check(self, events=None, collect=False):
        result = self._check(events, collect)
        from risk_events import inspect
        try:
            numeric, evidence, coverage = inspect(self.root, accounts.read(self.registry), self.clock())
        except (ValueError, OSError, KeyError, TypeError) as exc:
            numeric, evidence, coverage = [], {}, [{'trigger': 'numeric limits', 'coverage': 'unavailable', 'error': str(exc)}]
        # Preserve first observed availability and evidence across hourly checks.
        with schedule.locked(self.path):
            state = self.load()
            saved = state.setdefault('numeric_events', {})
            for item in numeric:
                if item['id'] not in saved:
                    saved[item['id']] = {'event': item, 'evidence': evidence[item['id']]}
            if saved:
                combined = {e['id']:e for e in result['events']}
                combined.update({k:v['event'] for k,v in saved.items()})
                event_path=self.directory/'event-batches'/(uuid.uuid4().hex+'.json')
                schedule.write_json(event_path,list(combined.values()),exclusive=True)
                augmented=self._check(event_path,False)
                augmented['collection']=result['collection']
                result=augmented
            result['trigger_coverage']=coverage
            state['last_check'] = result
            if result['collection'] is not None:
                state['source_health'] = result['collection']
            self.save(state, 'check')
            for job in state['jobs'].values():
                if job['status'] in ('blocked', 'cancelled'):
                    self._finish_schedule(job, job['status'])
        return self.status()

    def _repair_claim(self, job):
        path = Path(job['schedule_state'])
        with schedule.locked(path):
            state = schedule.state_at(path)
            own = state['experts'][job['expert_id']]
            if any(a['id'] == job['id'] for a in own['attempts']):
                return
            if own['active_attempt'] is not None:
                raise ValueError('Another scheduler attempt owns this expert; do not clear it')
            own['attempts'].append(copy.deepcopy(job['schedule_attempt']))
            own['active_attempt'] = job['id']
            own['last_attempt_at'] = job['created_at']
            schedule.write_json(path, state)

    def claim(self, expert, authorization):
        if not authorization.strip():
            raise ValueError('Research and paper-operation authorization required')
        with schedule.locked(self.path):
            state = self.load()
            entry = self.entry(expert)
            self.require_not_stopped(entry)
            existing = [j for j in state['jobs'].values() if j['expert_id'] == expert
                        and j['status'] not in ('complete', 'blocked', 'cancelled')]
            if existing:
                job = existing[-1]
                self._repair_claim(job)
                return self.work(job)
            completed = any(j['status']=='complete' for j in state['jobs'].values())
            if not completed and any(j['status']=='active' for j in state['jobs'].values()):
                raise ValueError('Initial rollout: finish the first expert before releasing others')
            if state.get('last_check') is None:
                raise ValueError('Run check before claiming work')
            checked = state['last_check']
            # Reassess under the actual scheduler lock; old due receipts are not authority.
            entry = self.entry(expert)
            if entry.get('stopped') or entry.get('enabled') is False:
                raise ValueError('Expert explicitly stopped')
            path = self.resolve(entry['schedule_state'])
            profile = schedule.profiles_at(self.root / 'skills/finrunbook-investor/references/forward-profiles.json')[expert]
            with schedule.locked(path):
                current = schedule.state_at(path)
                own = current['experts'][expert]
                assessment = schedule.assess(profile, own, checked['events'], self.clock())
                if not assessment['due']:
                    raise ValueError('Not due: ' + ', '.join(assessment['reasons']))
                now = schedule.iso(self.clock())
                job_id = str(uuid.uuid4())
                attempt = {'id': job_id, 'started_at': now, 'event_ids': assessment['event_ids'],
                           'reasons': assessment['reasons'], 'provenance': schedule.provenance(profile, checked['events']),
                           'outcome': None}
                output = self.directory / 'jobs' / job_id
                account_path = self.resolve(entry['account'])
                account = accounts.read(account_path)
                if account['expert_id'] != expert or account['account_id'] != entry['account_id']:
                    raise ValueError('Registered account identity mismatch')
                snapshot = output / 'account-snapshot.json'
                schedule.write_json(snapshot, account, exclusive=True)
                job = {'id': job_id, 'expert_id': expert, 'account': str(account_path),
                       'account_snapshot': schedule.artifact(snapshot), 'skill_path': account['skill_path'],
                       'skill_hash': account['skill_hash'], 'schedule_state': str(path),
                       'schedule_attempt': attempt, 'created_at': now, 'authorization': authorization,
                       'status': 'active', 'corrections': 0, 'output': str(output),
                       'stages': {s: {'status': 'pending', 'artifacts': {}} for s in STAGES}}
                job['prior_report']=entry.get('report')
                evidence_index={}
                evidence_path=(checked.get('collection') or {}).get('evidence_path')
                if evidence_path:
                    evidence_index=accounts.read(evidence_path)
                    if 'events' in evidence_index:
                        evidence_index=evidence_index['events']
                job['event_evidence']={event_id:evidence_index.get(event_id) or state.get('numeric_events',{}).get(event_id,{}).get('evidence')
                                       for event_id in attempt['event_ids']}
                state['jobs'][job_id] = job
                self.save(state, 'claim_prepared', job_id)
                own['attempts'].append(attempt)
                own['active_attempt'] = job_id
                own['last_attempt_at'] = now
                schedule.write_json(path, current)
            self.save(state, 'claim_committed', job_id)
            return self.work(job)

    def work(self, job):
        stage = next((s for s in ('research','review','approval','publication') if job['stages'][s]['status'] not in ('completed', 'not_required')), None)
        return {'job_id': job['id'], 'expert_id': job['expert_id'], 'stage': stage,
                'status': job['status'], 'stage_state': job['stages'].get(stage),
                'execution_status': job['stages']['execution']['status'],
                'output': job['output'], 'account_snapshot': job['account_snapshot'],
                'skill_path': job['skill_path'], 'skill_hash': job['skill_hash'],
                'prior_report': job.get('prior_report'), 'event_evidence': job.get('event_evidence',{}),
                'artifacts': {s: x['artifacts'] for s, x in job['stages'].items() if x['artifacts']},
                'execution_mode': 'native_agents', 'parent_history_inherited': False,
                'instructions': 'Fresh own-expert context. English US forward research. Never launch a model CLI.'}

    def record_result(self, job_id, stage, result):
        if stage not in ('research', 'review'):
            raise ValueError('Only native research/review results are accepted; finalize owns later stages')
        status = result['status']
        if status not in ('running', 'completed', 'retryable', 'blocked', 'cancelled'):
            raise ValueError('Invalid stage result')
        with schedule.locked(self.path):
            state = self.load()
            job = state['jobs'][job_id]
            current = job['stages'][stage]
            result_hash = schedule.canonical_hash(result)
            if current.get('result_hash') == result_hash:
                if job['status'] in ('blocked', 'cancelled'):
                    self._finish_schedule(job, job['status'])
                return self.work(job)
            if job['status'] in ('complete', 'blocked', 'cancelled'):
                raise ValueError('Job is terminal; do not resume stopped work implicitly')
            if current['status'] == 'completed':
                raise ValueError('Completed stage immutable; request a targeted correction first')
            if stage == 'review' and job['stages']['research']['status'] != 'completed':
                raise ValueError('Research must be complete before review')
            evidence = result.get('native_observation')
            if status in ('running', 'completed', 'cancelled'):
                if not isinstance(evidence, dict) or not all(evidence.get(k) for k in ('worker_id', 'tool', 'observed_at', 'status')):
                    raise ValueError('Native tool observation required; do not infer liveness from files')
                if schedule.timestamp(evidence['observed_at']) > self.clock():
                    raise ValueError('Future worker observation')
                if status == 'completed' and evidence['status'] != 'completed':
                    raise ValueError('Completion requires native completion observation')
                worker = evidence['worker_id']
                if stage == 'review' and worker == job['stages']['research'].get('worker_id'):
                    raise ValueError('Independent reviewer required')
                if status == 'running':
                    if current.get('retry_at') and self.clock() < schedule.timestamp(current['retry_at']):
                        raise ValueError('Stage retry cooldown has not elapsed')
                    limit = 2 if stage == 'research' else 1
                    occupied = sum(j['stages'][stage]['status'] == 'running' and j['id'] != job_id for j in state['jobs'].values())
                    if occupied >= limit:
                        raise ValueError('Native stage capacity occupied; queue without dispatch')
                current.update(worker_id=worker, native_observation=copy.deepcopy(evidence))
            if status == 'retryable' and result.get('error_kind') not in ('capacity', 'provider', 'runtime'):
                raise ValueError('Only provider, capacity or runtime failures are retryable')
            if current['status']=='running' and status=='retryable' and (not evidence or evidence.get('status') not in ('failed','cancelled','completed')):
                raise ValueError('Confirm the previous worker stopped before retrying')
            artifacts = {k: schedule.artifact(self.resolve(v)) for k, v in result.get('artifacts', {}).items()}
            if status == 'completed':
                required = ('candidate', 'report', 'evidence', 'html') if stage == 'research' else ('review',)
                if not all(k in artifacts for k in required):
                    raise ValueError('Missing completed-stage artifacts')
                if stage == 'research':
                    candidate = accounts.read(artifacts['candidate']['path'])
                    if candidate['task_id'] != current['worker_id'] or candidate['expert_id'] != job['expert_id']:
                        raise ValueError('Native author and candidate identity mismatch')
                    for name in ('report', 'evidence'):
                        if Path(candidate[name + '_path']).resolve() != Path(artifacts[name]['path']) or candidate[name + '_hash'] != artifacts[name]['sha256']:
                            raise ValueError('Candidate artifact binding mismatch')
                    if candidate['action'] == 'rebalance' and candidate.get('execution_policy') != 'fresh_reference_price_ledger':
                        raise ValueError('New Arena orders require explicit fresh-reference-price policy')
                else:
                    review = accounts.read(artifacts['review']['path'])
                    if review['reviewer_task_id'] != current['worker_id']:
                        raise ValueError('Native reviewer identity mismatch')
                if stage == 'research':
                    job['presentation'] = result.get('presentation', {'status': 'unverified'})
            current.update(status=status, artifacts=artifacts or current['artifacts'],
                           result_hash=result_hash, updated_at=schedule.iso(self.clock()),
                           error=result.get('error'), error_kind=result.get('error_kind'),
                           retry_at=schedule.iso(self.clock() + timedelta(minutes=5)) if status == 'retryable' else None)
            if status in ('blocked', 'cancelled'):
                job['status'] = status
            self.save(state, 'record_result', {'job_id': job_id, 'stage': stage, 'result': result})
            if status in ('blocked', 'cancelled'):
                self._finish_schedule(job, status)
            return self.work(job)

    def correct(self, job_id, findings):
        with schedule.locked(self.path):
            state = self.load()
            job = state['jobs'][job_id]
            if job['corrections'] or job['stages']['approval']['status'] != 'pending':
                raise ValueError('Only one correction before approval is allowed')
            if job['stages']['review']['status'] != 'completed':
                raise ValueError('Correction requires a recorded independent review')
            job['prior_revision'] = copy.deepcopy(job['stages'])
            job['corrections'] += 1
            job['correction_findings'] = findings
            for stage in ('research', 'review'):
                job['stages'][stage] = {'status': 'pending', 'artifacts': {}}
            self.save(state, 'targeted_correction', job_id)
            return self.work(job)

    @staticmethod
    def verify(artifacts):
        for item in artifacts.values():
            if schedule.artifact(item['path']) != item:
                raise ValueError('Saved stage artifact changed: ' + item['path'])

    def _finish_schedule(self, job, outcome='completed'):
        path = Path(job['schedule_state'])
        decision = job['stages']['approval']['artifacts'].get('decision')
        report = job['stages']['research']['artifacts'].get('report')
        with schedule.locked(path):
            state = schedule.state_at(path)
            own = state['experts'][job['expert_id']]
            attempt = next(a for a in own['attempts'] if a['id'] == job['id'])
            if attempt.get('outcome') is not None:
                if attempt['outcome'] != outcome or attempt.get('decision') != decision or attempt.get('report') != report:
                    raise ValueError('Conflicting scheduler recovery')
                return
            next_review = job.get('next_review_at')
            # Preserve a passed review commitment as immediately due, not a fabricated future time.
            args = SimpleNamespace(expert=job['expert_id'], attempt=job['id'], outcome=outcome,
                                   next_review_at=next_review if next_review and schedule.timestamp(next_review) >= self.clock() else None)
            schedule.finish(args, state, self.clock(), {'report': report, 'decision': decision})
            if next_review and (not own.get('next_review_at') or schedule.timestamp(next_review)<schedule.timestamp(own['next_review_at'])):
                own['next_review_at'] = next_review
            schedule.write_json(path, state)

    def finalize(self, job_id, publish=True):
        with schedule.locked(self.path):
            state = self.load()
            job = state['jobs'][job_id]
            entry = self.entry(job['expert_id'])
            self.require_not_stopped(entry)
            self._repair_claim(job)
            for stage in ('research', 'review'):
                if job['stages'][stage]['status'] != 'completed':
                    raise ValueError(stage + ' not complete; resume that stage only')
                self.verify(job['stages'][stage]['artifacts'])
            author = job['stages']['research']
            reviewer = job['stages']['review']
            candidate = accounts.read(author['artifacts']['candidate']['path'])
            review = accounts.read(reviewer['artifacts']['review']['path'])
            if candidate['task_id'] != author['worker_id'] or review['reviewer_task_id'] != reviewer['worker_id'] or author['worker_id'] == reviewer['worker_id']:
                raise ValueError('Native financial provenance mismatch')
            accounts.review_status(review, candidate, schedule.iso(self.clock()))
            if job['stages']['approval']['status'] != 'completed':
                with accounts.locked(job['account']):
                    account = accounts.read(job['account'])
                    previous = next((d for d in account['decisions'] if d['candidate_hash'] == accounts.digest(candidate)), None)
                    validation = previous['validation'] if previous else accounts.validate(account, candidate)
                    decision = accounts.seal(account, candidate, validation, review, schedule.iso(self.clock()))
                    if not previous:
                        accounts.atomic_write(job['account'], account)
                decision_path = Path(job['output']) / 'sealed-decision.json'
                if decision_path.exists() and accounts.read(decision_path) != decision:
                    raise ValueError('Conflicting sealed-decision projection')
                if not decision_path.exists():
                    schedule.write_json(decision_path, decision, exclusive=True)
                job['stages']['approval'] = {'status': 'completed', 'decision_id': decision['decision_id'],
                                             'updated_at': decision['sealed_at'], 'artifacts': {'decision': schedule.artifact(decision_path)}}
                job['next_review_at'] = candidate.get('next_review_at')
                self.save(state, 'approval', job_id)
            else:
                self.verify(job['stages']['approval']['artifacts'])
                decision = accounts.read(job['stages']['approval']['artifacts']['decision']['path'])
            self._finish_schedule(job)
            job['scheduler_finished'] = True
            self.save(state, 'schedule_finished', job_id)
            if candidate['action'] == 'no_change':
                job['stages']['execution'] = {'status': 'not_required', 'artifacts': {}, 'reason': 'Retains holdings and existing pending intent'}
            elif job['stages']['execution']['status'] == 'pending':
                import execution_queue
                queued = execution_queue.enqueue(self.root, self.registry, self.directory / 'execution-queue.json',
                                                 job['expert_id'], decision['decision_id'], job['authorization'], now=self.clock())
                job['stages']['execution'] = {'status': 'queued', 'artifacts': {}, 'receipt': queued}
            self.save(state, 'execution_handoff', job_id)
            if publish:
                try:
                    # Financial provenance is saved before publication and remains usable on failure.
                    result = refresh.run(self.registry, self.root / 'runs/live-portfolio', offline=True)
                    if result['status'] == 'skipped_already_running':
                        raise ValueError('Publication busy; retry finalize')
                    job['stages']['publication'] = {'status': 'completed', 'artifacts': {},
                                                   'updated_at': schedule.iso(self.clock()), 'receipt': result}
                    job['status'] = 'complete'
                except (ValueError, OSError, KeyError) as exc:
                    job['stages']['publication'].update(status='retryable', error=str(exc), retry_at=schedule.iso(self.clock()+timedelta(minutes=5)))
                self.save(state, 'publication', job_id)
            return self.work(job)

    def status(self):
        state = self.load()
        jobs = []
        for raw in state['jobs'].values():
            if raw['status'] in ('complete','blocked','cancelled'):
                continue
            job = copy.deepcopy(raw)
            for stage in ('research', 'review'):
                s = job['stages'][stage]
                observation = s.get('native_observation')
                s['liveness'] = (observation['status'] if observation and
                                 (self.clock() - schedule.timestamp(observation['observed_at'])).total_seconds() <= 300
                                 else 'unknown')
            jobs.append(self.work(job))
        check = state.get('last_check') or {}
        health=state.get('source_health')
        if health:
            health={k:health.get(k) for k in ('status','error_count','notification_required','collected_at','receipt_path','error')} | {
                'sources':[{k:r.get(k) for k in ('source_id','status','http_status','next_retry_at','notification_required')} for r in state['source_health'].get('sources',[])]}
        recent=sorted(state['jobs'].values(),key=lambda j:j['created_at'],reverse=True)[:10]
        maintenance=state.get('service',{})
        service_summary={'finished_at':maintenance.get('finished_at'),'error':maintenance.get('error'),
                         'valuation_status':maintenance.get('valuation',{}).get('status'),
                         'execution_status':maintenance.get('execution',{}).get('status'),
                         'execution_outcomes':[{'expert_id':x.get('expert_id'),'status':x.get('status'),'reason':x.get('reason')}
                                               for x in maintenance.get('execution',{}).get('outcomes',[])]}
        return {'schema_version': 1, 'revision': state['revision'], 'checked_at': check.get('checked_at'),
                'rollout': 'verified_first_expert' if any(j['status']=='complete' for j in state['jobs'].values()) else 'first_expert_only',
                'due_experts': check.get('due_experts', []), 'jobs': jobs,
                'job_count':len(state['jobs']),
                'recent_results':[{'job_id':j['id'],'expert_id':j['expert_id'],'status':j['status'],
                                   'decision_id':j['stages']['approval'].get('decision_id'),
                                   'execution':j['stages']['execution']['status']} for j in recent],
                'experts': [{k: r.get(k) for k in ('expert_id', 'due', 'reasons', 'next_eligible_at')} for r in check.get('experts', [])],
                'source_health': health, 'trigger_coverage': check.get('trigger_coverage'),
                'service': service_summary}

    def service_tick(self, offline=False):
        import execution_queue
        started = schedule.iso(self.clock())
        try:
            executions = execution_queue.tick(self.root, self.registry, self.directory / 'execution-queue.json', now=self.clock(), clock=self.clock) if not offline else {'status': 'offline_not_executed'}
        except (ValueError,OSError,KeyError) as exc:
            executions={'status':'error','error':str(exc)}
        with schedule.locked(self.path):
            state = self.load()
            for job in state['jobs'].values():
                decision_id=job['stages']['approval'].get('decision_id')
                item=next((i for i in executions.get('items',{}).values() if i['decision_id']==decision_id),None)
                if item:
                    job['stages']['execution'].update(status=item['status'],receipt=item,updated_at=item['updated_at'])
            self.save(state,'execution_status_refreshed')
        valuation = refresh.run(self.registry, self.root / 'runs/live-portfolio', offline=offline)
        with schedule.locked(self.path):
            state = self.load()
            state['service'] = {'started_at': started, 'finished_at': schedule.iso(self.clock()),
                                'execution': executions, 'valuation': valuation}
            self.save(state, 'service_tick')
        return state['service']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path)
    parser.add_argument('--directory', type=Path)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check'); check.add_argument('--events', type=Path); check.add_argument('--collect-events', action='store_true')
    claim = sub.add_parser('claim'); claim.add_argument('--expert', required=True); claim.add_argument('--authorization', required=True)
    record = sub.add_parser('record-result'); record.add_argument('--job', required=True); record.add_argument('--stage', choices=('research', 'review'), required=True); record.add_argument('--result', type=Path, required=True)
    final = sub.add_parser('finalize'); final.add_argument('--job', required=True)
    correction = sub.add_parser('correct'); correction.add_argument('--job', required=True); correction.add_argument('--findings', required=True)
    tick = sub.add_parser('service-tick'); tick.add_argument('--offline', action='store_true')
    sub.add_parser('status')
    args = parser.parse_args()
    c = Controller(registry=args.registry, directory=args.directory)
    try:
        if args.command == 'check': result = c.check(args.events, args.collect_events)
        elif args.command == 'claim': result = c.claim(args.expert, args.authorization)
        elif args.command == 'record-result': result = c.record_result(args.job, args.stage, accounts.read(args.result))
        elif args.command == 'finalize': result = c.finalize(args.job)
        elif args.command == 'correct': result = c.correct(args.job, args.findings)
        elif args.command == 'service-tick': result = c.service_tick(args.offline)
        else: result = c.status()
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, KeyError, StopIteration) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)})); return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

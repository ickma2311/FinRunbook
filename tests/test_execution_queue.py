"""Offline synthetic durability/risk checks; no real accounts or price network."""
import copy
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'portfolio'))
import execution_queue as q

NOW = datetime(2026, 9, 9, 15, 0, tzinfo=timezone.utc)


@contextmanager
def held_in_process(path):
    """Hold the same flock in another process; auto-release bounds regressions."""
    code = ('import fcntl,select,sys; '
            'lock=open(sys.argv[1]+".lock","a"); '
            'fcntl.flock(lock,fcntl.LOCK_EX); '
            'print("locked",flush=True); select.select([sys.stdin],[],[],5)')
    child = subprocess.Popen([sys.executable, '-c', code, str(path)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        if child.stdout.readline().strip() != 'locked':
            raise AssertionError('Fixture lock holder did not acquire lock')
        yield
    finally:
        child.communicate(input='release', timeout=10)
        if child.returncode != 0:
            raise AssertionError('Fixture lock holder failed')


def market(now):
    """Synthetic weekday calendar with a declared September 11 early close."""
    day = now.date()
    while day.weekday() >= 5:
        day += timedelta(days=1)
    opened = datetime.combine(day, datetime.min.time(), timezone.utc).replace(hour=13, minute=30)
    closed = opened.replace(hour=17 if day.day == 11 else 20, minute=0)
    if now >= closed:
        return market(datetime.combine(day + timedelta(days=1), datetime.min.time(), timezone.utc)) | {'is_open': False}
    return {'is_open': opened <= now < closed, 'session': day.isoformat(),
            'open_at': opened.isoformat(), 'close_at': closed.isoformat(),
            'eligible_open_at': opened.isoformat(), 'eligible_close_at': closed.isoformat()}


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / 'method.md'
        self.skill.write_text('Synthetic method')
        self.report = self.root / 'report.json'
        self.report.write_text('{"fixture": true}')
        self.evidence = self.root / 'evidence.json'
        self.evidence.write_text(json.dumps({'sources': [{'available_at': '2026-09-08T12:00:00Z', 'retrieved_at': '2026-09-09T13:00:00Z'}]}))
        self.a = q.records.init_account('expert', 'paper', self.skill, '2026-09-09T13:00:00Z', symbols=['AAA'])
        self.path = self.root / 'account.json'
        self.registry = self.root / 'registry.json'
        q.records.atomic_write(self.registry, {'experts': [{'id': 'expert', 'account_id': 'paper', 'account': 'account.json'}]})
        self.decision = self.seal()
        self.calls = 0
        self.time = NOW + timedelta(minutes=1)

    def seal(self, action='rebalance', at=NOW, policy='fresh_reference_price_ledger'):
        a = self.a
        c = {'expert_id': 'expert', 'account_id': 'paper', 'task_id': 'author-' + str(a['revision']),
             'skill_hash': a['skill_hash'], 'report_path': str(self.report), 'report_hash': q.records.file_hash(self.report),
             'evidence_path': str(self.evidence), 'evidence_hash': q.records.file_hash(self.evidence),
             'evidence_cutoff': '2026-09-09T14:00:00Z', 'account_snapshot_hash': q.records.digest(q.records.snapshot(a)),
             'action': action, 'rationale': 'Synthetic test', 'next_review_condition': 'Next source'}
        if action == 'rebalance':
            c.update(target_weights={'AAA': '.20'}, execution_policy=policy, replaces_intent_id=a['pending_intent_id'],
                     price_limits={'AAA': {'min': '50', 'max': '150'}})
        r = {'candidate_hash': q.records.digest(c), 'author_task_id': c['task_id'], 'reviewer_task_id': 'reviewer',
             'parent_history_inherited': False, 'reviewed_at': at.isoformat(),
             'findings': [{'id': k, 'required': True, 'status': 'PASS'} for k in ['material_evidence', 'calculations', 'report_decision']]}
        result = q.records.seal(a, c, q.records.validate(a, c), r, at.isoformat())
        q.records.atomic_write(self.path, a)
        return result

    def enqueue(self, decision=None, at=None, authorization='Explicit fixture authorization'):
        return q.enqueue(self.root, self.registry, 'queue.json', 'expert', (decision or self.decision)['decision_id'],
                         authorization, now=at or self.time, market_provider=market)

    def provider(self, symbols, context, timeout):
        self.calls += 1
        return {s: {'symbol': s, 'currency': 'USD', 'basis': 'completed_1m_close', 'price': '100',
                    'price_as_of': (self.time - timedelta(seconds=30)).isoformat(),
                    'retrieved_at': self.time.isoformat(), 'action_coverage_since': since, 'actions': []}
                for s, since in symbols.items()}, {}, False

    def tick(self, provider=None):
        return q.tick(self.root, self.registry, 'queue.json', self.time,
                      market_provider=market, quote_provider=provider or self.provider)

    def item(self, result):
        return next(iter(result['items'].values()))

    def test_empty_queue_never_imports_historical_pending(self):
        self.assertEqual(self.tick()['items'], {})
        self.assertEqual(q.records.read(self.path), self.a)
        self.assertEqual(self.calls, 0)

    def test_requires_authorization(self):
        with self.assertRaisesRegex(ValueError, 'authorization'):
            self.enqueue(authorization='')

    def test_apply_and_idempotent_enqueue_tick(self):
        old_decisions = copy.deepcopy(self.a['decisions'])
        item = self.enqueue()
        self.assertEqual(item, self.enqueue())
        applied = self.item(self.tick())
        self.assertEqual(applied['status'], 'applied')
        account = q.records.read(self.path)
        self.assertEqual(account['positions'], {'AAA': 200})
        self.assertEqual(account['decisions'], old_decisions)
        self.assertFalse(any(x['type'] == 'execution_policy_amendment' for x in account['ledger']))
        self.assertEqual(self.item(self.tick()), applied)
        self.assertEqual(self.calls, 1)
        self.assertEqual(q.records.read(self.path), account)

    def test_five_minute_retry_then_success_preserves_receipts(self):
        self.enqueue()
        first = self.item(self.tick(lambda *a: ({}, {'AAA': 'transient'}, True)))
        self.assertEqual(first['status'], 'waiting_price')
        prior = copy.deepcopy(first['attempts'][0])
        self.time += timedelta(minutes=4)
        self.assertEqual(len(self.item(self.tick())['attempts']), 1)
        self.time += timedelta(minutes=1)
        result = self.item(self.tick())
        self.assertEqual(result['status'], 'applied')
        self.assertEqual(result['attempts'][0], prior)
        files = list((self.root / 'queue-receipts').rglob('*-result.json'))
        self.assertEqual(len(files), 2)

    def test_missing_and_preseal_prices_wait(self):
        self.enqueue()
        def stale(*args):
            quotes, errors, timed = self.provider(*args)
            quotes['AAA']['price_as_of'] = NOW.isoformat()
            return quotes, errors, timed
        self.assertEqual(self.item(self.tick(stale))['status'], 'waiting_price')
        self.assertEqual(q.records.read(self.path), self.a)

    def test_no_change_does_not_invalidate_pending(self):
        self.enqueue()
        self.seal('no_change', at=self.time)
        self.assertEqual(self.item(self.tick())['status'], 'applied')

    def test_explicit_replacement_cancels_old_queue_item(self):
        self.enqueue()
        new = self.seal(at=self.time)
        result = self.tick()
        self.assertEqual(self.item(result)['status'], 'cancelled')
        self.assertEqual(self.calls, 0)
        self.assertEqual(q.records.read(self.path)['pending_intent_id'], new['intent_id'])

    def test_explicit_cancel(self):
        self.enqueue()
        item = q.cancel(self.root, self.registry, 'queue.json', 'expert', self.decision['decision_id'],
                        'Fixture cancel', self.time)
        self.assertEqual(item['status'], 'cancelled')
        self.assertIsNone(q.records.read(self.path)['pending_intent_id'])
        self.tick()
        self.assertEqual(self.calls, 0)

    def test_expiry_clears_only_pending_intent(self):
        self.enqueue()
        self.time = NOW.replace(hour=20)
        result = self.item(self.tick())
        self.assertEqual(result['status'], 'expired')
        account = q.records.read(self.path)
        self.assertEqual(account['cash'], self.a['cash'])
        self.assertEqual(account['decisions'], self.a['decisions'])
        self.assertIsNone(account['pending_intent_id'])
        self.assertEqual(self.calls, 0)

    def test_outside_session_expiry_next_regular_close(self):
        self.decision = self.seal(at=NOW.replace(hour=21))
        item = self.enqueue(at=NOW.replace(hour=21))
        self.assertEqual(q.prices.stamp(item['expires_at']), datetime(2026, 9, 10, 20, tzinfo=timezone.utc))
        self.time = NOW.replace(hour=21)
        self.assertEqual(self.item(self.tick())['status'], 'market_closed')
        self.assertEqual(self.calls, 0)

    def test_early_close_expiry(self):
        self.decision = self.seal(at=NOW.replace(day=11, hour=15))
        item = self.enqueue(at=NOW.replace(day=11, hour=15))
        self.assertEqual(q.prices.stamp(item['expires_at']).hour, 17)

    def test_weekend_expiry(self):
        self.decision = self.seal(at=NOW.replace(day=12, hour=15))
        item = self.enqueue(at=NOW.replace(day=12, hour=15))
        self.assertEqual(q.prices.stamp(item['expires_at']), NOW.replace(day=14, hour=20))

    def test_price_collection_crossing_close_expires_without_filling(self):
        self.time = NOW.replace(hour=19, minute=59, second=50)
        self.enqueue()
        times = iter([self.time, NOW.replace(hour=20, minute=0, second=5)])
        result = q.tick(self.root, self.registry, 'queue.json', self.time, clock=lambda: next(times),
                        market_provider=market, quote_provider=self.provider)
        self.assertEqual(self.item(result)['status'], 'expired')
        self.assertEqual(q.records.read(self.path)['positions'], {})

    def test_risk_block_does_not_retry_or_fill(self):
        self.enqueue()
        def expensive(*args):
            quotes, errors, timed = self.provider(*args)
            quotes['AAA']['price'] = '160'
            return quotes, errors, timed
        self.assertEqual(self.item(self.tick(expensive))['status'], 'risk_blocked')
        account = q.records.read(self.path)
        self.assertEqual(account['cash'], self.a['cash'])
        self.assertEqual(account['positions'], {})
        self.time += timedelta(minutes=5)
        self.tick()
        self.assertEqual(self.calls, 1)

    def test_crash_after_account_commit_recovers_without_duplicate(self):
        self.enqueue()
        with patch.object(q, 'finish', side_effect=OSError('simulated process loss after account commit')):
            with self.assertRaises(OSError):
                self.tick()
        committed = q.records.read(self.path)
        self.assertEqual(committed['positions'], {'AAA': 200})
        self.assertEqual(self.item(self.tick())['status'], 'applied')
        self.assertEqual(q.records.read(self.path), committed)
        self.assertEqual(self.calls, 1)

    def test_crash_before_price_attempt_reuses_no_outcome(self):
        self.enqueue()
        with patch.object(q, 'market_context', side_effect=AssertionError('unused')):
            def die(*a):
                raise KeyboardInterrupt('simulated process loss')
            with self.assertRaises(KeyboardInterrupt):
                self.tick(die)
        result = self.item(self.tick())
        self.assertEqual(result['attempts'][0]['reason'], 'interrupted_attempt_recovered')
        self.assertEqual(self.calls, 0)
        self.time += timedelta(minutes=5)
        self.assertEqual(self.item(self.tick())['status'], 'applied')

    def test_crash_after_receipt_publication_recovers_same_receipt(self):
        self.enqueue()
        write = q.records.atomic_write
        def lose_ack(path, value):
            if Path(path).name == 'queue.json' and any(i['status'] == 'applied' for i in value['items'].values()):
                raise OSError('simulated queue acknowledgement loss')
            return write(path, value)
        with patch.object(q.records, 'atomic_write', side_effect=lose_ack):
            with self.assertRaises(OSError):
                self.tick()
        receipt_path = next((self.root / 'queue-receipts').rglob('*-result.json'))
        receipt_bytes = receipt_path.read_bytes()
        account = q.records.read(self.path)
        result = self.item(self.tick())
        self.assertEqual(result['status'], 'applied')
        self.assertEqual(len(result['attempts']), 1)
        self.assertEqual(receipt_path.read_bytes(), receipt_bytes)
        self.assertEqual(q.records.read(self.path), account)
        self.assertEqual(self.calls, 1)

    def test_quote_provider_exception_and_missing_fields_are_transient(self):
        self.enqueue()
        def unavailable(*args):
            raise TimeoutError('synthetic timeout')
        self.assertEqual(self.item(self.tick(unavailable))['status'], 'waiting_price')
        self.time += timedelta(minutes=5)
        self.assertEqual(self.item(self.tick(lambda *a: ({'AAA': {}}, {}, False)))['status'], 'waiting_price')
        self.assertEqual(q.records.read(self.path), self.a)

    def test_queue_cannot_alias_account(self):
        with self.assertRaises(ValueError):
            q.enqueue(self.root, self.registry, 'account.json', 'expert', self.decision['decision_id'], 'yes',
                      now=self.time, market_provider=market)
        self.assertEqual(q.records.read(self.path), self.a)

    def test_unavailable_account_throttles_then_expires_without_mutation(self):
        self.enqueue()
        self.path.write_text('unreadable synthetic account')
        first = self.item(self.tick())
        self.assertEqual(first['status'], 'waiting_price')
        self.time += timedelta(minutes=1)
        self.assertEqual(len(self.item(self.tick())['attempts']), 1)
        self.time = NOW.replace(hour=20)
        expired = self.item(self.tick())
        self.assertEqual(expired['status'], 'expired')
        self.assertTrue(expired['reconciliation_required'])
        self.assertEqual(self.path.read_text(), 'unreadable synthetic account')
        self.assertEqual(self.calls, 0)

    def test_tick_attempt_budget_defers_remaining_order_without_starvation(self):
        self.enqueue()
        # Duplicate a synthetic due entry with its own key to exercise ordering;
        # the injected provider only returns timeouts, so neither can execute.
        state = q.records.read(self.root / 'queue.json')
        first = next(iter(state['items'].values()))
        second = copy.deepcopy(first)
        second['execution_key'] = 'second-fixture'
        state['items']['second-fixture'] = second
        q.records.atomic_write(self.root / 'queue.json', state)
        result = q.tick(self.root, self.registry, 'queue.json', self.time, market_provider=market,
                        quote_provider=lambda *a: ({}, {'AAA': 'timeout'}, True), max_attempts=1)
        self.assertEqual(len(result['outcomes']), 1)
        self.assertIsNone(result['items']['second-fixture']['last_attempt_at'])
        self.time += timedelta(minutes=5)
        result = q.tick(self.root, self.registry, 'queue.json', self.time, market_provider=market,
                        quote_provider=lambda *a: ({}, {'AAA': 'timeout'}, True), max_attempts=1)
        self.assertEqual(result['outcomes'][0]['execution_key'], 'second-fixture')

    def test_old_policy_gets_append_only_amendment(self):
        self.decision = self.seal(at=self.time, policy='next_regular_session_open')
        old = copy.deepcopy(self.a['decisions'])
        self.enqueue()
        self.time += timedelta(minutes=1)
        self.assertEqual(self.item(self.tick())['status'], 'applied')
        account = q.records.read(self.path)
        self.assertEqual(account['decisions'], old)
        self.assertEqual(sum(x['type'] == 'execution_policy_amendment' for x in account['ledger']), 1)

    def test_busy_queue_skips_without_reading_or_writing_then_recovers(self):
        self.enqueue()
        before = (self.root / 'queue.json').read_bytes()
        with held_in_process(self.root / 'queue.json'):
            started = time.monotonic()
            result = self.tick()
            self.assertLess(time.monotonic() - started, 1)
            self.assertEqual(result['status'], 'skipped')
            self.assertEqual(result['reason'], 'queue_lock_busy')
            self.assertNotIn('items', result)
        self.assertEqual((self.root / 'queue.json').read_bytes(), before)
        self.assertEqual(self.calls, 0)
        self.assertEqual(self.item(self.tick())['status'], 'applied')

    def test_busy_account_skips_without_leaking_queue_lock_and_keeps_expiry(self):
        self.enqueue()
        before = (self.root / 'queue.json').read_bytes()
        self.time = NOW.replace(hour=20)
        with held_in_process(self.path):
            started = time.monotonic()
            result = self.tick()
            self.assertLess(time.monotonic() - started, 1)
            self.assertEqual(result['outcomes'][0]['reason'], 'account_lock_busy')
            self.assertTrue(result['outcomes'][0]['expiry_due'])
            self.assertEqual(self.item(result)['status'], 'waiting_price')
            with q.try_locked(self.root / 'queue.json') as acquired:
                self.assertTrue(acquired)
        self.assertEqual((self.root / 'queue.json').read_bytes(), before)
        self.assertEqual(q.records.read(self.path), self.a)
        self.assertEqual(self.item(self.tick())['status'], 'expired')
        self.assertEqual(self.calls, 0)

    def test_busy_account_does_not_block_another_expert_or_consume_attempt_budget(self):
        self.enqueue()
        # A second independent, sealed paper account uses the same neutral fixture
        # sources but its own identity, candidate, review and queue entry.
        account2 = q.records.init_account('expert2', 'paper2', self.skill, '2026-09-09T13:00:00Z', symbols=['AAA'])
        candidate = copy.deepcopy(self.decision['candidate'])
        candidate.update(expert_id='expert2', account_id='paper2',
                         account_snapshot_hash=q.records.digest(q.records.snapshot(account2)))
        review = copy.deepcopy(self.decision['review'])
        review['candidate_hash'] = q.records.digest(candidate)
        decision = q.records.seal(account2, candidate, q.records.validate(account2, candidate), review, NOW.isoformat())
        q.records.atomic_write(self.root / 'account2.json', account2)
        registry = q.records.read(self.registry)
        registry['experts'].append({'id': 'expert2', 'account_id': 'paper2', 'account': 'account2.json'})
        q.records.atomic_write(self.registry, registry)
        second = q.enqueue(self.root, self.registry, 'queue.json', 'expert2', decision['decision_id'], 'fixture approval',
                           self.time, market_provider=market)
        with held_in_process(self.path):
            started = time.monotonic()
            result = q.tick(self.root, self.registry, 'queue.json', self.time, market_provider=market,
                            quote_provider=self.provider, max_attempts=1)
            self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(result['items'][second['execution_key']]['status'], 'applied')
        self.assertEqual(q.records.read(self.path), self.a)
        self.assertEqual(self.calls, 1)
        self.assertTrue(any(o['reason'] == 'account_lock_busy' for o in result['outcomes']))

    def test_nonblocking_lock_released_after_exception(self):
        path = self.root / 'fixture.json'
        with self.assertRaisesRegex(RuntimeError, 'fixture interruption'):
            with q.try_locked(path) as acquired:
                self.assertTrue(acquired)
                raise RuntimeError('fixture interruption')
        with held_in_process(path):
            with q.try_locked(path) as acquired:
                self.assertFalse(acquired)
        with q.try_locked(path) as acquired:
            self.assertTrue(acquired)


if __name__ == '__main__':
    unittest.main()

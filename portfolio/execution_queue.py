#!/usr/bin/env python3
"""Durable, explicitly authorized paper execution; never discovers old orders.

Account JSON is authoritative. Queue and immutable attempt receipts are recoverable
projections; an account commit always precedes its successful queue acknowledgement.
All writers lock queue then account. No model or broker calls occur here.
"""
import argparse
import copy
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import time
import uuid

import apply_decision as apply

records = apply.records
prices = apply.prices
TERMINAL = frozenset({'applied', 'expired', 'risk_blocked', 'cancelled'})
RETRY_SECONDS = 300


def moment(value=None):
    value = value or prices.utcnow()
    return prices.stamp(value) if isinstance(value, str) else prices.stamp(value.isoformat())


def market_context(now):
    """Use the exchange calendar, including holidays and early closing sessions."""
    import exchange_calendars as xc
    import pandas as pd
    result = prices.market_context(now)
    cal = xc.get_calendar('XNYS')
    day = pd.Timestamp(now.astimezone(prices.ZoneInfo('America/New_York')).date())
    for session in cal.sessions_in_range(day, day + pd.Timedelta(days=21)):
        opened = cal.session_open(session).to_pydatetime()
        closed = cal.session_close(session).to_pydatetime()
        if closed > now:
            result.update(eligible_open_at=opened.isoformat(), eligible_close_at=closed.isoformat())
            return result
    raise ValueError('No eligible regular session in exchange calendar')


def scoped(root, path):
    base = Path(root).resolve()
    result = (base / path).resolve()
    apply.check(base in result.parents, 'Queue/account path must be inside root')
    return result


def account_path(root, registry_path, expert_id):
    registry = records.read(scoped(root, registry_path))
    entries = [e for e in registry['experts'] if e['id'] == expert_id]
    apply.check(len(entries) == 1, 'Expert must have one registry entry')
    entry = entries[0]
    return scoped(root, entry['account']), entry


def identity(account, entry):
    apply.check(account['account_id'] == entry['account_id'] and account['expert_id'] == entry['id'],
                'Registry identity mismatch')


def load_queue(path):
    queue = records.read(path) if path.exists() else {'schema_version': 1, 'items': {}}
    apply.check(queue.get('schema_version') == 1 and isinstance(queue.get('items'), dict), 'Invalid execution queue')
    return queue


@contextmanager
def try_locked(path):
    """Acquire the existing sidecar lock immediately or yield False.

    Open descriptions are closed on every path, including contention and raised
    exceptions. Never unlink sidecars: other writers may already be locking them.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with Path(str(path) + '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def immutable(path, value):
    """Publish a complete receipt without ever replacing a prior receipt."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        apply.check(records.read(path) == value, 'Immutable execution receipt conflict')
        return
    # Write/fsync an isolated file, then link it atomically with no overwrite.
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    try:
        records.atomic_write(temporary, value)
        os.link(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def receipt_path(queue_path, item, attempt_id, kind):
    return queue_path.parent / (queue_path.stem + '-receipts') / item['execution_key'] / (attempt_id + '-' + kind + '.json')


def begin(queue_path, queue, item, now):
    attempt_id = uuid.uuid4().hex
    request = {'attempt_id': attempt_id, 'execution_key': item['execution_key'],
               'expert_id': item['expert_id'], 'decision_id': item['decision_id'],
               'started_at': now.isoformat(), 'authorization': item['authorization']}
    immutable(receipt_path(queue_path, item, attempt_id, 'request'), request)
    item.update(active_attempt=request, last_attempt_at=now.isoformat(),
                next_attempt_at=(now + timedelta(seconds=RETRY_SECONDS)).isoformat())
    records.atomic_write(queue_path, queue)
    return request


def finish(queue_path, item, now, status, reason, **details):
    request = item['active_attempt']
    receipt = {**request, 'finished_at': now.isoformat(), 'status': status, 'reason': reason, **details}
    path = receipt_path(queue_path, item, request['attempt_id'], 'result')
    # A previous process may have published the outcome before queue acknowledgement.
    if path.exists():
        receipt = records.read(path)
    else:
        immutable(path, receipt)
    if not any(a['attempt_id'] == request['attempt_id'] for a in item['attempts']):
        item['attempts'].append(receipt)
    item.update(status=receipt['status'], reason=receipt['reason'], updated_at=receipt['finished_at'], active_attempt=None)
    if item['status'] in TERMINAL:
        item['next_attempt_at'] = None
    return receipt


def enqueue(root, registry_path, queue_path, expert_id, decision_id, authorization, now=None, *, market_provider=None):
    """Accept one explicit approved decision, never scan pending historical intents."""
    now = moment(now)
    apply.check(isinstance(authorization, str) and bool(authorization.strip()), 'Explicit decision authorization required')
    queue_path = scoped(root, queue_path)
    path, entry = account_path(root, registry_path, expert_id)
    records.reject_output_alias(queue_path, [path, scoped(root, registry_path), str(path) + '.lock'])
    with records.locked(queue_path), records.locked(path):
        queue = load_queue(queue_path)
        account = records.read(path)
        identity(account, entry)
        execution_key = apply.key(account, decision_id)
        if execution_key in queue['items']:
            return copy.deepcopy(queue['items'][execution_key])
        decision = apply.approved(account, decision_id, now=now, root=root)
        session = (market_provider or market_context)(prices.stamp(decision['sealed_at']))
        sealed = prices.stamp(decision['sealed_at'])
        opened = prices.stamp(session.get('eligible_open_at', session['open_at']))
        closed = prices.stamp(session.get('eligible_close_at', session['close_at']))
        apply.check(closed > sealed and opened < closed, 'Calendar must supply current or next eligible session')
        item = {'execution_key': execution_key, 'expert_id': expert_id, 'account_id': account['account_id'],
                'decision_id': decision_id, 'intent_id': decision['intent_id'],
                'authorization': authorization, 'enqueued_at': now.isoformat(), 'sealed_at': decision['sealed_at'],
                'execution_policy': 'fresh_reference_price_ledger', 'eligible_open_at': opened.isoformat(),
                'expires_at': closed.isoformat(), 'status': 'waiting_price', 'reason': 'approved_decision_enqueued',
                'updated_at': now.isoformat(), 'last_attempt_at': None, 'next_attempt_at': now.isoformat(),
                'active_attempt': None, 'attempts': []}
        queue['items'][execution_key] = item
        records.atomic_write(queue_path, queue)
        return copy.deepcopy(item)


def end_intent(account, item, status, reason, now):
    """Close only this active intent; decisions and existing fills stay immutable."""
    if account['pending_intent_id'] != item['intent_id']:
        return False
    intent = next(i for i in account['intents'] if i['intent_id'] == item['intent_id'])
    intent['status'] = status
    account['pending_intent_id'] = None
    account['ledger'].append({'type': 'execution_status', 'at': now.isoformat(),
                              'decision_id': item['decision_id'], 'intent_id': item['intent_id'],
                              'status': status, 'reason': reason})
    if status == 'risk_blocked':
        account.setdefault('review_events', []).append({
            'id': 'execution-review-' + records.digest([item['execution_key'], reason])[:24],
            'decision_id': item['decision_id'], 'intent_id': item['intent_id'],
            'reason': reason, 'at': now.isoformat()})
    account['revision'] += 1
    return True


def failure_status(error):
    # Quote transport, freshness and completeness failures retry. Portfolio limits,
    # source bindings, corporate actions and malformed risk rules require review.
    message = str(error)
    transient = ('Incomplete price basket', 'Price is stale, future, or predates decision',
                 'Price outside regular session', 'Wrong price identity/basis', 'Invalid price',
                 'Missing corporate-action coverage')
    return 'waiting_price' if any(message.startswith(t) for t in transient) else 'risk_blocked'


def unavailable(queue_path, queue, item, now, error):
    expired = now >= prices.stamp(item['expires_at'])
    if not expired and not item.get('active_attempt') and item.get('next_attempt_at') and now < prices.stamp(item['next_attempt_at']):
        return None
    if not item.get('active_attempt'):
        begin(queue_path, queue, item, now)
    status = 'expired' if expired else 'waiting_price'
    if expired:
        item['reconciliation_required'] = True
    receipt = finish(queue_path, item, now, status, 'account_unavailable_at_expiry' if expired else 'account_unavailable',
                     error=str(error), reconciliation_required=expired)
    records.atomic_write(queue_path, queue)
    return receipt


def tick(root, registry_path, queue_path, now=None, *, market_provider=None, quote_provider=None, clock=None,
         max_attempts=4, max_seconds=120):
    """Run due attempts once. Inject calendar, quotes and clock for offline testing.

    quote_provider(symbols_to_account_observed_at, market, timeout_seconds) returns
    (quotes, errors, timed_out), matching refresh.fetch_shared. Explicit now fixes
    the clock unless clock is supplied. Production obtains time again after I/O.
    """
    started = moment(now)
    apply.check(type(max_attempts) is int and max_attempts > 0 and max_seconds > 0, 'Positive tick limits required')
    deadline = time.monotonic() + max_seconds
    attempted = 0
    clock = clock or ((lambda: started) if now is not None else prices.utcnow)
    queue_path = scoped(root, queue_path)
    with try_locked(queue_path) as queue_locked:
        if not queue_locked:
            # Do not return an unlocked queue snapshot or imply an empty queue.
            return {'schema_version': 1, 'status': 'skipped', 'reason': 'queue_lock_busy',
                    'tick_at': started.isoformat(), 'outcomes': []}
        queue = load_queue(queue_path)
        outcomes = []
        # Oldest due item first ensures a repeatedly failing expert cannot starve
        # later experts when a tick reaches its bounded provider budget.
        ordered = sorted(queue['items'].values(), key=lambda i: i.get('next_attempt_at') or i['enqueued_at'])
        for item in ordered:
            if item['status'] in TERMINAL:
                continue
            current = moment(clock())
            try:
                path, entry = account_path(root, registry_path, item['expert_id'])
                records.reject_output_alias(queue_path, [path, scoped(root, registry_path), str(path) + '.lock'])
            except (OSError, ValueError, KeyError, TypeError) as exc:
                receipt = unavailable(queue_path, queue, item, current, exc)
                if receipt is not None:
                    outcomes.append(receipt)
                continue
            with try_locked(path) as account_locked:
                if not account_locked:
                    # The owner may be committing a fill. Defer even expiry
                    # until we can reconcile the authoritative account safely.
                    # This is a skipped check, not a price attempt or cancellation.
                    outcomes.append({'execution_key': item['execution_key'], 'expert_id': item['expert_id'],
                                     'decision_id': item['decision_id'], 'status': 'skipped',
                                     'reason': 'account_lock_busy', 'checked_at': current.isoformat(),
                                     'expiry_due': current >= prices.stamp(item['expires_at'])})
                    continue
                try:
                    account = records.read(path)
                    identity(account, entry)
                    apply.check(account['account_id'] == item['account_id'], 'Queued account identity changed')
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    receipt = unavailable(queue_path, queue, item, current, exc)
                    if receipt is not None:
                        outcomes.append(receipt)
                    continue
                settlement = account['settlements'].get(item['execution_key'])
                if settlement:
                    if not item.get('active_attempt'):
                        begin(queue_path, queue, item, current)
                    outcomes.append(finish(queue_path, item, current, 'applied', 'account_commit_recovered',
                                           settlement=settlement['receipt']))
                    records.atomic_write(queue_path, queue)
                    continue
                if item.get('active_attempt'):
                    outcomes.append(finish(queue_path, item, current, 'waiting_price', 'interrupted_attempt_recovered'))
                intent = next((i for i in account['intents'] if i['intent_id'] == item['intent_id']), {})
                if account['pending_intent_id'] != item['intent_id'] or intent.get('status') != 'pending':
                    begin(queue_path, queue, item, current)
                    status = intent.get('status') if intent.get('status') in TERMINAL else 'cancelled'
                    outcomes.append(finish(queue_path, item, current, status, 'intent_' + intent.get('status', 'inactive')))
                    records.atomic_write(queue_path, queue)
                    continue
                if current >= prices.stamp(item['expires_at']):
                    begin(queue_path, queue, item, current)
                    end_intent(account, item, 'expired', 'eligible_session_closed', current)
                    records.atomic_write(path, account)
                    outcomes.append(finish(queue_path, item, current, 'expired', 'eligible_session_closed'))
                    records.atomic_write(queue_path, queue)
                    continue
                if item.get('next_attempt_at') and current < prices.stamp(item['next_attempt_at']):
                    records.atomic_write(queue_path, queue)
                    continue
                if attempted >= max_attempts or time.monotonic() >= deadline:
                    continue
                attempted += 1
                begin(queue_path, queue, item, current)
                details = {}
                try:
                    decision = apply.approved(account, item['decision_id'], now=current, root=root)
                    try:
                        market = (market_provider or market_context)(current)
                    except Exception as exc:
                        outcomes.append(finish(queue_path, item, moment(clock()), 'waiting_price', 'calendar_unavailable', error=str(exc)))
                        records.atomic_write(queue_path, queue)
                        continue
                    details['market'] = market
                    if not market['is_open']:
                        outcomes.append(finish(queue_path, item, current, 'market_closed', 'regular_market_closed', **details))
                    else:
                        symbols = set(decision['candidate']['target_weights']) | set(account['positions'])
                        try:
                            quotes, errors, timed_out = (quote_provider or prices.fetch_shared)(
                                {s: account['observed_at'] for s in symbols}, market, max(0.001, min(35, deadline - time.monotonic())))
                        except Exception as exc:
                            quotes, errors, timed_out = {}, {'provider': str(exc)}, False
                        observed = moment(clock())
                        details.update(quotes=quotes, errors=errors, timed_out=timed_out)
                        if observed >= prices.stamp(item['expires_at']):
                            end_intent(account, item, 'expired', 'eligible_session_closed', observed)
                            records.atomic_write(path, account)
                            outcomes.append(finish(queue_path, item, observed, 'expired', 'eligible_session_closed', **details))
                        elif errors or timed_out:
                            outcomes.append(finish(queue_path, item, observed, 'waiting_price', 'price_collection_failed', **details))
                        else:
                            try:
                                updated, receipt = apply.apply_observed(account, decision, quotes, market, observed, current, item['authorization'])
                            except (KeyError, TypeError) as exc:
                                raise ValueError('Incomplete price basket: ' + str(exc)) from exc
                            records.atomic_write(path, updated)
                            outcomes.append(finish(queue_path, item, observed, 'applied', 'fresh_prices_applied', settlement=receipt, **details))
                except (ValueError, KeyError, TypeError) as exc:
                    # Never overwrite a successful authoritative account commit
                    # if acknowledgement/receipt processing then failed.
                    committed = records.read(path)['settlements'].get(item['execution_key'])
                    if committed:
                        raise
                    status = failure_status(exc)
                    if status == 'risk_blocked':
                        end_intent(account, item, status, str(exc), moment(clock()))
                        records.atomic_write(path, account)
                    outcomes.append(finish(queue_path, item, moment(clock()), status, str(exc), **details))
                records.atomic_write(queue_path, queue)
        return {**copy.deepcopy(queue), 'tick_at': started.isoformat(), 'outcomes': outcomes}


def cancel(root, registry_path, queue_path, expert_id, decision_id, authorization, now=None):
    now = moment(now)
    apply.check(isinstance(authorization, str) and bool(authorization.strip()), 'Explicit cancellation authorization required')
    queue_path = scoped(root, queue_path)
    path, entry = account_path(root, registry_path, expert_id)
    records.reject_output_alias(queue_path, [path, scoped(root, registry_path), str(path) + '.lock'])
    with records.locked(queue_path), records.locked(path):
        account = records.read(path)
        identity(account, entry)
        queue = load_queue(queue_path)
        item = queue['items'][apply.key(account, decision_id)]
        if item['status'] in TERMINAL:
            return copy.deepcopy(item)
        if item.get('active_attempt'):
            finish(queue_path, item, now, 'waiting_price', 'interrupted_attempt_recovered')
        begin(queue_path, queue, item, now)
        if item['execution_key'] in account['settlements']:
            finish(queue_path, item, now, 'applied', 'account_commit_recovered',
                   settlement=account['settlements'][item['execution_key']]['receipt'])
        else:
            end_intent(account, item, 'cancelled', authorization, now)
            records.atomic_write(path, account)
            finish(queue_path, item, now, 'cancelled', authorization)
        records.atomic_write(queue_path, queue)
        return copy.deepcopy(item)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('enqueue', 'tick', 'cancel'))
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--registry', default='portfolio/experts.json')
    parser.add_argument('--queue', default='runs/arena-controller/execution-queue.json')
    parser.add_argument('--expert')
    parser.add_argument('--decision')
    parser.add_argument('--authorization')
    args = parser.parse_args()
    kwargs = dict(root=args.root, registry_path=args.registry, queue_path=args.queue)
    if args.command != 'tick':
        if not all((args.expert, args.decision, args.authorization)):
            parser.error('--expert, --decision and --authorization are required')
        kwargs.update(expert_id=args.expert, decision_id=args.decision, authorization=args.authorization)
    print(json.dumps(globals()[args.command](**kwargs), indent=2))


if __name__ == '__main__':
    main()

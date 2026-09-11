#!/usr/bin/env python3
"""Managed localhost Arena preview and five-minute paper-account maintenance."""
import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import urllib.request

from controller import Controller, ROOT, schedule


def health(controller, instance=None):
    state = controller.load()
    service = state.get('service', {})
    finished = service.get('finished_at')
    age = (controller.clock()-schedule.timestamp(finished)).total_seconds() if finished else None
    return {'service': 'arena-local', 'instance': instance, 'pid': os.getpid(),
            'status': 'ok' if age is not None and 0 <= age <= 420 and not service.get('error') and service.get('valuation',{}).get('status')=='ok' and service.get('execution',{}).get('status')!='error' else 'degraded',
            'last_tick_at': finished, 'tick_age_seconds': age,
            'valuation_status': service.get('valuation', {}).get('status'),
            'error': service.get('error'), 'research_dispatch': False,
            'controller_revision': state['revision']}


def serve(controller, port, interval=300, offline=False, instance=None):
    stopped = threading.Event()
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path.split('?')[0] == '/health':
                payload = json.dumps(health(controller, instance)).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers(); self.wfile.write(payload)
            else:
                super().do_GET()

        def log_message(self, fmt, *args):
            logging.info(fmt, *args)

    def maintenance():
        while not stopped.is_set():
            try:
                controller.service_tick(offline=offline)
            except Exception as exc:
                logging.exception('Arena maintenance failed')
                try:
                    with schedule.locked(controller.path):
                        state = controller.load()
                        state['service'] = {'finished_at': schedule.iso(controller.clock()), 'error': str(exc)}
                        controller.save(state, 'service_error')
                except Exception:
                    logging.exception('Could not save maintenance error')
            stopped.wait(interval)

    server = ThreadingHTTPServer(('127.0.0.1', port), functools.partial(Handler, directory=str(controller.root / 'runs')))
    server.timeout = 1
    thread = threading.Thread(target=maintenance, name='arena-maintenance', daemon=True)
    thread.start()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.set())
    logging.info('Serving Arena on port %s; paper maintenance every %ss', port, interval)
    try:
        while not stopped.is_set():
            server.handle_request()
    finally:
        server.server_close()


def probe(port):
    # No proxy forwarding of localhost health checks.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(f'http://127.0.0.1:{port}/health', timeout=2) as response:
        return json.load(response)


def start(controller, port, offline=False):
    pidfile = controller.directory / 'service.json'
    with schedule.locked(pidfile):
        if pidfile.exists():
            saved = schedule.read_json(pidfile)
            try:
                current = probe(saved['port'])
                if current.get('instance') == saved['instance']:
                    return current
            except (OSError, ValueError):
                pass
        controller.directory.mkdir(parents=True, exist_ok=True)
        import uuid
        instance = uuid.uuid4().hex
        log = controller.directory / 'service.log'
        command = [sys.executable, str(Path(__file__).resolve()), '--registry', str(controller.registry),
                   '--directory', str(controller.directory), '--port', str(port), 'serve', '--instance', instance]
        if offline:
            command.append('--offline')
        with log.open('ab', buffering=0) as stream:
            child = subprocess.Popen(command, cwd=controller.root, stdin=subprocess.DEVNULL,
                                     stdout=stream, stderr=stream, start_new_session=True, close_fds=True)
        record = {'pid': child.pid, 'port': port, 'instance': instance, 'log': str(log),
                  'started_at': schedule.iso(controller.clock()), 'url': f'http://127.0.0.1:{port}/live-portfolio/'}
        schedule.write_json(pidfile, record)
        for _ in range(30):
            if child.poll() is not None:
                raise ValueError('Service exited; inspect ' + str(log))
            try:
                current = probe(port)
                if current.get('instance') == instance:
                    return record
            except (OSError, ValueError):
                pass
            time.sleep(.1)
        raise ValueError('Service did not become reachable; inspect ' + str(log))


def stop(controller):
    path = controller.directory / 'service.json'
    with schedule.locked(path):
        saved = schedule.read_json(path)
        current = probe(saved['port'])
        if current.get('service') != 'arena-local' or current.get('instance') != saved['instance'] or current.get('pid') != saved['pid']:
            raise ValueError('Service identity not verified; no process was stopped')
        os.kill(saved['pid'], signal.SIGTERM)
        return {'status': 'stop_requested', 'pid': saved['pid']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path)
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--port', type=int, default=8798)
    sub = parser.add_subparsers(dest='command', required=True)
    launch = sub.add_parser('start'); launch.add_argument('--offline', action='store_true')
    run = sub.add_parser('serve'); run.add_argument('--offline', action='store_true'); run.add_argument('--instance', required=True)
    sub.add_parser('stop'); sub.add_parser('status')
    args = parser.parse_args()
    controller = Controller(registry=args.registry, directory=args.directory)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        if args.command == 'serve':
            serve(controller, args.port, offline=args.offline, instance=args.instance); return 0
        if args.command == 'start': result = start(controller, args.port, args.offline)
        elif args.command == 'stop': result = stop(controller)
        else:
            saved = schedule.read_json(controller.directory / 'service.json')
            result = probe(saved['port'])
            if result.get('instance') != saved['instance']:
                raise ValueError('Service identity mismatch')
        print(json.dumps(result, indent=2)); return 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({'status': 'unavailable', 'error': str(exc)})); return 2


if __name__ == '__main__':
    raise SystemExit(main())

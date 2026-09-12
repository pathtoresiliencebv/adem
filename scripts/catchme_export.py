#!/usr/bin/env python3
"""Export a bounded, read-only Adem process snapshot for local CatchMe recall.

This intentionally writes no activity events and never includes command lines,
paths, window titles, URLs, screen content or credentials.
"""
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.request

DEST = Path.home() / '.catchme' / 'integrations' / 'adem-processes.json'
FALLBACK = Path.home() / '.cache' / 'adem' / 'catchme-processes.json'


def export(url='http://127.0.0.1:8765/api/state', destination=DEST):
    request = urllib.request.Request(url, headers={'Host': '127.0.0.1:8765'})
    with urllib.request.urlopen(request, timeout=4) as response:
        state = json.load(response)
    apps = sorted(state.get('apps', []), key=lambda app: (app.get('memory', 0), app.get('cpu', 0)), reverse=True)
    expensive = [
        {
            'name': str(app.get('name', 'Unknown'))[:80],
            'memoryBytes': max(0, int(app.get('memory', 0))),
            'cpuPercent': round(max(0.0, float(app.get('cpu', 0))), 1),
            'processCount': max(0, int(app.get('count', 0))),
            'closable': bool(app.get('closable', False)),
            'protected': not bool(app.get('closable', False)),
            'protectionReason': str(app.get('reason', ''))[:120],
        }
        for app in apps[:20]
        if int(app.get('memory', 0)) >= 50 * 1024 * 1024 or float(app.get('cpu', 0)) >= 1
    ]
    payload = {
        'schema': 'adem.catchme.processes.v1',
        'source': 'Adem local process dashboard',
        'capturedAt': time.time(),
        'hostname': str(state.get('hostname', ''))[:80],
        'scope': 'current Linux user process groups; no screen or activity history',
        'expensiveProcesses': expensive,
        'readOnly': True,
        'actions': [],
    }
    destination = Path(destination)
    try:
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError:
        destination = FALLBACK
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.adem-processes-', dir=destination.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temporary, destination)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return payload, destination


if __name__ == '__main__':
    try:
        payload, destination = export()
        print(json.dumps({'ok': True, 'destination': str(destination), 'count': len(payload['expensiveProcesses'])}))
    except (OSError, ValueError, TypeError, urllib.error.URLError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        raise SystemExit(1)

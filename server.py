#!/usr/bin/env python3
"""Adem: loopback-only Linux process dashboard. Python standard library only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
APPS = {
    'spotify': 'Spotify', 'vlc': 'VLC', 'mpv': 'MPV', 'slack': 'Slack',
    'discord': 'Discord', 'Discord': 'Discord', 'telegram-desktop': 'Telegram',
    'Telegram': 'Telegram', 'signal-desktop': 'Signal', 'thunderbird': 'Thunderbird',
    'gimp': 'GIMP', 'gimp-3.0': 'GIMP', 'gimp-2.10': 'GIMP', 'inkscape': 'Inkscape',
    'blender': 'Blender', 'krita': 'Krita', 'soffice.bin': 'LibreOffice',
    'evince': 'Document viewer', 'eog': 'Image viewer', 'totem': 'Video player',
    'rhythmbox': 'Rhythmbox', 'audacity': 'Audacity', 'kdenlive': 'Kdenlive',
    'shotcut': 'Shotcut', 'nautilus': 'Files', 'cosmic-files': 'COSMIC Files',
    'dolphin': 'Dolphin', 'thunar': 'Thunar', 'gedit': 'Text editor',
    'gnome-text-editor': 'Text editor', 'cosmic-edit': 'COSMIC Text editor',
    'code': 'Visual Studio Code', 'code-insiders': 'VS Code Insiders',
    'steam': 'Steam', 'steamwebhelper': 'Steam Web Helper', 'lutris': 'Lutris',
    'missioncenter': 'Mission Center', 'gnome-system-monitor': 'System monitor',
    'cosmic-settings': 'COSMIC Settings', 'cosmic-store': 'COSMIC Store',
    'gnome-calculator': 'Calculator', 'file-roller': 'Archive manager',
    'transmission-gtk': 'Transmission', 'qbittorrent': 'qBittorrent',
}


def read_process(pid):
    try:
        base = Path('/proc') / str(pid)
        uid = base.stat().st_uid
        raw = (base / 'stat').read_text()
        fields = raw[raw.rfind(')') + 2:].split()
        executable = os.readlink(base / 'exe')
        return {'pid': int(pid), 'uid': uid, 'exe': executable,
                'start': fields[19], 'state': fields[0],
                'ticks': int(fields[11]) + int(fields[12]),
                'rss': max(0, int(fields[21])) * os.sysconf('SC_PAGE_SIZE')}
    except (OSError, ValueError, IndexError):
        return None


def process_inventory():
    result = []
    for entry in Path('/proc').iterdir():
        if entry.name.isdigit():
            p = read_process(int(entry.name))
            if p and p['uid'] == os.getuid() and p['state'] != 'Z':
                result.append(p)
    return result


def classify(executable):
    name = Path(executable).name
    if name in APPS:
        return APPS[name], True, 'Closable after confirmation'
    lower = executable.lower()
    if any(x in lower for x in ('chrome', 'chromium', 'firefox', 'brave', 'msedge')):
        return name, False, 'Browser stays open so Adem remains reachable'
    if any(x in lower for x in ('codex', 'claude', 'cursor', 'electron')):
        return name, False, 'Work and agent session protected'
    if any(x in lower for x in ('keepass', 'lastpass', 'bitwarden', '1password', 'keyring', 'vault')):
        return name, False, 'Password manager protected'
    if name in ('obs', 'obs-studio'):
        return name, False, 'Possible recording protected'
    return name, False, 'System, service or unrecognised app'


def app_id(executable):
    return hashlib.sha256(executable.encode()).hexdigest()[:20]


class Monitor:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_cpu = None
        self.last_processes = {}
        self.last_time = time.monotonic()

    def snapshot(self):
        with self.lock:
            return self._snapshot()

    def _snapshot(self):
        processes = process_inventory()
        now = time.monotonic()
        elapsed = max(now - self.last_time, 0.001)
        groups = {}
        ticks_per_second = os.sysconf('SC_CLK_TCK')
        for p in processes:
            key = app_id(p['exe'])
            label, closable, reason = classify(p['exe'])
            if key not in groups:
                groups[key] = {'id': key, 'name': label, 'closable': closable,
                               'reason': reason, 'memory': 0, 'cpu': 0, 'count': 0}
            group = groups[key]
            group['memory'] += p['rss']
            group['count'] += 1
            old = self.last_processes.get((p['pid'], p['start']))
            if old is not None:
                group['cpu'] += max(0, p['ticks'] - old) / ticks_per_second / elapsed * 100
        self.last_processes = {(p['pid'], p['start']): p['ticks'] for p in processes}
        self.last_time = now
        cpu_fields = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
        total, idle = sum(cpu_fields), cpu_fields[3] + cpu_fields[4]
        cpu = None
        if self.last_cpu:
            delta = total - self.last_cpu[0]
            cpu = max(0, min(100, 100 * (1 - (idle - self.last_cpu[1]) / delta))) if delta else 0
        self.last_cpu = total, idle
        memory = {}
        for line in Path('/proc/meminfo').read_text().splitlines():
            key, value = line.split(':', 1)
            memory[key] = int(value.strip().split()[0]) * 1024
        disk = shutil.disk_usage(Path.home())
        return {'hostname': socket.gethostname(), 'cpu': cpu, 'cores': os.cpu_count(),
                'memory': {'total': memory['MemTotal'], 'available': memory['MemAvailable'],
                           'used': memory['MemTotal'] - memory['MemAvailable'],
                           'swapUsed': memory['SwapTotal'] - memory['SwapFree'], 'swapTotal': memory['SwapTotal']},
                'disk': {'total': disk.total, 'used': disk.used, 'free': disk.free},
                'uptime': float(Path('/proc/uptime').read_text().split()[0]),
                'processCount': len(processes), 'apps': sorted(groups.values(), key=lambda x: -x['memory']),
                'updatedAt': time.time()}


class Plans:
    def __init__(self):
        self.items = {}
        self.lock = threading.Lock()

    def create(self, ids):
        if not isinstance(ids, list) or not ids or len(ids) > 100 or any(not isinstance(i, str) for i in ids):
            raise ValueError('Select at least one closable app (maximum 100).')
        chosen = set(ids)
        processes = [p for p in process_inventory() if app_id(p['exe']) in chosen]
        if {app_id(p['exe']) for p in processes} != chosen:
            raise ValueError('De applijst is veranderd. Vernieuw en selecteer opnieuw.')
        if any(not classify(p['exe'])[1] for p in processes):
            raise ValueError('This selection contains a protected app.')
        token = secrets.token_urlsafe(24)
        plan = {'processes': processes, 'expires': time.monotonic() + 60}
        with self.lock:
            self.items = {k: v for k, v in self.items.items() if v['expires'] > time.monotonic()}
            if len(self.items) >= 100:
                raise ValueError('Te veel open plannen. Wacht een minuut en probeer opnieuw.')
            self.items[token] = plan
        return {'plan': token, 'expiresIn': 60,
                'apps': sorted({classify(p['exe'])[0] for p in processes}),
                'processCount': len(processes), 'memory': sum(p['rss'] for p in processes)}

    def execute(self, token):
        if not isinstance(token, str):
            raise ValueError('Invalid close plan.')
        with self.lock:
            plan = self.items.pop(token, None)
        if not plan or plan['expires'] <= time.monotonic():
            raise ValueError('This close plan expired or was already used. Review your selection again.')
        results = []
        sent = []
        for expected in plan['processes']:
            result = {'pid': expected['pid'], 'name': classify(expected['exe'])[0]}
            fd = None
            try:
                fd = os.pidfd_open(expected['pid'])
                current = read_process(expected['pid'])
                if not current:
                    result['status'] = 'already_closed'
                elif any(current[k] != expected[k] for k in ('start', 'exe', 'uid')) or current['uid'] != os.getuid() or not classify(current['exe'])[1]:
                    result['status'] = 'changed'
                else:
                    signal.pidfd_send_signal(fd, signal.SIGTERM)
                    result['status'] = 'pending'
                    sent.append((expected, result))
            except ProcessLookupError:
                result['status'] = 'already_closed'
            except (OSError, AttributeError):
                result['status'] = 'failed'
            finally:
                if fd is not None:
                    os.close(fd)
            results.append(result)
        if sent:
            time.sleep(0.5)
        for expected, result in sent:
            current = read_process(expected['pid'])
            if not current or current['start'] != expected['start'] or current['state'] == 'Z':
                result['status'] = 'closed'
        return {'results': results}


def package_candidates():
    """Read user-level Flatpak packages without changing the system."""
    packages = []
    try:
        output = subprocess.run(['flatpak', 'list', '--user', '--app', '--columns=application,name,version'], capture_output=True, text=True, timeout=8, check=False)
        if output.returncode == 0:
            for line in output.stdout.splitlines():
                parts = line.split('\t')
                if len(parts) >= 2 and parts[0].startswith(('com.', 'org.', 'net.', 'io.')):
                    packages.append({'id': parts[0][:160], 'name': parts[1][:120], 'version': parts[2][:80] if len(parts) > 2 else '', 'manager': 'flatpak-user', 'removable': True, 'note': 'User install; removal also deletes Flatpak app data after confirmation.'})
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {'packages': packages, 'managers': {'flatpakUser': bool(packages), 'systemPackageRemoval': False}, 'note': 'Only user-level Flatpak apps are removable here. System packages require a distro-specific administrator flow outside Adem.'}


def uninstall_package(package_id):
    if not isinstance(package_id, str) or len(package_id) > 160 or not package_id.startswith(('com.', 'org.', 'net.', 'io.')) or any(ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-' for ch in package_id):
        raise ValueError('Only a valid user-level Flatpak application ID can be removed.')
    available = package_candidates()['packages']
    if not any(p['id'] == package_id and p['removable'] for p in available):
        raise ValueError('This Flatpak is not currently installed for your user. Refresh the package list.')
    result = subprocess.run(['flatpak', 'uninstall', '--user', '--delete-data', '--noninteractive', '--', package_id], capture_output=True, text=True, timeout=120, check=False)
    if result.returncode != 0:
        raise OSError((result.stderr or result.stdout or 'Flatpak removal failed.')[-500:])
    return {'status': 'removed', 'id': package_id, 'dataDeleted': True, 'output': (result.stdout or '')[-500:]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # No request bodies, tokens or process details in logs.

    def valid_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

    def respond(self, status, content, content_type='application/json; charset=utf-8'):
        payload = json.dumps(content).encode() if content_type.startswith('application/json') else content
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if not self.valid_host() or self.headers.get('Sec-Fetch-Site') == 'cross-site':
            return self.respond(403, {'error': 'Local access only.'})
        if self.path == '/api/state':
            return self.respond(200, {**self.server.monitor.snapshot(), 'token': self.server.token})
        if self.path == '/api/packages':
            return self.respond(200, self.server.package_candidates())
        files = {'/': ('index.html', 'text/html; charset=utf-8'),
                 '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                 '/style.css': ('style.css', 'text/css; charset=utf-8'),
                 '/icon.svg': ('icon.svg', 'image/svg+xml')}
        if self.path not in files:
            return self.respond(404, {'error': 'Not found.'})
        name, mime = files[self.path]
        self.respond(200, (ROOT / 'web' / name).read_bytes(), mime)

    def do_POST(self):
        origin = self.headers.get('Origin')
        if not self.valid_host() or origin != f'http://{self.headers.get("Host")}' or not secrets.compare_digest(self.headers.get('X-Optimizer-Token', ''), self.server.token):
            return self.respond(403, {'error': 'Invalid local session. Reload the page.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 16384:
                raise ValueError('Invalid request size.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Invalid request.')
            if self.path == '/api/plan':
                result = self.server.plans.create(data.get('apps'))
            elif self.path == '/api/uninstall' and data.get('confirmed') is True:
                result = self.server.uninstall_package(data.get('id'))
            elif self.path == '/api/close' and data.get('confirmed') is True:
                result = self.server.plans.execute(data.get('plan'))
            else:
                raise ValueError('Unknown action or confirmation missing.')
            self.respond(200, result)
        except (ValueError, TypeError, KeyError) as exc:
            self.respond(400, {'error': str(exc)})
        except OSError:
            self.respond(500, {'error': 'Linux could not complete the action. Refresh the page.'})

    def setup(self):
        super().setup()
        self.connection.settimeout(10)


def make_server(port=8765):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.token = secrets.token_urlsafe(32)
    server.monitor = Monitor()
    server.plans = Plans()
    server.package_candidates = package_candidates
    server.uninstall_package = uninstall_package
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Adem — local Linux optimizer')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = make_server(args.port)
    print(f'Adem listening on http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

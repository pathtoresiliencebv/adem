import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


class ProcessSafetyTests(unittest.TestCase):
    def setUp(self):
        self.plans = server.Plans()

    def fake(self, **kwargs):
        return {'pid': 12345, 'start': '987', 'exe': '/usr/bin/vlc', 'uid': os.getuid(), 'rss': 1024, **kwargs}

    def test_protected_process_cannot_be_planned(self):
        for name in ('/usr/bin/chrome', '/usr/bin/codex', '/usr/bin/python3', '/usr/bin/obs', '/usr/bin/bitwarden', '/usr/bin/systemd'):
            with self.subTest(name=name), patch.object(server, 'process_inventory', return_value=[self.fake(exe=name)]):
                with self.assertRaises(ValueError):
                    self.plans.create([server.app_id(name)])

    def test_empty_stale_and_malformed_selection_rejected(self):
        for selection in ([], None, 'vlc', [{}], ['missing']):
            with self.subTest(selection=selection), patch.object(server, 'process_inventory', return_value=[]):
                with self.assertRaises(ValueError):
                    self.plans.create(selection)

    def test_expired_plan_rejected(self):
        self.plans.items['expired'] = {'expires': time.monotonic() - 1, 'processes': []}
        with self.assertRaises(ValueError):
            self.plans.execute('expired')

    def test_pid_identity_revalidated_before_signal(self):
        for changed in (self.fake(start='999'), self.fake(exe='/usr/bin/codex'), self.fake(uid=os.getuid() + 1)):
            with self.subTest(changed=changed):
                self.plans.items['test'] = {'expires': time.monotonic() + 60, 'processes': [self.fake()]}
                with patch.object(os, 'pidfd_open', return_value=99), patch.object(os, 'close'), patch.object(server, 'read_process', return_value=changed), patch.object(server.signal, 'pidfd_send_signal') as send:
                    result = self.plans.execute('test')
                    self.assertEqual(result['results'][0]['status'], 'changed')
                    send.assert_not_called()

    def test_real_owned_disposable_process_stops_and_plan_is_single_use(self):
        # Own temporary sleep binary, named as a recognized app. No existing apps touched.
        with tempfile.TemporaryDirectory(prefix='adem-test-') as directory:
            executable = Path(directory) / 'vlc'
            shutil.copy2('/usr/bin/sleep', executable)
            child = subprocess.Popen([str(executable), '30'])
            try:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    process = server.read_process(child.pid)
                    if process and process['exe'] == str(executable):
                        break
                    time.sleep(0.01)
                self.assertEqual(process['exe'], str(executable))
                plan = self.plans.create([server.app_id(str(executable))])
                self.assertEqual(plan['processCount'], 1)
                result = self.plans.execute(plan['plan'])
                self.assertEqual(result['results'][0]['status'], 'closed')
                self.assertEqual(child.wait(timeout=3), -15)
                with self.assertRaises(ValueError):
                    self.plans.execute(plan['plan'])
            finally:
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=3)

    def test_unavailable_pidfd_fails_closed(self):
        self.plans.items['test'] = {'expires': time.monotonic() + 60, 'processes': [self.fake()]}
        with patch.object(os, 'pidfd_open', side_effect=OSError('unsupported')), patch.object(server.signal, 'pidfd_send_signal') as send:
            result = self.plans.execute('test')
            self.assertEqual(result['results'][0]['status'], 'failed')
            send.assert_not_called()


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = server.make_server(0)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.host = f'127.0.0.1:{cls.http.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()

    def request(self, path, method='GET', data=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        try:
            connection.request(method, path, body=json.dumps(data) if data is not None else None, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_live_metrics_and_no_command_lines(self):
        status, headers, body = self.request('/api/state')
        state = json.loads(body)
        self.assertEqual(status, 200)
        self.assertGreater(state['memory']['total'], 0)
        self.assertGreater(state['processCount'], 0)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertNotIn('cmdline', state['apps'][0])
        self.assertNotIn('exe', state['apps'][0])

    def test_host_and_cross_site_reads_blocked(self):
        for headers in ({'Host': 'attacker.invalid'}, {'Sec-Fetch-Site': 'cross-site'}):
            self.assertEqual(self.request('/api/state', headers=headers)[0], 403)

    def test_mutation_requires_token_and_exact_origin(self):
        for headers in ({}, {'Origin': f'http://{self.host}'}, {'Origin': 'https://evil.example', 'X-Optimizer-Token': self.http.token}):
            with patch.object(self.http.plans, 'create') as create:
                self.assertEqual(self.request('/api/plan', 'POST', {'apps': ['anything']}, headers)[0], 403)
                create.assert_not_called()

    def test_confirmation_required_and_unknown_routes_rejected(self):
        headers = {'Origin': f'http://{self.host}', 'X-Optimizer-Token': self.http.token}
        self.assertEqual(self.request('/api/close', 'POST', {'plan': 'anything'}, headers)[0], 400)
        self.assertEqual(self.request('/api/close', 'POST', {'plan': 'anything', 'confirmed': True}, headers)[0], 400)
        self.assertEqual(self.request('/../../server.py')[0], 404)

    def test_static_security_headers(self):
        for path in ('/', '/app.js', '/style.css', '/icon.svg'):
            status, headers, _ = self.request(path)
            self.assertEqual(status, 200)
            self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])


if __name__ == '__main__':
    unittest.main()

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import catchme_export


class CatchMeExportTests(unittest.TestCase):
    def test_export_is_bounded_and_redacted(self):
        state = {'hostname': 'test-host', 'apps': [
            {'name': 'Browser', 'memory': 900 * 1024 * 1024, 'cpu': 20, 'count': 4, 'closable': False, 'reason': 'protected', 'id': 'secret-id'},
            {'name': '/home/jason/private', 'memory': 1, 'cpu': 0, 'count': 1, 'closable': False, 'reason': 'unknown'},
        ]}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return json.dumps(state).encode()
            def __iter__(self): return iter(())
        Response.__iter__ = None
        with tempfile.TemporaryDirectory() as directory, patch.object(catchme_export.urllib.request, 'urlopen', return_value=Response()):
            payload, destination = catchme_export.export(destination=Path(directory) / 'integrations' / 'snapshot.json')
            self.assertEqual(payload['schema'], 'adem.catchme.processes.v1')
            self.assertEqual(len(payload['expensiveProcesses']), 1)
            self.assertNotIn('id', payload['expensiveProcesses'][0])
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(destination.read_text())['actions'], [])


if __name__ == '__main__':
    unittest.main()

"""Public CLI boundaries: no paid dry-runs, no overwrites, grade after commit."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from mah2.appworld_cli import main


class AppWorldCLITests(unittest.TestCase):
    def args(self, root):
        task = root/'world/data/tasks/abc_1'
        task.mkdir(parents=True)
        (task/'specs.json').write_text(json.dumps({'instruction': 'Inspect public state.'}))
        return ['--task', 'abc_1', '--appworld-root', str(root/'world'),
                '--appworld-python', sys.executable, '--output', str(root/'run')]

    def test_dry_run_needs_no_credentials_and_creates_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = self.args(root)
            with patch('mah2.gateway.Gateway', side_effect=AssertionError('No calls')), contextlib.redirect_stdout(io.StringIO()) as stream:
                self.assertEqual(main(args), 0)
            self.assertFalse(json.loads(stream.getvalue())['paid_calls'])
            self.assertFalse((root/'run').exists())

    def test_rejects_existing_output_invalid_budget_and_task_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = self.args(root)
            for suffix in (['--budget', '2'], ['--task', '../abc_1']):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(args + suffix)
            (root/'run').mkdir()
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(args)

    def test_official_grade_follows_commit_and_failure_keeps_artifacts(self):
        class Gateway:
            charged = .01
            calls = []
            def __init__(self, *args, **kwargs): pass
            def set_stage(self, *args): pass
        class Team:
            def __init__(self, *args, **kwargs): pass
            def run(self): return {'runnable': True, 'completed': True, 'task_id': 'abc_1', 'experiment': 'fixture'}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = self.args(root) + ['--method', 'base', '--execute', '--grade']
            def grade(outcome, destination):
                self.assertTrue((destination/'commit.json').is_file())
                self.assertIsNone(json.loads((destination/'commit.json').read_text())['official_success'])
                raise RuntimeError('fixture grader failure')
            with patch('mah2.gateway.Gateway', Gateway), patch('mah2.gateway.load_api_key', return_value='fixture'), patch('mah2.appworld_adapter.Team', Team), patch('mah2.appworld_adapter.grade_selected', side_effect=grade), patch.dict('os.environ'), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 1)
            result = json.loads((root/'run/result.json').read_text())
            self.assertIn('fixture grader failure', result['error'])
            self.assertIsNone(result['official_success'])
            self.assertEqual(result['charged_or_reserved_usd'], .01)


if __name__ == '__main__':
    unittest.main()

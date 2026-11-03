import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from mah2.adapters import TeamResult, optimize_team
from mah2.dsstar.harness import initial

spec = importlib.util.spec_from_file_location('team_example', Path(__file__).parents[1]/'examples/existing_team.py')
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)


class CustomTeamTests(unittest.TestCase):
    def config(self):
        return dict(allowance_usd=0, input_per_million=0, output_per_million=0,
                    stage_shares=dict(reference=.25,proposal_a=.08,proposal_b=.08,
                    candidate_a=.14,candidate_b=.14,composer=.1,successor=.1,selector=.08,reflector=.03))

    def test_existing_harness_fresh_workspaces_current_round_reuse(self):
        seen = []
        base = initial();base['roles']['coder'] = 'Existing team procedure'
        untouched = copy.deepcopy(base)
        def execute(**kwargs):
            seen.append((kwargs['workspace'], copy.deepcopy(kwargs['harness'])))
            self.assertEqual(list(kwargs['workspace'].iterdir()), [])
            result = example.execute_team(**kwargs)
            kwargs['harness']['roles']['coder'] = 'callback mutation'
            return result
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'run'
            commit=optimize_team(executor=execute,task={'task_inst':'Add 2 and 3'},data=Path(tmp),
                output=root,config=self.config(),starting_harness=base,client_factory=example.ScriptedClient)
            self.assertEqual(len(seen),6)
            self.assertEqual(len({p for p,h in seen}),6)
            self.assertTrue(all(h == base for p,h in seen))
            self.assertEqual(base,untouched)
            self.assertTrue(commit['runnable'])
            self.assertIsNone(commit['official_success'])
            for n in (1,2):
                for stage in ('proposal_a','proposal_b','composer'):
                    self.assertTrue(json.loads((root/f'round_{n}/{stage}_decision.json').read_text())['valid'])
                record=json.loads((root/f'round_{n}/successor_reuse.json').read_text())
                self.assertEqual(record['source_stage'],'reference')
                selection=json.loads((root/f'round_{n}/selection.json').read_text())
                self.assertTrue(selection['valid'])
            with self.assertRaises(FileExistsError):
                optimize_team(executor=execute,task={'task_inst':'Add'},data=Path(tmp),output=root,
                    config=self.config(),starting_harness=base,client_factory=example.ScriptedClient)

    def test_invalid_budget_split_does_not_execute(self):
        c=self.config();c['stage_shares']['reference']=.9
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            optimize_team(executor=lambda **kw:self.fail('must not execute'), task={'task_inst':'Add'},
                data=Path(tmp),output=Path(tmp)/'run',config=c,starting_harness=initial(),client_factory=example.ScriptedClient)

    def test_separate_edits_composition_and_selected_state_carry_forward(self):
        class Editors(example.ScriptedClient):
            def complete(self, prompt, role=None):
                if self.stage == 'selector':
                    return json.dumps({'selected':'successor','evidence':['successor:e0000']})
                if self.stage == 'reflector':return '{"lesson":null}'
                ev=json.JSONDecoder().raw_decode(prompt[prompt.index('\n{')+1:])[0]
                h=copy.deepcopy(ev['base_harness'])
                if self.stage in ('proposal_a','proposal_b'):
                    assert set(ev['runs']) == {'reference'}
                    assert 'candidates' not in ev
                if self.stage == 'proposal_a':h['roles']['coder']='Check public inputs'
                if self.stage == 'proposal_b':
                    h['coordination']['coder_receives_question']=True
                    h['coordination']['version']+=1
                if self.stage == 'composer':
                    h=copy.deepcopy(ev['candidates']['a']['harness'])
                    h['coordination']=copy.deepcopy(ev['candidates']['b']['harness']['coordination'])
                return json.dumps({'harness':h,'evidence':['candidate_b:e0000' if self.stage=='composer' else 'reference:e0000']})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'run'
            optimize_team(executor=example.execute_team,task={'task_inst':'Add'},data=Path(tmp),
                output=root,config=self.config(),starting_harness=initial(),client_factory=Editors)
            first=root/'round_1'
            for name in ('proposal_a','proposal_b','composer'):
                self.assertTrue(json.loads((first/f'{name}_decision.json').read_text())['valid'], (first/f'{name}_decision.json').read_text())
            a=json.loads((first/'candidate_a_harness.json').read_text())
            b=json.loads((first/'candidate_b_harness.json').read_text())
            self.assertEqual(a['coordination'],initial()['coordination'])
            self.assertEqual(b['roles'],initial()['roles'])
            selected=json.loads((first/'selected_harness.json').read_text())
            self.assertEqual(selected['roles'],a['roles'])
            self.assertEqual(selected['coordination'],b['coordination'])
            self.assertFalse((first/'successor_reuse.json').exists())
            self.assertEqual(selected,json.loads((root/'round_2/reference_harness.json').read_text()))

    def test_explicit_gateway_is_used_and_charged(self):
        from types import SimpleNamespace
        from mah2.dsstar.provider import Client, Budget
        gateway=SimpleNamespace(charged=0, set_stage=lambda *args:None)
        def request(payload):
            gateway.charged+=.01
            return {'choices':[{'message':{'content':'ok'}}]}
        gateway.request=request
        budget=Budget(.1)
        client=Client({},budget,Path('run/ledger.jsonl'),gateway=gateway)
        self.assertEqual(client.complete('public prompt'),'ok')
        self.assertAlmostEqual(budget.charged,.01)

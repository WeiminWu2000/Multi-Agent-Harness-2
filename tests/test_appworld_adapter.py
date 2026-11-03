import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mah2.appworld_adapter import Team
from mah2.dsstar.harness import initial


class AppWorldAdapterTests(unittest.TestCase):
    def test_mass_custom_workflow_survives_released_parser_and_revision(self):
        from mah2 import mass_rhi
        class Checked(Exception): pass
        class Gateway:
            charged=0.
        def check(cfg,tasks):
            query=mass_rhi.pipeline.ROOT/f'tasks/initial/query{tasks[0]}_ourTeam.txt'
            template=mass_rhi.rhi._read_query_template(query,
                start_marker=mass_rhi.rhi.DEFAULT_START_MARKER,
                end_marker='END OF EDITABLE TEAM WORKFLOW')
            self.assertEqual(template.task_text_for_eval,'public task')
            self.assertIn('inspect APIs',template.design_block)
            self.assertNotIn('fixed API restrictions',template.design_block)
            revised=mass_rhi.rhi._normalize_generated_design_block(
                template.design_block+'\nrepair handoffs\n'+template.after_design,
                start_marker=mass_rhi.rhi.DEFAULT_START_MARKER,
                end_marker='END OF EDITABLE TEAM WORKFLOW',after_design=template.after_design)
            self.assertIn('repair handoffs',revised)
            self.assertNotIn('fixed API restrictions',revised)
            raise Checked()
        with tempfile.TemporaryDirectory() as tmp, patch.object(mass_rhi.pipeline,'search',side_effect=check):
            with self.assertRaises(Checked):
                mass_rhi.run(Gateway(),{'model':'fixture','mass_rhi':{'iterations':2}},
                    {'task_inst':'public task'},Path(tmp),Path(tmp)/'search',1,1.,
                    footer='fixed API restrictions',design_override='inspect APIs')

    def test_manifest_has_disjoint_scenarios_and_balanced_categories(self):
        root=Path(__file__).resolve().parents[1]
        m=json.loads((root/'config/appworld_tasks.json').read_text())
        self.assertEqual(len(m['debug']),5)
        self.assertEqual(len(m['evaluation']),20)
        self.assertEqual(len({r['scenario'] for r in m['evaluation']}),20)
        self.assertFalse({r['scenario'] for r in m['debug']} & {r['scenario'] for r in m['evaluation']})
        for domain in ('music','finance'):
            self.assertEqual(sum(r['domain']==domain for r in m['evaluation']),10)
        self.assertTrue(all(r['split']=='test_normal' for r in m['evaluation']))
        self.assertTrue(all(r['split']=='dev' for r in m['debug']))

    def test_handoff_contract_and_public_history_reach_receiver(self):
        class Gateway:
            payload=None
            def request(self,payload):
                self.payload=payload
                return {'choices':[{'message':{'content':'{"plan":"inspect"}'}}]}
        with tempfile.TemporaryDirectory() as tmp:
            h=initial();h['coordination']['version']=2
            h['coordination']['contracts']['verifier.planner']={
                'version':2,'fields':['verification'],'sender_instruction':'cite observations',
                'receiver_instruction':'repair the observed failure'}
            g=Gateway();team=Team(g,{},Path(tmp)/'run','fixture',h)
            team.info={'instruction':'fixture'}
            team.state['verification']='observed missing field'
            team.event(kind='execution',code='print(1)',output='1',completed=False)
            team.ask('planner','plan')
            prompt=json.loads(g.payload['messages'][1]['content'])
            self.assertEqual(prompt['handoff']['verification'],'observed missing field')
            self.assertIn('repair the observed failure',prompt['contracts'])
            self.assertEqual(prompt['recent_public_interactions'][0]['output'],'1')
            self.assertNotIn('grade',prompt)


if __name__=='__main__':unittest.main()

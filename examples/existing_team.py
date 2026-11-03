"""Offline integration smoke: real Python execution, scripted optimizer responses.

Replace execute_team and ScriptedClient with your existing team and a model client.
This checks wiring and isolation; it is not evidence of optimization quality.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from mah2.adapters import TeamResult, optimize_team
from mah2.dsstar.harness import initial


class ScriptedClient:
    def __init__(self, config, budget, ledger, stage):
        self.stage = stage

    def complete(self, prompt, role=None):
        # The integration test deliberately proposes no changes.
        if self.stage == 'selector':
            return json.dumps({'selected':'reference','evidence':['reference:e0000']})
        if self.stage == 'reflector':
            return '{"lesson":null}'
        evidence = json.JSONDecoder().raw_decode(prompt[prompt.index('\n{')+1:])[0]
        return json.dumps({'harness':evidence['base_harness'], 'evidence':[]})


def execute_team(*, harness, task, data, workspace, client):
    # Trusted fixed Python only: replace this callback with an isolated team run.
    # A real adapter must apply harness['roles'] to prompts and the coordination
    # contracts to its handoffs; this no-op smoke does not implement a full team.
    program = 'print(sum([2, 3]))\n'
    completed = subprocess.run([sys.executable, '-c', program], cwd=workspace,
                               capture_output=True, text=True, timeout=10)
    return TeamResult(program, completed.returncode == 0,
                      [{'kind':'execution', 'stdout':completed.stdout,
                        'stderr':completed.stderr}],
                      {'sum_matches_public_requirement':completed.stdout.strip() == '5'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    shares = dict(reference=.25,proposal_a=.08,proposal_b=.08,candidate_a=.14,
                  candidate_b=.14,composer=.10,successor=.10,selector=.08,reflector=.03)
    harness = initial()
    harness['roles']['coder'] = 'Compute the requested sum with Python.'
    result = optimize_team(executor=execute_team, task={'task_inst':'Compute 2 + 3.'},
                           data=Path.cwd(), output=args.output, starting_harness=harness,
                           config=dict(allowance_usd=0, stage_shares=shares,
                                       input_per_million=0, output_per_million=0),
                           client_factory=ScriptedClient)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

"""Bring an existing team to the same optimizer used by the AppWorld adapter.

Install from a checkout and fetch pinned dependencies before importing this module.
The executor owns environment isolation; only public observations may be returned.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .appworld_optimizer import AppWorldExperiment
from .dsstar.harness import initial, validate
from .dsstar.optimizer import Experiment
from .dsstar.recursion import run_recursive


@dataclass
class TeamResult:
    """Executable deliverable and public evidence, never official grading results."""

    program: str
    runnable: bool
    trace: list[dict]
    observations: dict = field(default_factory=dict)


def optimize_team(*, executor: Callable, task: dict, data: Path, output: Path,
                  config: dict, starting_harness: dict, rounds: int = 2,
                  client_factory) -> dict:
    """Adapt an existing seven-role team using independent role/coordination edits.

    executor(harness=..., task=..., data=..., workspace=..., client=...) -> TeamResult
    Each call must reset external state and apply both role and handoff instructions.
    Route every model call through the supplied budgeted client. The callback may
    use workspace for artifacts; it must not run a hidden/official evaluator.
    See docs/custom_teams.md for the executable contract and limitations.
    """
    validate(starting_harness, initial(), 'composer')
    if not isinstance(task.get('task_inst'), str) or not task['task_inst'].strip():
        raise ValueError('task_inst must be a nonempty public instruction')
    data = Path(data).resolve()
    if not data.is_dir():
        raise ValueError('data must be an existing public-input directory')
    cfg = copy.deepcopy(config)
    cfg.update(selection_pool='current-round', retain_candidate_archive=False,
               reuse_identical_successor=True, public_selection=True,
               runnable_fallback=True, codex_coordination=False,
               scoped_glm_coordination=False)
    if cfg.get('allowance_usd', -1) < 0:
        raise ValueError('allowance_usd must be nonnegative')
    stages = {'reference','proposal_a','proposal_b','candidate_a','candidate_b',
              'composer','successor','selector','reflector'}
    shares = cfg.get('stage_shares', {})
    if set(shares) != stages or any(v < 0 for v in shares.values()) or abs(sum(shares.values())-1) > 1e-9:
        raise ValueError('stage_shares must allocate exactly one allowance across all stages')

    class AdaptedTeam(AppWorldExperiment):
        task_domain = 'user-provided team'

        def __init__(self, config, directory):
            super().__init__(config, directory, client_factory=client_factory)

        client = Experiment.client

        def run_team(self, stage, harness, packet, data):
            (self.root/(stage+'_harness.json')).write_text(json.dumps(harness, indent=2))
            workspace = self.root/stage
            workspace.mkdir()
            result = executor(harness=copy.deepcopy(harness), task=copy.deepcopy(packet),
                              data=data, workspace=workspace, client=self.client(stage))
            if not isinstance(result, TeamResult) or type(result.runnable) is not bool:
                raise TypeError('executor must return TeamResult with a boolean runnable flag')
            if not isinstance(result.program, str) or (result.runnable and not result.program.strip()):
                raise ValueError('runnable result requires a saved executable program')
            events = []
            for index, event in enumerate(result.trace):
                if not isinstance(event, dict):
                    raise TypeError('trace events must be dictionaries')
                events.append(dict(event, id=f'e{index:04d}'))
            outcome = dict(runnable=result.runnable,
                           program_sha256=hashlib.sha256(result.program.encode()).hexdigest(),
                           public_observations=result.observations)
            (workspace/'submission.py').write_text(result.program)
            (workspace/'trace.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
            (workspace/'outcome.json').write_text(json.dumps(outcome, indent=2))
            return outcome

    return run_recursive(cfg, output, 'multi_agent', task, data, [], rounds,
                         AdaptedTeam, starting_harness=starting_harness)

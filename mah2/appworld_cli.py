"""Portable AppWorld entrypoint; dry-run by default, grading after commitment."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]


def prepare(args):
    config = json.loads(Path(args.config).read_text())
    if not re.fullmatch(r'[a-fA-F0-9]+_[0-9]+', args.task):
        raise ValueError('Use an AppWorld task ID, e.g. 4ec8de5_1')
    if not 0 < args.budget <= config['budget']['per_method_task_cap']:
        raise ValueError('Budget must be positive and within the configured per-task cap')
    root = Path(args.appworld_root).expanduser().resolve()
    python = Path(args.appworld_python).expanduser().absolute()
    output = Path(args.output).expanduser().resolve()
    if output.exists():
        raise ValueError('Output already exists; choose a fresh directory')
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError('AppWorld data and run output must be disjoint')
    specs = root / 'data/tasks' / args.task / 'specs.json'
    instruction = json.loads(specs.read_text())['instruction']
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError('AppWorld Python executable is missing')
    return config, root, python, output, {'task_inst': instruction}


def execute(args, prepared):
    config, data_root, python, output, packet = prepared
    # Import optional prompt dependencies before creating a paid occurrence.
    from .appworld_adapter import Team, grade_selected, write_json
    from .gateway import Gateway, load_api_key
    if args.method == 'harness2':
        from .appworld_optimizer import AppWorldExperiment
        from .dsstar.recursion import run_recursive
    if args.method == 'mass':
        from .mass_rhi import run as mass_run
    load_api_key()
    os.environ['APPWORLD_ROOT'] = str(data_root)
    os.environ['MAH2_APPWORLD_PYTHON'] = str(python)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output/'config.json', config)
    write_json(output/'packet.json', packet)
    write_json(output/'source_hashes.json', {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT/'mah2').rglob('*.py')})
    gateway = Gateway(output/'api', config, cap=args.budget)
    result = dict(task=args.task, method=args.method, model=config['model'],
                  cap_usd=args.budget, evaluation='not_run', official_success=None)
    try:
        if args.method == 'base':
            gateway.set_stage('base', args.budget)
            outcome = Team(gateway, config, output/'rollout', args.task).run()
        elif args.method == 'harness2':
            AppWorldExperiment.gateway = gateway
            AppWorldExperiment.task_id = args.task
            run_recursive({**config['dsstar'], 'allowance_usd': args.budget},
                          output/'optimization', 'multi_agent', packet, output, [],
                          config['outer_cycles'], AppWorldExperiment)
            outcome = json.loads((output/'optimization/successor/outcome.json').read_text())
            result['selection'] = json.loads((output/'optimization/commit.json').read_text())
        else:
            def episode(gateway, harness, packet, data, directory, config, prompt_override):
                directory.mkdir(parents=True, exist_ok=False)
                outcome = Team(gateway, config, directory/'work', args.task,
                               workflow=prompt_override).run()
                (directory/'work/logs.txt').write_text((directory/'work/trace.jsonl').read_text())
                return dict(agent={'returncode': 0 if outcome['runnable'] else 1},
                            runnable=outcome['runnable'])
            result['search'] = mass_run(
                gateway, {**config, 'public_context': False}, packet, output,
                output/'search', int(args.task.split('_')[0], 16),
                args.budget, episode_adapter=episode,
                footer='Use the documented AppWorld Python APIs and complete the task in simulated app state. Do not produce a CSV submission or access hidden evaluation. The executor is the shared seven-role team; workflow text can guide all its roles.',
                design_override='Analyze API documentation, plan, execute code, verify public observations, route to repair or finalize. Preserve task requirements across role handoffs.')
            outcome = json.loads((Path(result['search']['selected'])/'work/outcome.json').read_text())
        write_json(output/'commit.json', dict(outcome=outcome,
                   selection=result.get('selection'), official_success=None))
        result['outcome'] = outcome
        if args.grade:
            result['grade'] = grade_selected(outcome, output)
            result.update(evaluation='official', official_success=result['grade']['success'])
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
        (output/'error.txt').write_text(traceback.format_exc())
    finally:
        result.update(charged_or_reserved_usd=gateway.charged, api_calls=len(gateway.calls))
        write_json(output/'result.json', result)
    print(json.dumps(result, indent=2))
    return int('error' in result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', required=True)
    parser.add_argument('--method', choices=['base', 'harness2', 'mass'], default='harness2')
    parser.add_argument('--config', default=str(ROOT/'config/appworld.json'))
    parser.add_argument('--output', required=True)
    parser.add_argument('--appworld-root', default=os.environ.get('APPWORLD_ROOT', str(ROOT/'appworld_data')))
    parser.add_argument('--appworld-python', default=os.environ.get('MAH2_APPWORLD_PYTHON', str(ROOT/'.venv-appworld/bin/python')))
    parser.add_argument('--budget', type=float, default=1.)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--execute', action='store_true', help='Permit paid model calls')
    group.add_argument('--dry-run', action='store_true', help='Check paths/configuration without calls (default)')
    parser.add_argument('--grade', action='store_true', help='Run official evaluation after final commitment')
    args = parser.parse_args(argv)
    try:
        prepared = prepare(args)
        if not args.execute:
            print(json.dumps(dict(valid=True, paid_calls=False, task=args.task,
                       method=args.method, model=prepared[0]['model'], budget_usd=args.budget,
                       note='Configuration check only; worker runtime not exercised'), indent=2))
            return 0
        return execute(args, prepared)
    except (ValueError, OSError, KeyError, RuntimeError, ImportError) as exc:
        parser.exit(2, f'{type(exc).__name__}: {exc}\n')


if __name__ == '__main__':
    sys.exit(main())

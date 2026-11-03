"""Isolated AppWorld process: public interaction OR post-commit grading."""
import argparse
import contextlib
import json
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--task', required=True)
    p.add_argument('--experiment', required=True)
    p.add_argument('--grade', action='store_true')
    a = p.parse_args()
    # AppWorld freezes time and maintains global database state. Keep it out of
    # the budget gateway process; a new worker always starts from task inputs.
    with contextlib.redirect_stdout(sys.stderr):
        if a.grade:
            from appworld.evaluator import evaluate_task
            report = evaluate_task(a.task, experiment_name=a.experiment)
            result = dict(success=report.success, tests=report.to_dict(stats_only=True))
        else:
            from appworld import AppWorld
            world = AppWorld(a.task, experiment_name=a.experiment,
                             load_ground_truth=False, timeout_seconds=45,
                             max_interactions=100, max_api_calls_per_interaction=100)
            result = dict(instruction=world.task.instruction,
                          supervisor=dict(world.task.supervisor),
                          datetime=str(world.task.datetime),
                          app_descriptions=world.task.app_descriptions)
    print(json.dumps(result), flush=True)
    if a.grade:
        return
    try:
        for line in sys.stdin:
            request = json.loads(line)
            if request.get('close'):
                break
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    output = world.execute(request['code'])
                    completed = world.task_completed()
                response = dict(output=output, completed=completed)
            except Exception as exc:
                response = dict(output=f'{type(exc).__name__}: {exc}', completed=False, error=True)
            print(json.dumps(response), flush=True)
    finally:
        with contextlib.redirect_stdout(sys.stderr):
            world.close()


if __name__ == '__main__':
    main()

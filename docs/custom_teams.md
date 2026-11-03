---
noteId: "cc6f6840d71e11f1b34a5356bbd762cf"
tags: []

---

# Connect an existing multi-agent team

`mah2.adapters.optimize_team` wraps your executor with the same role editor, coordination editor, composer, selector, and task-local recursion used by the AppWorld adapter. It does not replace your team with the built-in executor. Install from a checkout and run `python scripts/fetch_dependencies.py` first; the optimizer imports pinned upstream prompt code from `vendor/`.

## Start with the integration smoke test

```bash
python examples/existing_team.py --output runs/my-team-smoke
```

This uses scripted no-op editors and executes trusted Python in six fresh workspaces over two rounds. Each successor reuses its reference execution. It makes no API calls and does not demonstrate scientific improvement. `mah2 demo --output runs/demo` is the separate teaching example with role and coordination repairs and public toy checks.

## Supply your team

Call `optimize_team` with `executor`, `task`, `data`, `output`, `config`, and `starting_harness`, as in the example. Replace `ScriptedClient` with your budgeted provider client. Its constructor receives `(config, budget, ledger, stage)`; implement `complete(prompt, role=None)`, check the remaining `budget.cap - budget.charged` before calls, update `budget.charged` for every call, and write usage to `ledger`. The built-in GLM client accepts an explicit gateway, as shown below. Paid execution requires provider credentials and positive allowances; the smoke example's zero allowance is intentional.

The executor has this signature:

```python
def execute_team(*, harness, task, data, workspace, client) -> TeamResult:
    ...
```

Implement these parts in your callback:

1. Create a fresh team and reset its environment for every call. The controller creates a new workspace, but it cannot reset an external service for you.
2. Append `harness['roles'][role]` to the corresponding role's existing instructions. Keep your base instructions in `starting_harness` or your executor, consistently across candidates.
3. Apply coordination flags and contracts at the actual handoff. The sender receives `sender_instruction`; the receiver receives only the listed current `fields` plus `receiver_instruction`. Update state before passing it on. Do not merely print the contract into a trace.
4. Route all model calls through `client.complete(prompt, role=role)` so execution and editing consume the same allowance. An executor that calls a separate API bypasses this accounting and must not claim the same budget guarantee. Enforce tool and wall-clock limits in your executor.
5. Return `TeamResult(program, runnable, trace, observations)`. `program` is the Python deliverable or replay script. Trace entries are public event dictionaries; the adapter assigns stable event IDs. Observations describe public checks, not official scores. Catch expected execution failures and return `runnable=False`; unexpected callback exceptions stop the run and preserve its existing files.

The controller writes `submission.py`, `trace.jsonl`, and `outcome.json` in each workspace. Do not return secrets, hidden targets, grader code, or private observations. It saves the selected program hash before returning. Run your official evaluator outside this function, after commitment; never feed its outcome back into the current task's proposals or selection.

## Supported surface and limits

This release uses the paper's seven logical roles: analyzer, planner, coder, verifier, router, debugger, and finalizer. Map your system to these roles; several roles may share a model or implementation. Arbitrary role names and new graph edges require an executor/schema extension and are not supported by this API.

Use `mah2.dsstar.harness.initial()` to obtain the schema, then populate it with your existing team's procedures and supported coordination. `starting_harness` is copied and used for the first reference; later references use the selected harness. The adapter never imports an earlier task's memory. Both editors receive the same reference evidence independently. Role edits preserve coordination; coordination edits preserve roles and change one existing mechanism. The composer retains a tested coordination option. Candidate selection is limited to runnable current-round programs.

Same-round reuse requires an identical complete harness and a matching saved program hash. For interactive tasks, keep the corresponding environment snapshot/artifacts with that workspace so the final evaluator can grade the selected state. A script hash alone does not attest to an external service state. The AppWorld adapter manages its own experiment state; custom callbacks must provide an equivalent contract.

`config` contains the provider settings, total `allowance_usd`, token prices (`input_per_million`, `output_per_million`), and `stage_shares` shown in the example. Stage shares must sum to one. `budget_policy='carry_forward'` enables unused-prefix allowance reuse. The optimizer divides the total allowance across rounds. Run independent tasks in separate processes; existing provider integrations are not designed for concurrent tasks in one process.

The trace-based adapter shares AppWorld's selection procedure. It does not add the scientific-file adapter's structured executable probe requirement. Runnable means execution succeeded, not that the scientific task passed, and adaptation does not guarantee an improvement over your initial team.

## Use the built-in budgeted GLM client

After implementing `execute_team`, the following wiring uses the existing gateway without process-global bindings. Set `OPENROUTER_API_KEY_FILE` outside the source tree before running it. Check the configured model and token prices with your provider before paid work.

```python
import json
from functools import partial
from pathlib import Path
from mah2.adapters import optimize_team
from mah2.dsstar.harness import initial
from mah2.dsstar.provider import Client
from mah2.gateway import Gateway

settings = json.loads(Path('config/appworld.json').read_text())
allowance = 1.0
config = {**settings['dsstar'], 'allowance_usd': allowance,
          'input_per_million': settings['budget']['input_per_million'],
          'output_per_million': settings['budget']['output_per_million']}
gateway = Gateway(Path('runs/custom-api'), settings, cap=allowance)
harness = initial()  # Populate with your current team instructions and contracts.
commit = optimize_team(
    executor=execute_team, task={'task_inst': 'Your public task instruction'},
    data=Path('tasks/my-task/data'), output=Path('runs/custom-optimization'),
    config=config, starting_harness=harness, rounds=2,
    client_factory=partial(Client, gateway=gateway),
)
```

Use fresh paths for each task. This direct client does not start an HTTP server. The gateway records requests and usage in `runs/custom-api`; keep this directory private because prompts may contain task data.

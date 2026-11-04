# Architecture

SciMARS has an execution team and a separate optimizer. The AppWorld adapter runs the same seven roles under each method. A harness contains role procedures and a structured coordination object. The optimizer changes these instructions and handoffs; the scheduler, tools, model, budget, and evaluator remain outside the editable surface.

## Execution team

The analyzer inspects public API documentation and state. The planner proposes the next action. The coder executes Python against AppWorld's documented APIs. The verifier checks public observations, and the router chooses whether to continue or finalize. The debugger repairs execution errors. The finalizer submits an answer or completes the task through the supervisor API.

Python variables and app state persist within one candidate execution. Each candidate starts a new worker from the original task state. Roles receive bounded public interaction history and the fields specified by their handoff contracts. AppWorld interaction happens through its own execution safeguards; this adapter does not claim an additional container isolation boundary.

## Revision loop

Each outer round executes a reference, proposes role and coordination edits, probes both, composes a successor, selects an execution, and extracts a lesson. The AppWorld configuration uses two rounds.

The role editor preserves the full coordination object. The coordination editor preserves all roles and changes one existing route or contract. A contract defines producer and consumer instructions plus the fields passed between them. The composer may retain base coordination or adopt the exact tested coordination candidate. A changed harness requires citations to supplied public trace events.

A distinct composed harness executes in a fresh world. If it exactly matches a runnable same-round candidate and that candidate's saved program hash verifies, the controller reuses the execution and records its provenance. The selector does not count the alias as another candidate.

Selection includes only the current round's reference, role candidate, coordination candidate, and distinct successor. Earlier traces can inform proposals, but unselected earlier programs cannot return as selectable candidates. The selected harness and task-local lessons carry forward. If all current-round executions fail, the controller does not silently return an older program.

## Evidence and evaluation

The AppWorld selector uses public observations and task requirements. A completion flag or a runnable trajectory is not an official success. The final selected state and generating harness are committed before the optional evaluator runs in a separate process. Official tests and scores are not passed to the editors, composer, or selector.

This is task-local harness adaptation. The meta-level optimizer does not modify its own implementation, and the default runner does not share learned harnesses across benchmark tasks.

## Code map

| Component | Canonical implementation |
|---|---|
| AppWorld command and final commitment | `mah2/appworld_cli.py` |
| Seven-role team and handoffs | `mah2/appworld_adapter.py` |
| AppWorld process and official evaluation | `mah2/appworld_worker.py` |
| Public-evidence edits and selection | `mah2/appworld_optimizer.py` |
| Harness schema and scope validation | `mah2/dsstar/harness.py` |
| Candidate execution, composition, reuse | `mah2/dsstar/optimizer.py` |
| Task-local outer rounds | `mah2/dsstar/recursion.py` |
| Shared API budget | `mah2/gateway.py` |
| Optional MASS workflow search | `mah2/mass_rhi.py` |

The local scientific Python adapter uses the same harness and recursion modules with a bubblewrap execution backend. See [setup](setup.md) for its separate environment requirements.

## Existing-team integration

`mah2.adapters.optimize_team` accepts an existing harness and execution callback. It reuses the AppWorld trace-based editor and selector plus the common recursive controller. The callback applies the supported seven-role schema to the user’s team and owns isolation. See [the adapter contract](custom_teams.md). This is task-local adaptation, not optimizer self-modification or demonstrated cross-task transfer.

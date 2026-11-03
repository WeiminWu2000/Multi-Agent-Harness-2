"""Shared same-round reuse rule for adapters and the offline demo."""
import hashlib
import json

def execute_successor(config, root, harness, candidates, execute):
    """Optionally reuse an identical runnable harness from this round only."""
    if config.get('reuse_identical_successor', False):
        for label, tested_harness in candidates:
            if harness != tested_harness:
                continue
            path = root / label
            outcome = json.loads((path / 'outcome.json').read_text())
            program = path / 'submission.py'
            if not outcome.get('runnable') or not program.is_file():
                continue
            digest = hashlib.sha256(program.read_bytes()).hexdigest()
            if digest != outcome.get('program_sha256'):
                continue
            (root / 'successor').symlink_to(label, target_is_directory=True)
            receipt = dict(source_stage=label, program_sha256=digest,
                           reason='exact_harness_match_within_round', executed=False)
            (root / 'successor_reuse.json').write_text(json.dumps(receipt, indent=2))
            return outcome
    return execute()

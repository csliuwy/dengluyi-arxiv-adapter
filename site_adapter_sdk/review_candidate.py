"""Import data-only candidate from an exact Git commit for a draft PR.

Run from trusted main code. Never checkout or execute the candidate's SDK/tests.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from .arxiv_contract import specification_checks
from .package import MEMBERS, MAX_TOTAL, load_bundle


def validate_revision(current, candidate):
    before, after = current['manifest'], candidate['manifest']
    if any(before[key] != after[key] for key in before if key != 'version'):
        raise ValueError('identity_permissions_or_origins_changed')
    if tuple(map(int, after['version'].split('.'))) <= tuple(map(int, before['version'].split('.'))):
        raise ValueError('new_version_required')
    checks = specification_checks(candidate['workflow'])
    if not all(check['passed'] for check in checks):
        raise ValueError('public_specification_conflict')
    existing = {s['id']: s for s in candidate['workflow']['steps']}
    for step in current['workflow']['steps']:
        if step['action'] in {'manual', 'submit', 'receipt'} and existing.get(step['id']) != step:
            raise ValueError('protected_checkpoint_changed')
    return {'status': 'candidate_ready_for_frozen_tests', 'before': current['sha256'],
            'after': candidate['sha256'], 'automaticActivationAllowed': False,
            'realWebsiteTested': False}


def pack(files, output):
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items(): archive.writestr(name, data)


def prepare(root, commit):
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('exact_candidate_commit_required')
    root = Path(root)
    files = {}; total = 0
    for name in sorted(MEMBERS):
        # Only literal whitelist paths; no candidate code or workflow can be imported.
        mode = subprocess.run(['git', 'ls-tree', commit, '--', 'adapter/' + name], cwd=root,
                              check=True, capture_output=True).stdout.decode('ascii', errors='strict')
        if not mode.startswith('100644 blob '):
            raise ValueError('candidate_member_not_regular_file')
        size = subprocess.run(['git', 'cat-file', '-s', commit + ':adapter/' + name], cwd=root,
                              check=True, capture_output=True).stdout
        total += int(size)
        if total > MAX_TOTAL: raise ValueError('candidate_size_limit')
        files[name] = subprocess.run(['git', 'show', commit + ':adapter/' + name], cwd=root,
                                    check=True, capture_output=True).stdout
    with tempfile.TemporaryDirectory(dir=root) as temporary:
        current_path = Path(temporary) / 'current.zip'; candidate_path = Path(temporary) / 'candidate.zip'
        pack({n: (root/'adapter'/n).read_bytes() for n in MEMBERS}, current_path)
        pack(files, candidate_path)
        report = validate_revision(load_bundle(current_path), load_bundle(candidate_path))
    # Only after all checks pass, write the data candidate for trusted-main tests.
    for name, data in files.items():
        (root/'adapter'/name).write_bytes(data)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-commit', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(Path.cwd(), args.candidate_commit), indent=2))


if __name__ == '__main__':
    main()

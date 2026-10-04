import copy
import json
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from site_adapter_sdk.review_candidate import validate_revision, prepare

ROOT = Path(__file__).resolve().parents[1]


class CandidateReview(unittest.TestCase):
    def setUp(self):
        self.current = {'manifest': json.loads((ROOT/'adapter/manifest.json').read_text(encoding='utf8')),
                        'workflow': json.loads((ROOT/'adapter/workflows/main.json').read_text(encoding='utf8')),
                        'sha256': '0'*64}
        self.candidate = copy.deepcopy(self.current)
        version = self.current['manifest']['version'].split('.')
        version[-1] = str(int(version[-1])+1)
        self.candidate['manifest']['version'] = '.'.join(version)
        self.candidate['sha256'] = '1'*64

    def test_versioned_data_candidate_remains_unapproved(self):
        result = validate_revision(self.current, self.candidate)
        self.assertFalse(result['automaticActivationAllowed'])
        self.assertFalse(result['realWebsiteTested'])

    def test_permissions_and_site_cannot_expand(self):
        self.candidate['manifest']['origins'].append('https://foreign.invalid')
        with self.assertRaisesRegex(ValueError, 'origins_changed'):
            validate_revision(self.current, self.candidate)

    def test_same_version_cannot_replace(self):
        self.candidate['manifest']['version'] = self.current['manifest']['version']
        with self.assertRaisesRegex(ValueError, 'new_version_required'):
            validate_revision(self.current, self.candidate)

    def test_manual_gate_cannot_change(self):
        step = next(s for s in self.candidate['workflow']['steps'] if s['action']=='manual')
        step['instruction'] = 'Skip approval'
        with self.assertRaisesRegex(ValueError, 'protected_checkpoint_changed'):
            validate_revision(self.current, self.candidate)

    def test_invalid_git_reference_rejected_before_git(self):
        for reference in ('main', '--help', 'x;rm', '../private', 'a'*39):
            with self.subTest(reference=reference), self.assertRaisesRegex(ValueError,'exact_candidate_commit'):
                prepare(ROOT, reference)

    def test_git_candidate_imports_data_but_never_candidate_code(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            root = Path(temporary)
            def git(*args):
                return subprocess.run(['git', *args], cwd=root, check=True,
                                      capture_output=True).stdout.decode().strip()
            for source in (ROOT/'adapter').rglob('*'):
                if source.is_file():
                    target = root/source.relative_to(ROOT)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(source.read_bytes())
            git('init'); git('config','user.email','synthetic@example.invalid'); git('config','user.name','Synthetic Test')
            git('config','core.autocrlf','false')
            git('add','adapter'); git('commit','-m','synthetic baseline')
            original = git('rev-parse','HEAD')
            manifest = root/'adapter/manifest.json'
            manifest.write_text(json.dumps(self.candidate['manifest']),encoding='utf8')
            sums = {p.relative_to(root/'adapter').as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (root/'adapter').rglob('*') if p.is_file() and p.name!='checksums.json'}
            (root/'adapter/checksums.json').write_text(json.dumps(sums),encoding='utf8')
            (root/'never_execute.py').write_text("raise RuntimeError('must not execute')")
            git('add','.'); git('commit','-m','synthetic candidate')
            candidate = git('rev-parse','HEAD')
            git('checkout',original)
            report = prepare(root,candidate)
            self.assertFalse(report['automaticActivationAllowed'])
            self.assertFalse((root/'never_execute.py').exists())
            self.assertEqual(json.loads(manifest.read_text())['version'], self.candidate['manifest']['version'])


if __name__ == '__main__':
    unittest.main()

"""Offline distribution boundary tests; never compile or upload a manuscript."""
import hashlib
import io
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
import zipfile

from site_adapter_sdk.package import check_tex_zip, load_bundle, read_zip

ROOT = Path(__file__).resolve().parents[1]


def archive(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for name, data in entries:
            if isinstance(name, str):
                # Windows ZipInfo normalizes backslashes during construction.
                # Preserve the raw member spelling to exercise hostile ZIP input.
                entry = zipfile.ZipInfo("placeholder")
                entry.filename = name
                entry.orig_filename = name
                entry.compress_type = zipfile.ZIP_DEFLATED
                name = entry
            output.writestr(name, data)
    return stream.getvalue()


class DistributionBoundary(unittest.TestCase):
    def test_exported_candidate_passes_without_execution_claim(self):
        entries = [(p.relative_to(ROOT / "adapter").as_posix(), p.read_bytes())
                   for p in (ROOT / "adapter").rglob("*") if p.is_file()]
        # Keep scratch files in the independent checkout (D: on the development host).
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            bundle = Path(temporary) / "candidate.zip"
            bundle.write_bytes(archive(entries))
            result = load_bundle(bundle)
            self.assertEqual(result["manifest"]["verificationLevel"], "offline-candidate")
            self.assertEqual(result["sha256"], hashlib.sha256(bundle.read_bytes()).hexdigest())
            changed = [(name, b"tampered" if name == "README.md" else data)
                       for name, data in entries]
            bundle.write_bytes(archive(changed))
            with self.assertRaisesRegex(ValueError, "bundle_hash_mismatch"):
                load_bundle(bundle)

    def test_traversal_and_windows_special_paths_rejected(self):
        for name in ("../outside.tex", "/absolute.tex", "C:/secret.tex", "a\\b.tex",
                     "NUL.tex", "folder/CON.txt", "trailing./main.tex"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "archive_member_rejected"):
                read_zip(archive([(name, b"synthetic")]))

    def test_duplicate_and_case_colliding_members_rejected(self):
        for second in ("main.tex", "MAIN.tex"):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                data = archive([("main.tex", b"one"), (second, b"two")])
            with self.assertRaisesRegex(ValueError, "archive_member_rejected"):
                read_zip(data)

    def test_symlink_rejected(self):
        entry = zipfile.ZipInfo("main.tex")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaisesRegex(ValueError, "archive_member_rejected"):
            read_zip(archive([(entry, b"../../private")]))

    def test_expansion_bound(self):
        data = archive([("main.tex", b"x" * 100000)])
        self.assertLess(len(data), 1024)
        with self.assertRaisesRegex(ValueError, "archive_expansion_limit"):
            read_zip(data, max_total=1024)

    def test_tex_static_success_never_claims_compilation(self):
        data = archive([("main.tex", br"\documentclass{article}\begin{document}Synthetic\end{document}")])
        result = check_tex_zip(data)
        self.assertTrue(result["passed"])
        self.assertFalse(result["compiled"])
        self.assertFalse(result["websiteAccepted"])

    def test_tex_missing_dependencies_and_commands_fail(self):
        cases = [(br"\documentclass{article}\input{missing}", "missing_reference:"),
                 (br"\documentclass{article}\write18{echo synthetic}", "unsafe_tex_command:"),
                 (br"\documentclass{article}\input{../private}", "unsafe_tex_reference:")]
        for source, expected in cases:
            result = check_tex_zip(archive([("main.tex", source)]))
            self.assertFalse(result["passed"])
            self.assertTrue(any(issue.startswith(expected) for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()

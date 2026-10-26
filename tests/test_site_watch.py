import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from site_adapter_sdk import site_watch as watch


def page(url, *, chrome='Navigation A', body='Read and review the submission carefully. ' * 8,
         target='../review.html'):
    return ('<!doctype html><html><nav>' + chrome + '</nav><main>'
            '<article class="md-content__inner md-typeset"><h1>' + watch.TITLES[url] + '</h1>'
            '<p>' + body + '</p><a href="' + target + '">Review</a></article>'
            '</main><footer>' + chrome + '</footer></html>')


class SiteWatch(unittest.TestCase):
    def observe(self, **changes):
        return watch.observe(lambda u: page(u, **changes), normalization=watch.ARTICLE_NORMALIZATION)

    def baseline(self):
        return {'schemaVersion': watch.SCHEMA, 'normalization': watch.ARTICLE_NORMALIZATION,
                'pages': self.observe()}

    def cli(self, path, fetch, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = watch.main(['--baseline', str(path), *args], fetch=fetch)
        return code, json.loads(output.getvalue())

    def test_chrome_change_does_not_change_article(self):
        self.assertEqual(self.observe(), self.observe(chrome='Entirely new navigation and footer'))

    def test_body_change_still_requires_review(self):
        result = watch.compare_public(self.observe(), self.observe(body='Different specification. ' * 20))
        self.assertEqual(result['status'], 'revision_candidate_required')
        self.assertEqual(result['changedUrls'], list(watch.URLS))
        self.assertFalse(result['automaticActivationAllowed'])

    def test_link_target_change_without_text_change_requires_review(self):
        self.assertNotEqual(self.observe(), self.observe(target='https://other.example.invalid/review'))

    def test_structure_and_other_attributes_remain_in_fingerprint(self):
        for before, after in (('<p>', '<p class="new">'), ('<p>', '<div>')):
            def fetch(url):
                html = page(url).replace(before, after)
                return html.replace('</p>', '</div>') if after == '<div>' else html
            observed = watch.observe(fetch, normalization=watch.ARTICLE_NORMALIZATION)
            self.assertNotEqual(self.observe(), observed)

    def test_article_absent_does_not_fall_back_to_navigation_markers(self):
        with self.assertRaises(ValueError):
            watch.observe(lambda _: '<nav>Submission TeX ' + 'x' * 400 + '</nav>',
                          normalization=watch.ARTICLE_NORMALIZATION)

    def test_duplicate_nested_unclosed_and_wrong_article_fail(self):
        for change in (lambda s: s + s, lambda s: s.replace('<p>', '<article><p>'),
                       lambda s: s.replace('</article>', ''),
                       lambda s: s.replace('md-content__inner md-typeset', 'unexpected')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                watch.observe(lambda u: change(page(u)), normalization=watch.ARTICLE_NORMALIZATION)

    def test_error_page_with_expected_title_is_too_short(self):
        with self.assertRaises(ValueError):
            self.observe(body='Unavailable')

    def test_exact_single_page_title_required(self):
        for change in (lambda s: s.replace('Submission Guidelines', 'Login'),
                       lambda s: s.replace('</h1>', '</h1><h1>Other</h1>')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                watch.observe(lambda u: change(page(u)), normalization=watch.ARTICLE_NORMALIZATION)

    def test_active_article_content_rejected(self):
        for tag in watch.ACTIVE_TAGS:
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                watch.observe(lambda u: page(u).replace('</article>', '<' + tag + '></' + tag + '></article>'),
                              normalization=watch.ARTICLE_NORMALIZATION)

    def test_oversize_invalid_data_and_duplicate_attribute_rejected(self):
        for payload in (None, 'x' * (watch.MAX_BYTES + 1),
                        page(watch.URLS[0]).replace('<a href=', '<a href="first" href=')):
            with self.subTest(kind=type(payload).__name__), self.assertRaises(ValueError):
                watch.observe(lambda _: payload, normalization=watch.ARTICLE_NORMALIZATION)

    def test_legacy_baselines_keep_legacy_whole_page_semantics(self):
        old = watch.observe(lambda u: page(u))
        hashes, normalization = watch.load_baseline(old)
        self.assertEqual(hashes, old)
        self.assertEqual(normalization, watch.LEGACY_NORMALIZATION)
        self.assertNotEqual(old, watch.observe(lambda u: page(u, chrome='New navigation')))

    def test_unknown_or_malformed_baseline_fails_before_fetch(self):
        cases = [[], {}, {'foreign': '0' * 64}, dict.fromkeys(watch.URLS, 'bad')]
        for field, value in (('schemaVersion', 'future'), ('normalization', 'ignore-all'),
                             ('pages', {}), ('extra', True)):
            candidate = self.baseline()
            candidate[field] = value
            cases.append(candidate)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'baseline.json'
            for value in cases:
                path.write_text(json.dumps(value), encoding='utf8')
                with self.subTest(value=value):
                    fetch = Mock(side_effect=AssertionError('must not fetch'))
                    code, result = self.cli(path, fetch)
                    fetch.assert_not_called()
                    self.assertEqual(code, 2)
                    self.assertFalse(result['baselineUpdated'])

    def test_cli_unchanged_and_drift_codes_never_rewrite_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'baseline.json'
            path.write_text(json.dumps(self.baseline()), encoding='utf8')
            before = path.read_bytes()
            for body, expected in ((None, 0), ('Changed instructions. ' * 20, 3)):
                fetch = lambda u: page(u, **({'body': body} if body else {}))
                code, result = self.cli(path, fetch)
                self.assertEqual(code, expected)
                self.assertFalse(result['automaticActivationAllowed'])
                self.assertFalse(result['baselineUpdated'])
                self.assertEqual(path.read_bytes(), before)

    def test_observation_failure_code_does_not_echo_body_or_error(self):
        def failed(_):
            raise RuntimeError('untrusted exception body must not escape')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'baseline.json'
            path.write_text(json.dumps(self.baseline()), encoding='utf8')
            before = path.read_bytes()
            code, result = self.cli(path, failed)
            self.assertEqual(code, 2)
            self.assertEqual(result['reason'], 'RuntimeError')
            self.assertNotIn('untrusted', json.dumps(result))
            self.assertEqual(path.read_bytes(), before)

    def test_record_new_only_and_never_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'new.json'
            code, result = self.cli(path, page, '--record-baseline')
            self.assertEqual(code, 0)
            self.assertEqual(watch.load_baseline(json.loads(path.read_text()))[1], watch.ARTICLE_NORMALIZATION)
            before = path.read_bytes()
            fetch = Mock(side_effect=AssertionError('must not fetch'))
            code, result = self.cli(path, fetch, '--record-baseline')
            fetch.assert_not_called()
            self.assertEqual(code, 2)
            self.assertEqual(path.read_bytes(), before)

    def test_redirect_and_http_size_bound_remain_enforced(self):
        with self.assertRaisesRegex(ValueError, 'redirect_requires_review'):
            watch.NoRedirect().redirect_request(None)
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size):
                self.size = size
                return b'x' * size
        response = Response()
        with patch.object(watch.urllib.request, 'build_opener') as build:
            build.return_value.open.return_value = response
            with self.assertRaisesRegex(ValueError, 'observation_size_limit'):
                watch.public_get(watch.URLS[0])
            self.assertEqual(response.size, watch.MAX_BYTES + 1)

    def test_normalization_unknown_and_scope_changes_rejected(self):
        fetch = Mock(side_effect=AssertionError('must not fetch'))
        with self.assertRaises(ValueError):
            watch.observe(fetch, normalization='future')
        fetch.assert_not_called()
        for value in ({}, {**self.observe(), 'https://other.invalid': '0' * 64}):
            with self.assertRaises(ValueError):
                watch.compare_public(self.observe(), value)


if __name__ == '__main__':
    unittest.main()

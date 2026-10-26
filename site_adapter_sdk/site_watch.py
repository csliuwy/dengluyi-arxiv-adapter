"""Read two public arXiv help articles. Never log in, activate or submit."""
from __future__ import annotations
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.request

URLS = ('https://info.arxiv.org/help/submit/index.html',
        'https://info.arxiv.org/help/submit_tex.html')
TITLES = dict(zip(URLS, ('Submission Guidelines', 'TeX Submissions')))
SCHEMA = 'arxiv-public-docs/2'
ARTICLE_NORMALIZATION = 'unique-article-structure-text-links/1'
LEGACY_NORMALIZATION = 'legacy-whole-page-text/1'
MAX_BYTES = 2_000_000
VOID_TAGS = frozenset(('area', 'base', 'br', 'col', 'embed', 'hr', 'img',
                       'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'))
ACTIVE_TAGS = frozenset(('script', 'style', 'iframe', 'object', 'embed', 'form',
                         'input', 'textarea', 'button'))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('redirect_requires_review')


class Article(HTMLParser):
    """Fingerprint the unique article, including structure and all attributes.

    Only outside-article chrome and comments are excluded. Missing, ambiguous,
    active or unbalanced content fails closed. This is not a browser or approval.
    """
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.count = 0
        self.stack = []
        self.tokens = []
        self.headings = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag == 'article':
            self.count += 1
            if self.count != 1 or self.stack:
                raise ValueError('observation_article_ambiguous')
            if len({name for name, _ in attrs}) != len(attrs):
                raise ValueError('observation_duplicate_attribute')
            classes = (dict(attrs).get('class') or '').split()
            if not {'md-content__inner', 'md-typeset'} <= set(classes):
                raise ValueError('observation_article_contract')
            self.stack.append(tag)
            self.tokens.append(['start', tag, sorted(attrs)])
            return
        if not self.stack:
            return
        if tag in ACTIVE_TAGS:
            raise ValueError('observation_active_article')
        if len({name for name, _ in attrs}) != len(attrs):
            raise ValueError('observation_duplicate_attribute')
        self.tokens.append(['start', tag, sorted(attrs)])
        if tag == 'h1':
            self.headings.append([])
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if not self.stack:
            if tag == 'article':
                raise ValueError('observation_article_unbalanced')
            return
        if self.stack[-1] != tag:
            raise ValueError('observation_article_unbalanced')
        self.stack.pop()
        self.tokens.append(['end', tag])

    def handle_data(self, data):
        if not self.stack:
            return
        value = re.sub(r'\s+', ' ', data).strip()
        if value:
            self.tokens.append(['text', value])
            self.text.append(value)
            if 'h1' in self.stack:
                self.headings[-1].append(value)

    def digest(self, title):
        self.close()
        if self.count != 1 or self.stack:
            raise ValueError('observation_article_missing_or_unclosed')
        if [' '.join(parts) for parts in self.headings] != [title]:
            raise ValueError('observation_article_title')
        if len(' '.join(self.text)) < 200:
            raise ValueError('observation_article_too_short')
        encoded = json.dumps(self.tokens, ensure_ascii=False, separators=(',', ':')).encode('utf8')
        return hashlib.sha256(encoded).hexdigest()


def public_get(url):
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(url, headers={'User-Agent': 'LoginEasy-adapter-spec-watch/0.2'})
    with opener.open(request, timeout=20) as response:
        if response.status != 200:
            raise ValueError('observation_http_failure')
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError('observation_size_limit')
    return body.decode('utf8')


def observe(fetch=None, *, normalization=LEGACY_NORMALIZATION):
    # Preserve the legacy import API and old-baseline comparison semantics.
    if normalization not in (LEGACY_NORMALIZATION, ARTICLE_NORMALIZATION):
        raise ValueError('normalization_requires_review')
    pages = {}
    for url in URLS:
        html = (fetch or public_get)(url)
        if not isinstance(html, str) or len(html.encode('utf8')) > MAX_BYTES:
            raise ValueError('observation_size_limit')
        if normalization == ARTICLE_NORMALIZATION:
            article = Article()
            article.feed(html)
            pages[url] = article.digest(TITLES[url])
        else:
            if len(html) < 200 or not any(marker in html for marker in ('Submission', 'TeX')):
                raise ValueError('observation_not_specification')
            text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html)).strip()
            pages[url] = hashlib.sha256(text.encode()).hexdigest()
    return pages


def validate_hashes(pages):
    if not isinstance(pages, dict) or set(pages) != set(URLS):
        raise ValueError('baseline_scope_mismatch')
    if any(not isinstance(v, str) or not re.fullmatch('[0-9a-f]{64}', v) for v in pages.values()):
        raise ValueError('baseline_hash_invalid')
    return pages


def load_baseline(value):
    if isinstance(value, dict) and set(value) == set(URLS):
        return validate_hashes(value), LEGACY_NORMALIZATION
    if (not isinstance(value, dict) or set(value) != {'schemaVersion', 'normalization', 'pages'}
            or value['schemaVersion'] != SCHEMA or value['normalization'] != ARTICLE_NORMALIZATION):
        raise ValueError('baseline_format_requires_review')
    return validate_hashes(value['pages']), ARTICLE_NORMALIZATION


def compare_public(baseline, observed):
    validate_hashes(baseline)
    validate_hashes(observed)
    changed = [u for u in URLS if baseline[u] != observed[u]]
    return {'status': 'revision_candidate_required' if changed else 'public_docs_unchanged',
            'changedUrls': changed, 'loginPagesObserved': False, 'allSiteChangesCovered': False,
            'automaticActivationAllowed': False, 'baselineUpdated': False,
            'baselineHashes': baseline, 'observedHashes': observed}


def main(argv=None, *, fetch=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--record-baseline', action='store_true',
                   help='Explicit review of a NEW article baseline file only')
    a = p.parse_args(argv)
    try:
        if a.record_baseline:
            if a.baseline.exists():
                raise FileExistsError('baseline_already_exists')
            current = observe(fetch, normalization=ARTICLE_NORMALIZATION)
            value = {'schemaVersion': SCHEMA, 'normalization': ARTICLE_NORMALIZATION, 'pages': current}
            with a.baseline.open('x', encoding='utf8') as f:
                json.dump(value, f, ensure_ascii=False, indent=2)
                f.write('\n')
            result = {'status': 'baseline_recorded', 'normalization': ARTICLE_NORMALIZATION,
                      'automaticActivationAllowed': False}
        else:
            baseline, normalization = load_baseline(json.loads(a.baseline.read_text(encoding='utf8')))
            current = observe(fetch, normalization=normalization)
            result = compare_public(baseline, current)
            result['normalization'] = normalization
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 3 if result['status'] == 'revision_candidate_required' else 0
    except Exception as exc:
        # Never echo response HTML or an untrusted exception message.
        print(json.dumps({'status': 'observation_failed', 'reason': type(exc).__name__,
                          'baselineUpdated': False, 'automaticActivationAllowed': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

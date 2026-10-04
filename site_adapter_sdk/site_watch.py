"""Read public arXiv specification pages. No login, mutation or auto-activation."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.request

URLS = ('https://info.arxiv.org/help/submit/index.html',
        'https://info.arxiv.org/help/submit_tex.html')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('redirect_requires_review')


def observe(fetch=None):
    def public_get(url):
        opener=urllib.request.build_opener(NoRedirect())
        request=urllib.request.Request(url,headers={'User-Agent':'LoginEasy-adapter-spec-watch/0.1'})
        with opener.open(request,timeout=20) as response:
            if response.status!=200: raise ValueError('observation_http_failure')
            body=response.read(2_000_001)
        if len(body)>2_000_000: raise ValueError('observation_size_limit')
        return body.decode('utf8')
    pages={}
    for url in URLS:
        html=(fetch or public_get)(url)
        if len(html)<200 or not any(marker in html for marker in ('Submission','TeX')):
            raise ValueError('observation_not_specification')
        text=re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',html)).strip()
        pages[url]=hashlib.sha256(text.encode()).hexdigest()
    return pages


def compare_public(baseline, observed):
    if set(baseline)!=set(URLS) or set(observed)!=set(URLS): raise ValueError('baseline_scope_mismatch')
    changed=[u for u in URLS if baseline[u]!=observed[u]]
    return {'status':'revision_candidate_required' if changed else 'public_docs_unchanged',
            'changedUrls':changed,'loginPagesObserved':False,'allSiteChangesCovered':False,
            'automaticActivationAllowed':False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--record-baseline',action='store_true',help='Explicit approval of a NEW baseline file only')
    a=p.parse_args(argv)
    try:
        current=observe()
        if a.record_baseline:
            with a.baseline.open('x',encoding='utf8') as f: json.dump(current,f,indent=2)
            result={'status':'baseline_recorded','automaticActivationAllowed':False}
        else: result=compare_public(json.loads(a.baseline.read_text(encoding='utf8')),current)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 3 if result['status']=='revision_candidate_required' else 0
    except Exception as exc:
        print(json.dumps({'status':'observation_failed','reason':type(exc).__name__,
                          'baselineUpdated':False})); return 2


if __name__=='__main__': raise SystemExit(main())

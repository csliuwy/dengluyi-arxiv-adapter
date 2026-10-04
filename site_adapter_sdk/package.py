"""Data-only extension packages: bounded ZIP validation, no extraction/eval."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

from .runtime import PROTOCOL, origin, validate_workflow

MAX_TOTAL = 8 * 1024 * 1024
MEMBERS = {'manifest.json', 'workflows/main.json', 'schemas/input.json',
           'skills/site-guide.md', 'tests/fixtures.json', 'reports/acceptance.json',
           'README.md', 'checksums.json'}


def safe_name(name):
    return (isinstance(name, str) and len(name) < 200 and not name.startswith('/')
            and '\\' not in name and ':' not in name
            and all(p and p not in {'.', '..'} and not p.endswith(('.', ' '))
                    and not re.match(r'(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', p)
                    for p in name.split('/')) and not any(ord(c) < 32 for c in name))


def read_zip(path, *, max_total=MAX_TOTAL, max_files=100):
    if isinstance(path,bytes):
        if len(path)>max_total: raise ValueError('archive_size_limit')
        path=io.BytesIO(path)
    elif Path(path).stat().st_size > max_total:
        raise ValueError('archive_size_limit')
    out = {}
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > max_files or sum(i.file_size for i in infos) > max_total:
            raise ValueError('archive_expansion_limit')
        seen = set()
        for info in infos:
            name=info.filename.rstrip('/') if info.is_dir() else info.filename
            original=info.orig_filename.rstrip('/') if info.is_dir() else info.orig_filename
            if (not safe_name(name) or not safe_name(original)
                    or info.filename.casefold() in seen
                    or stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1
                    or info.file_size > max_total):
                raise ValueError('archive_member_rejected')
            seen.add(info.filename.casefold())
            if info.is_dir(): continue
            data = archive.read(info)
            if len(data) != info.file_size:
                raise ValueError('archive_member_size_mismatch')
            out[info.filename] = data
    return out


def load_bundle(path):
    with Path(path).open('rb') as stream:
        data=stream.read(MAX_TOTAL+1)
    raw = read_zip(data)
    if set(raw) != MEMBERS:
        raise ValueError('bundle_members_invalid')
    sums = json.loads(raw['checksums.json'])
    if sums != {n: hashlib.sha256(b).hexdigest() for n, b in raw.items() if n != 'checksums.json'}:
        raise ValueError('bundle_hash_mismatch')
    manifest = json.loads(raw['manifest.json'])
    if (set(manifest) != {'schemaVersion', 'id', 'version', 'origins', 'hostProtocol', 'permissions', 'runtime', 'verificationLevel'}
            or manifest['schemaVersion'] != PROTOCOL or manifest['runtime'] != 'declarative-v1'
            or manifest['hostProtocol'] != 'dengluyi-browser/1'
            or manifest['permissions'] != ['snapshot', 'fill', 'select', 'upload', 'click', 'submit']
            or manifest['verificationLevel'] != 'offline-candidate'
            or not re.fullmatch(r'[a-z][a-z0-9-]{2,80}', manifest['id'])
            or not re.fullmatch(r'\d+\.\d+\.\d+', manifest['version'])):
        raise ValueError('manifest_invalid')
    workflow = json.loads(raw['workflows/main.json'])
    validate_workflow(workflow, manifest['origins'])
    return {'manifest': manifest, 'workflow': workflow,
            'sha256': hashlib.sha256(data).hexdigest(), 'files': raw}


def check_tex_zip(path):
    """Static source validation only; never compiles untrusted TeX on the host."""
    raw = read_zip(path, max_total=64 * 1024 * 1024, max_files=1000)
    allowed = {'.tex', '.bib', '.bbl', '.bst', '.sty', '.cls', '.pdf', '.png', '.jpg', '.jpeg', '.eps', '.ind', '.gls', '.nls'}
    issues = []
    mains = []
    for name, data in raw.items():
        suffix = PurePosixPath(name).suffix.lower()
        if suffix not in allowed or not re.fullmatch(r'[a-zA-Z0-9_+.,=/\-]+', name):
            issues.append('source_member_not_allowed:' + name)
        if suffix != '.tex': continue
        text = data.decode('utf8', errors='replace')
        if '\\documentclass' in text: mains.append(name)
        if re.search(r'\\(?:write18|immediate\s*\\write18|openout|read|input)\s*\|', text) or '\\write18' in text:
            issues.append('unsafe_tex_command:' + name)
        for kind, target in re.findall(r'\\(input|include|includegraphics|bibliography)\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}', text):
            for item in target.split(','):
                parent = PurePosixPath(name).parent
                candidate = (parent / item.strip()).as_posix()
                if not safe_name(candidate):
                    issues.append('unsafe_tex_reference:' + name); continue
                endings = {'input': ['', '.tex'], 'include': ['', '.tex'],
                           'includegraphics': ['', '.pdf', '.png', '.jpg', '.jpeg', '.eps'],
                           'bibliography': ['', '.bib']}[kind]
                if not any(candidate + ext in raw for ext in endings):
                    issues.append('missing_reference:' + candidate)
    if len(mains) != 1: issues.append('one_main_tex_required')
    return {'passed': not issues, 'issues': issues, 'mainTex': mains[0] if len(mains) == 1 else None,
            'compiled': False, 'websiteAccepted': False,
            'remaining': ['隔离完整编译', '人工检查注释及素材的公开权限', 'arXiv 网站编译与最终预览']}

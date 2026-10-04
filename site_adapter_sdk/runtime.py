"""Portable, stdlib-only adapter interpreter; also exported with adapter source.

Pages and model-generated workflows are untrusted data. This module has no
browser credentials, no shell, no network and no automatic submission loop.
"""
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urlsplit

PROTOCOL = 'dengluyi-site-adapter/1'
ACTIONS = {'fill', 'select', 'upload', 'click', 'submit', 'manual', 'receipt'}
FIELDS = {'title', 'abstract', 'authors', 'category', 'license', 'comments'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def origin(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('https_origin_required')
    if parsed.port not in (None, 443):
        raise ValueError('nonstandard_port_rejected')
    return 'https://' + parsed.hostname.lower()


def validate_workflow(workflow, origins):
    if not isinstance(workflow, dict) or set(workflow) != {'schemaVersion', 'steps'}:
        raise ValueError('workflow_shape_invalid')
    if workflow['schemaVersion'] != PROTOCOL:
        raise ValueError('workflow_version_unsupported')
    if not isinstance(origins, list) or not 1 <= len(origins) <= 8:
        raise ValueError('origins_required')
    if any(origin(o) != o for o in origins):
        raise ValueError('exact_origins_required')
    steps = workflow['steps']
    if not isinstance(steps, list) or not 3 <= len(steps) <= 40:
        raise ValueError('steps_limit')
    ids = set()
    keys = {'id', 'action', 'pathPrefix', 'pageTexts', 'labels', 'field', 'instruction'}
    for step in steps:
        if not isinstance(step, dict) or set(step) != keys:
            raise ValueError('step_shape_invalid')
        if not isinstance(step['id'], str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', step['id']) or step['id'] in ids:
            raise ValueError('step_id_invalid')
        ids.add(step['id'])
        if step['action'] not in ACTIONS:
            raise ValueError('action_not_allowed')
        if not isinstance(step['pathPrefix'], str) or not step['pathPrefix'].startswith('/') or len(step['pathPrefix']) > 200:
            raise ValueError('path_prefix_invalid')
        for key in ('labels', 'pageTexts'):
            if not isinstance(step[key], list) or len(step[key]) > 12 or any(
                not isinstance(v, str) or not v.strip() or len(v) > 180 for v in step[key]):
                raise ValueError('matching_rules_invalid')
        if not step['pageTexts']:
            raise ValueError('page_identity_required')
        if step['action'] not in {'manual', 'receipt'} and not step['labels']:
            raise ValueError('observed_label_required')
        if step['field'] not in FIELDS | {''}:
            raise ValueError('metadata_field_invalid')
        if step['action'] in {'fill', 'select'} and step['field'] not in FIELDS:
            raise ValueError('metadata_field_required')
        if step['action'] not in {'fill', 'select'} and step['field']:
            raise ValueError('unexpected_metadata_field')
        if not isinstance(step['instruction'], str) or not 1 <= len(step['instruction']) <= 1200:
            raise ValueError('instruction_invalid')
    # A workflow cannot silently omit the final confirmation or receipt boundary.
    if not {'submit', 'receipt'} <= {s['action'] for s in steps}:
        raise ValueError('submit_and_receipt_stages_required')


def snapshot_contract(snapshot):
    """Structure fingerprint, excluding values, cookies and page body text."""
    return {'origin': origin(snapshot['url']), 'path': urlsplit(snapshot['url']).path,
            'elements': sorted((str(e.get('tag', '')), str(e.get('type', '')),
                                str(e.get('label', ''))[:400])
                               for e in snapshot.get('elements', []))}


def plan_step(workflow, origins, snapshot, metadata, *, confirmed_manual_steps=()):
    validate_workflow(workflow, origins)
    if 'https://arxiv.org' in origins:
        from .arxiv_contract import specification_checks
        failures=[c['id'] for c in specification_checks(workflow) if not c['passed']]
        if failures:
            return {'status':'blocked','reason':'public_specification_conflict','issues':failures}
    if origin(snapshot.get('url', '')) not in origins:
        return {'status': 'blocked', 'reason': 'site_origin_not_allowed'}
    if snapshot.get('truncated') or not snapshot.get('snapshotId'):
        return {'status': 'blocked', 'reason': 'complete_fresh_snapshot_required'}
    if not isinstance(metadata, dict) or any(k not in FIELDS for k in metadata):
        return {'status': 'blocked', 'reason': 'metadata_shape_invalid'}
    if any(not isinstance(v, str) or len(v) > 16000 for v in metadata.values()):
        return {'status': 'blocked', 'reason': 'metadata_values_invalid'}
    text = str(snapshot.get('text', '')).casefold()
    path = urlsplit(snapshot['url']).path
    candidates = []
    for step in workflow['steps']:
        if not path.startswith(step['pathPrefix']) or not all(t.casefold() in text for t in step['pageTexts']):
            continue
        if step['action'] in {'manual', 'receipt'}:
            # Only the trusted host may supply these explicit current-page acknowledgements.
            if step['action']=='manual' and step['id'] in confirmed_manual_steps:
                continue
            candidates.append((step, None)); continue
        matches = [e for e in snapshot.get('elements', [])
                   if str(e.get('label', '')).strip().casefold() in {s.casefold() for s in step['labels']}
                   and not e.get('disabled') and not e.get('readOnly')]
        if len(matches) > 1:
            return {'status': 'needs_review', 'reason': 'ambiguous_element', 'stepId': step['id']}
        if not matches:
            if step['action'] in {'fill','select'}:
                # A changed form must not silently skip a required field and
                # reach its Continue/Submit button just because that is visible.
                return {'status':'needs_review','reason':'declared_field_control_missing','stepId':step['id']}
            continue
        element = matches[0]
        if step['action'] in {'fill', 'select'}:
            value = metadata.get(step['field'])
            if value is None or (not value and step['field'] != 'comments'):
                return {'status': 'awaiting_metadata', 'field': step['field']}
            if element.get('value') == value:
                continue
        if step['action']=='upload' and element.get('value'):
            # File selection belongs to the native host. A nonempty observed
            # input permits planning the next action, not proving its bytes.
            continue
        candidates.append((step, element))
    if not candidates:
        return {'status': 'needs_review', 'reason': 'page_contract_unmatched',
                'contractHash': digest(snapshot_contract(snapshot))}
    # Declaration order handles sequential fields on one form, not broad LLM clicking.
    step, element = candidates[0]
    if step['action'] == 'manual':
        return {'status': 'awaiting_user', 'stepId': step['id'], 'instruction': step['instruction']}
    if step['action'] == 'receipt':
        return {'status': 'receipt_observed_unverified', 'stepId': step['id'],
                'instruction': '请核对网站编号与账号。页面匹配不是投稿受理证明。'}
    action = step['action']
    if element.get('type') in {'hidden', 'password'}:
        return {'status': 'blocked', 'reason': 'protected_control'}
    if action == 'upload' and element.get('type') != 'file':
        return {'status': 'blocked', 'reason': 'file_input_required'}
    if action == 'fill' and not element.get('writable'):
        return {'status': 'blocked', 'reason': 'writable_control_required'}
    if action == 'select' and element.get('tag') != 'SELECT':
        return {'status': 'blocked', 'reason': 'select_control_required'}
    command = {'action': action, 'snapshot_id': snapshot['snapshotId'],
               'element_id': str(element['elementId']),
               'value': metadata.get(step['field'], '') if action in {'fill', 'select'} else ''}
    return {'status': 'awaiting_host_approval', 'stepId': step['id'], 'command': command,
            'instruction': step['instruction'], 'approvalRequired': True,
            'submissionAccepted': False}


def semantic_drift(baseline, current):
    """Compare observation contracts; never silently learn a new baseline."""
    old, new = snapshot_contract(baseline), snapshot_contract(current)
    return {'changed': old != new, 'baselineHash': digest(old), 'observedHash': digest(new),
            'status': 'revision_candidate_required' if old != new else 'observed_contract_unchanged',
            'allSiteChangesCovered': False, 'automaticActivationAllowed': False}

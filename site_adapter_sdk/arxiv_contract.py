"""Independent public-specification gates, not authenticated DOM selectors.

Checked 2026-10-04 against https://info.arxiv.org/help/submit/index.html.
Keep these constraints independent of a model's self-authored fixtures.
"""


def specification_checks(workflow):
    checks=[]
    for step in workflow['steps']:
        labels={v.strip().casefold() for v in step['labels']}
        page=' '.join(step['pageTexts']).casefold()
        # Submission 1.5 Confirm can delete uploaded files. Until that dialog
        # has an independently tested contract, keep it a manual-only action.
        if 'confirm' in labels and step['action'] not in {'manual','receipt'}:
            checks.append({'id':'arxiv_confirm_requires_manual_file_deletion_review','passed':False})
        # Official overview: after successful compilation/PDF preview, Continue
        # leads to metadata; Accept and Continue belongs to file processing.
        if ('preview' in page and 'pdf' in page and step['action']=='click'
                and labels != {'continue'}):
            checks.append({'id':'arxiv_preview_navigation_must_be_continue','passed':False})
    if not checks:
        checks.append({'id':'arxiv_public_specification_safety','passed':True})
    return checks

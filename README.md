# LoginEasy arXiv TeX adapter

Experimental data-only adapter generated via TRIZa, with independently reviewed workflow corrections and host SDK. Not an official arXiv product.
No live submission has been verified. Author login, approval and website policies remain required.
Requires dengluyi-browser/1; no native installer or credentials are included.
Use site_adapter_sdk.runtime.plan_step with the host snapshot; the host alone dispatches approved operations.
Guide text preserves generation-time notes; only current host reports describe validation, not model prose.
Run: python -m unittest discover -s tests -v

Licensed under MIT. Public repository: https://github.com/csliuwy/dengluyi-arxiv-adapter

## Candidate download and host integration

Download the controlled adapter ZIP from [v0.1.0 prerelease](https://github.com/csliuwy/dengluyi-arxiv-adapter/releases/tag/v0.1.0), not GitHub's whole-repository source ZIP.
SHA-256: `fec45d61f386887f96648c0045353ee99e5452ed31f7439036b5e7dd50cdb389`.

LoginEasy desktop build 638 adds **Agent workspace → Document tools → Site adapters**.
Import stores an account-scoped candidate only: no execution, browser opening, manuscript upload
or verified publisher signature. Existing trademark/patent workbenches are unchanged.
This host integration is a candidate build, not a released installer.

Run unit tests first. Browser operations require the TRIZa site-adapter CLI, a LoginEasy approved
`dengluyi-browser/1` connection, a fresh snapshot and explicit single-step approval.
Native confirmation remains required. Query uncertain operations rather than replaying them.
Unknown pages must stop. Real arXiv upload needs an authorized manuscript and author approval.

One-click handoff, signed installation and marketplace distribution remain
unimplemented. Documentation watching covers configured public help pages, not every authenticated
UI change. Changed or unavailable documentation never activates a repair automatically.

## Bounded candidate-to-draft-PR workflow

Maintainers can run **Review data candidate and open draft PR** from Actions on `main`, supplying
the exact 40-character commit SHA of a proposed revision already available in this public repository.
The workflow reads only the eight allowlisted `adapter/` files; it never checks out or executes
candidate code. It requires a higher version, unchanged identity/origins/permissions, unchanged
manual/submission/receipt checkpoints, public-specification checks and trusted-main tests.
On success it creates a new `codex/adapter-review-<SHA>` branch and a **draft** PR. It never merges,
signs, enables an adapter, submits a paper or publishes to a marketplace. Duplicate branches stop.
If branch push succeeded but PR creation failed, review that branch and open the PR manually;
do not force-push/replay the workflow to hide the failure.

The repository administrator must permit GitHub Actions to create pull requests; otherwise
publication fails visibly. Generation of the candidate itself is not automated by this workflow.
No paid model calls are made. Changing protected checkpoints requires separate maintainer review,
not weakening the validator. This workflow has local regression coverage; a real revision PR run
still needs an actual candidate. Do not use a meaningless version bump as a fake repair test.

## Public documentation drift checks
Create a reviewed public-doc baseline: python -m site_adapter_sdk.site_watch --baseline docs-baseline.json --record-baseline
Watch: python -m site_adapter_sdk.site_watch --baseline docs-baseline.json
Exit 3 means changed specification; 2 means failed observation. Neither permits auto-activation.

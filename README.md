# LoginEasy arXiv TeX adapter

Experimental data-only adapter generated via TRIZa, with independently reviewed workflow corrections and host SDK. Not an official arXiv product.
No live submission has been verified. Author login, approval and website policies remain required.
Requires dengluyi-browser/1; no native installer or credentials are included.
Use site_adapter_sdk.runtime.plan_step with the host snapshot; the host alone dispatches approved operations.
Guide text preserves generation-time notes; only current host reports describe validation, not model prose.
Run: python -m unittest discover -s tests -v

Licensed under MIT. Before public release: confirm repository owner; inspect source and test data.
Create a reviewed public-doc baseline: python -m site_adapter_sdk.site_watch --baseline docs-baseline.json --record-baseline
Watch: python -m site_adapter_sdk.site_watch --baseline docs-baseline.json
Exit 3 means changed specification; 2 means failed observation. Neither permits auto-activation.

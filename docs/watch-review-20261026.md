# Public specification watch review — 2026-10-26

## Incident and limits

[Scheduled run 40288659958](https://github.com/csliuwy/dengluyi-arxiv-adapter/actions/runs/40288659958)
used adapter-repository commit `6c5b14440e15434c49fb454d9eb1611dfb3be598`.
Its public job metadata confirms that unit tests passed and the documentation
watch failed with exit 3. Full historical job logs required authentication and
were not available to this review. A separate read-only observation reproduced
exit 3 for both configured pages. This is not a claim to have read those logs.

Exit 3 is a detected fingerprint difference, not an interpreter failure. The
Node 20 deprecation and runner-image notices were not the failing step.

The old fingerprint stripped tags from the entire page, including global
navigation/footer/script text. It also discarded link destinations. It could
therefore raise a specification alert for unrelated site-chrome changes while
missing a destination-only change in the article.

## Independent public-source comparison

arXiv's [official documentation repository](https://github.com/arXiv/arxiv-docs)
links from the live help pages. Its public `master` comparison from
`aa965e62021d6ba69949098c77b30a63d16bc5d9` (latest master at or before this
adapter repository's 2026-10-04 publication) to
`e078a44fdedde282b9d8e2119152047de6747d13` (observed 2026-10-26) spans 36
commits. It includes theme/navigation/configuration and other-page changes,
but neither watched article's Markdown source changed:

| Official source path | Blob at both references |
| --- | --- |
| `source/help/submit/index.md` | `53f17f780621532292e5cf653d3572ce15f5a709` |
| `source/help/submit_tex.md` | `71e16e17b2b92794d38d835b0c0900aa92768579` |

[Public source comparison](https://github.com/arXiv/arxiv-docs/compare/aa965e62021d6ba69949098c77b30a63d16bc5d9...e078a44fdedde282b9d8e2119152047de6747d13).
This supports site-chrome drift as the cause of the old whole-page alert. It
does not reproduce historical generated HTML or prove what was served to the
GitHub runner. No historical article snapshot had been retained.

The current live [Submission Overview](https://info.arxiv.org/help/submit/index.html)
and [TeX Submissions](https://info.arxiv.org/help/submit_tex.html) were reviewed.
The existing manual file-deletion confirmation, compiler/top-level-file review,
website-generated PDF preview, author declarations/licence and one-attempt
submission boundaries remain appropriate. No authenticated page/DOM contract
or real submission has been verified, and no adapter data or version changed.

## Reviewed migration, not automatic repair

The original two whole-page hashes remain in
`baselines/public-docs-legacy-20261004.json`; they still use legacy comparison
semantics and still report the old drift. The active baseline explicitly opts
into schema `arxiv-public-docs/2` and normalization
`unique-article-structure-text-links/1`.

The new fingerprint accepts exactly one complete arXiv article with the expected
page-specific heading. It hashes article tag structure, normalized text and all
attributes (including link/image targets and embedded edit controls). Missing,
duplicate, short, wrong-title, unbalanced or active-content articles fail closed.
It excludes outside-article navigation/footer and comments, not arbitrary changed
article paragraphs. It is still a conservative observation heuristic: an article
formatting change may require review; CSS-only/rendering changes outside it and
authenticated UI changes are not covered. A matching hash is not site acceptance.

The response size limit, timeout, exact two-URL scope and redirect refusal remain.
Unknown baseline formats cannot silently fall back. Normal watch runs never
write a baseline. Explicit recording only creates a new file and cannot overwrite
an existing file. Neither exit 0, 2 nor 3 authorizes activation or submission.

## Verification

- The original 22 local tests passed before the change.
- 17 distinct new offline watch tests cover navigation-only changes, real
  article/link/structure changes, missing/ambiguous/error articles, active tags,
  response size, redirection, strict baseline formats, legacy compatibility,
  fixed error projection, exit codes 0/2/3 and baseline non-rewrite.
- Live read-only article observations were used for the reviewed v2 hashes;
  normal observation does not revise those hashes automatically.
- GitHub-side verification is separate from these local results; the original
  failed run remains historical evidence and is not rewritten or rerun to hide it.

No credentials, author accounts, uploads, native installers, model calls,
private research, SDK capability activation or production deployment are part
of this repair.

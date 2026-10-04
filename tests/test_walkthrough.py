"""Synthetic snapshot walkthrough, not live browser or arXiv acceptance."""
import copy
import json
from pathlib import Path
import unittest

from site_adapter_sdk.runtime import plan_step

ROOT = Path(__file__).resolve().parents[1]


class Walkthrough(unittest.TestCase):
    def setUp(self):
        self.workflow = json.loads((ROOT / "adapter/workflows/main.json").read_text(encoding="utf8"))
        self.origins = ["https://arxiv.org"]

    def snapshot(self, text, elements):
        return {"snapshotId": "synthetic-only", "url": "https://arxiv.org/submit/synthetic",
                "text": text, "elements": elements}

    def element(self, label, **extra):
        return {"elementId": label, "label": label, "tag": "BUTTON", "type": "button", **extra}

    def plan(self, snapshot, metadata=None, confirmed=()):
        return plan_step(self.workflow, self.origins, snapshot, metadata or {},
                         confirmed_manual_steps=confirmed)

    def test_metadata_fields_read_back_before_continue(self):
        metadata = dict(title="Synthetic title", abstract="Synthetic abstract", authors="Test Author",
                        category="cs.CR", comments="")
        labels = dict(title="Title", abstract="Abstract", authors="Authors",
                      category="Primary Category", comments="Comments")
        controls = [self.element(label, tag="SELECT" if field == "category" else "INPUT",
                                 type="text", writable=True, value="old")
                    for field, label in labels.items()]
        page = self.snapshot("Submission Metadata Title Abstract", controls + [self.element("Continue")])
        for index, (field, value) in enumerate(metadata.items()):
            result = self.plan(page, metadata)
            self.assertEqual(result["status"], "awaiting_host_approval")
            self.assertEqual(result["command"]["value"], value)
            self.assertEqual(result["command"]["element_id"], labels[field])
            self.assertFalse(result["submissionAccepted"])
            controls[index]["value"] = value  # Synthetic host readback, not a browser action.
            page["snapshotId"] = f"synthetic-{index}"
        self.assertEqual(self.plan(page, metadata)["stepId"], "continue-metadata")
        changed = copy.deepcopy(page)
        changed["elements"] = [e for e in changed["elements"] if e["label"] != "Authors"]
        self.assertEqual(self.plan(changed, metadata)["reason"], "declared_field_control_missing")

    def test_preview_needs_manual_confirmation_then_host_approval(self):
        page = self.snapshot("Preview PDF", [self.element("Continue")])
        self.assertEqual(self.plan(page)["status"], "awaiting_user")
        result = self.plan(page, confirmed=("review-compiled-preview",))
        self.assertEqual(result["stepId"], "accept-compiled-preview")
        self.assertTrue(result["approvalRequired"])

    def test_final_confirmation_does_not_itself_submit(self):
        page = self.snapshot("Review Submission Submit Article", [self.element("Submit Article")])
        self.assertEqual(self.plan(page)["stepId"], "confirm-final-submission")
        result = self.plan(page, confirmed=("confirm-final-submission",))
        self.assertEqual(result["command"]["action"], "submit")
        self.assertEqual(result["status"], "awaiting_host_approval")
        self.assertFalse(result["submissionAccepted"])
        receipt = self.plan(self.snapshot("Submission complete Submission ID synthetic", []))
        self.assertEqual(receipt["status"], "receipt_observed_unverified")
        self.assertNotIn("command", receipt)

    def test_upload_selection_is_not_upload_success(self):
        file_input = self.element("Choose File", tag="INPUT", type="file", value="")
        page = self.snapshot("Upload Files", [file_input, self.element("Upload")])
        self.assertEqual(self.plan(page)["command"]["action"], "upload")
        file_input["value"] = "synthetic.tex.zip"
        result = self.plan(page)
        self.assertEqual(result["stepId"], "upload-source-zip")
        self.assertFalse(result["submissionAccepted"])

    def test_ambiguous_and_incomplete_pages_stop(self):
        page = self.snapshot("Preview PDF", [self.element("Continue"), self.element("Continue")])
        self.assertEqual(self.plan(page, confirmed=("review-compiled-preview",))["reason"], "ambiguous_element")
        page["truncated"] = True
        self.assertEqual(self.plan(page)["reason"], "complete_fresh_snapshot_required")


if __name__ == "__main__":
    unittest.main()

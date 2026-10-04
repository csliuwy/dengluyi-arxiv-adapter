import copy, json, pathlib, unittest
from site_adapter_sdk.runtime import validate_workflow, plan_step
from site_adapter_sdk.arxiv_contract import specification_checks
ROOT = pathlib.Path(__file__).resolve().parents[1]
class Contract(unittest.TestCase):
 def setUp(self):
  self.m=json.loads((ROOT/"adapter/manifest.json").read_text(encoding="utf8"))
  self.w=json.loads((ROOT/"adapter/workflows/main.json").read_text(encoding="utf8"))
 def test_scope(self):
  validate_workflow(self.w,self.m["origins"])
  self.assertEqual(plan_step(self.w,self.m["origins"],{"url":"https://foreign.invalid/"},{})["status"],"blocked")
 def test_public_spec(self):
  self.assertTrue(all(c["passed"] for c in specification_checks(self.w)))
 def test_dangerous_confirm_regression(self):
  bad=copy.deepcopy(self.w)
  target=next(s for s in bad["steps"] if s["action"]=="submit")
  target["labels"]=["Confirm"]
  self.assertFalse(all(c["passed"] for c in specification_checks(bad)))
 def test_unrecognized_page_stops(self):
  snap={"snapshotId":"synthetic","url":self.m["origins"][0]+"/unknown","text":"synthetic unrelated page","elements":[]}
  self.assertEqual(plan_step(self.w,self.m["origins"],snap,{})["status"],"needs_review")

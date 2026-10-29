import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from src.scheduler import schedule_orders
from src.generator import build_dataset

class InfeasibilityReportingTests(unittest.TestCase):
    def test_no_eligible_machine_is_reported_as_proven(self):
        order={"order_id":"ORD-1","priority":"NORMAL","due_date":"2026-01-06","order_date":"2026-01-05","quantity":1}
        op={"operation_id":"OP-ORD-1-01","order_id":"ORD-1","route_operation_id":"ROUTEOP-1","sequence_no":1,"process_family":1,"product_family":"F1","run_minutes_per_unit":10,"setup_minutes":5}
        result=schedule_orders([order],[op],[],[],[],[],[],[],[],[],[],[],[],horizon_days=2)
        failure=result["unscheduled_operations"][0]
        self.assertEqual(failure["reason_codes"],"NO_ELIGIBLE_MACHINE")
        self.assertEqual(failure["classification"],"PROVEN_INFEASIBLE")
        self.assertIn("details_json",failure)

    def test_generator_writes_structured_infeasibility_report(self):
        with TemporaryDirectory() as tmp:
            build_dataset(Path(tmp),seed=7,sku_count=1,machine_count=0,order_count=1,material_count=1)
            report=json.loads((Path(tmp)/"data/output/infeasibility_report.json").read_text())
            self.assertEqual(report["status"],"HAS_UNSCHEDULED_OPERATIONS")
            first=report["unscheduled_operations"][0]
            self.assertEqual(first["reason_codes"],"NO_ELIGIBLE_MACHINE")
            self.assertEqual(first["classification"],"PROVEN_INFEASIBLE")

if __name__=="__main__": unittest.main()

import csv
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from src.generator import build_dataset

class ReschedulingTests(unittest.TestCase):
    def test_material_delay_replans_and_preserves_prior_schedule(self):
        with TemporaryDirectory() as tmp:
            result=build_dataset(Path(tmp),seed=20261022,sku_count=8,machine_count=8,order_count=20,material_count=16,material_delay={"material_id":"MAT-0001","delay_until":"2026-02-01T06:00:00"})
            root=Path(tmp)/"data"
            self.assertTrue((root/"output/operation_schedules_before_replan.csv").exists())
            self.assertEqual(result["validation"]["checks"]["schedule_hard_constraints"],"PASS")
            with (root/"transactions/reschedule_events.csv").open(newline="",encoding="utf-8") as f:
                events=list(csv.DictReader(f))
            self.assertEqual(events[0]["event_type"],"MATERIAL_DELIVERY_DELAY")
            with (root/"transactions/inventory_transactions.csv").open(newline="",encoding="utf-8") as f:
                txns=list(csv.DictReader(f))
            self.assertTrue(any(t["event_type"]=="RELEASE" for t in txns))
            self.assertTrue(any(t["event_type"]=="RESERVE" for t in txns))

    def test_breakdown_is_recorded_and_schedule_is_replanned(self):
        with TemporaryDirectory() as baseline_dir, TemporaryDirectory() as replanned_dir:
            options=dict(seed=20261022,sku_count=8,machine_count=8,order_count=20,material_count=16)
            build_dataset(Path(baseline_dir),**options)
            with (Path(baseline_dir)/"data/output/operation_schedules.csv").open(newline="",encoding="utf-8") as f:
                first=next(csv.DictReader(f))
            start=datetime.fromisoformat(first["start_at"])+timedelta(minutes=5); end=start+timedelta(minutes=30)
            breakdown={"machine_id":first["machine_id"],"start_at":start.isoformat(timespec="seconds"),"end_at":end.isoformat(timespec="seconds"),"reason":"UNPLANNED_BREAKDOWN"}
            result=build_dataset(Path(replanned_dir),**options,breakdown=breakdown)
            root=Path(replanned_dir)/"data"
            self.assertTrue((root/"output/operation_schedules_before_replan.csv").exists())
            self.assertEqual(result["validation"]["checks"]["schedule_hard_constraints"],"PASS")
            with (root/"transactions/reschedule_events.csv").open(newline="",encoding="utf-8") as f:
                events=list(csv.DictReader(f))
            self.assertEqual(events[0]["event_type"],"UNPLANNED_DOWNTIME")
            self.assertEqual(events[0]["status"],"REPLANNED")
            with (root/"output/schedule_change_events.csv").open(newline="",encoding="utf-8") as f:
                changes=list(csv.DictReader(f))
            self.assertGreater(len(changes),0)

if __name__=="__main__": unittest.main()

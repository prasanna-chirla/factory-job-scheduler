import unittest
from src.inventory import preview_allocation, make_inventory_balances

class InventoryAllocationTests(unittest.TestCase):
    def setUp(self):
        self.lots=[
            {"lot_id":"L-EXP-SOON","material_id":"MAT-1","initial_quantity":60,"available_from":"2026-01-01T06:00:00","expiry_at":"2026-03-01T23:59:59"},
            {"lot_id":"L-EXP-LATE","material_id":"MAT-1","initial_quantity":40,"available_from":"2026-01-02T06:00:00","expiry_at":"2026-06-01T23:59:59"},
        ]
        self.remaining={"L-EXP-SOON":60,"L-EXP-LATE":40}
        self.requirements=[{"requirement_id":"REQ-1","material_id":"MAT-1","required_quantity":70}]

    def test_fefo_allocates_earliest_expiry_first(self):
        allocation=preview_allocation(self.requirements,self.lots,self.remaining,"2026-01-03T06:00:00")
        self.assertEqual([(x["lot_id"],x["quantity"]) for x in allocation],[ ("L-EXP-SOON",60.0),("L-EXP-LATE",10.0)])

    def test_allocation_cannot_exceed_available_balance(self):
        self.requirements[0]["required_quantity"]=101
        self.assertIsNone(preview_allocation(self.requirements,self.lots,self.remaining,"2026-01-03T06:00:00"))

if __name__=="__main__": unittest.main()

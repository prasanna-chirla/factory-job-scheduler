import unittest
from src.schedule_validator import validate_schedule
from tests.helpers import schedule_tables

class MachineOverlapTests(unittest.TestCase):
    def test_overlapping_assignments_are_reported(self):
        data=schedule_tables(second_start="2026-01-05T06:10:00")
        self.assertTrue(any("overlaps" in x for x in validate_schedule(data)))

if __name__=="__main__": unittest.main()

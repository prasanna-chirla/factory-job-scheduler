import unittest
from src.schedule_validator import validate_schedule
from tests.helpers import schedule_tables

class PrecedenceTests(unittest.TestCase):
    def test_successor_before_predecessor_end_is_reported(self):
        data=schedule_tables(second_machine="MACH-002",second_start="2026-01-05T06:10:00")
        self.assertTrue(any("precedence violation" in x for x in validate_schedule(data)))

if __name__=="__main__": unittest.main()

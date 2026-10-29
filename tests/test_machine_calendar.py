import unittest
from src.schedule_validator import validate_schedule
from tests.helpers import schedule_tables

class MachineCalendarTests(unittest.TestCase):
    def test_sunday_work_is_reported(self):
        data=schedule_tables(second_machine="MACH-002",second_start="2026-01-11T06:20:00")
        data["operation_schedules"][1]["end_at"]="2026-01-11T06:40:00"
        self.assertTrue(any("outside a working shift" in x for x in validate_schedule(data)))

if __name__=="__main__": unittest.main()

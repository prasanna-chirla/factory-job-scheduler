import unittest
from src.schedule_validator import validate_schedule
from tests.helpers import schedule_tables

class ChangeoverTests(unittest.TestCase):
    def test_omitted_changeover_is_reported(self):
        data=schedule_tables(second_machine="MACH-001",second_start="2026-01-05T06:20:00",second_family=2,second_change=0)
        data["operation_schedules"][1]["start_at"]="2026-01-05T06:20:00"
        data["operation_schedules"][1]["end_at"]="2026-01-05T06:40:00"
        self.assertTrue(any("changeover mismatch" in x for x in validate_schedule(data)))

if __name__=="__main__": unittest.main()

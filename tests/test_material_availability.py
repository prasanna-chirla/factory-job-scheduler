import unittest
from src.schedule_validator import validate_schedule
from tests.helpers import schedule_tables

class MaterialAvailabilityTests(unittest.TestCase):
    def test_schedule_before_material_availability_is_reported(self):
        data=schedule_tables(material_available="2026-01-06")
        self.assertTrue(any("unavailable" in x for x in validate_schedule(data)))

if __name__=="__main__": unittest.main()

import unittest
from src.data_validator import validate_data

class DataIntegrityTests(unittest.TestCase):
    def test_duplicate_primary_key_is_reported(self):
        tables={"products":[{"product_id":"P1"},{"product_id":"P1"}]}
        self.assertTrue(any("duplicate product_id" in x for x in validate_data(tables)))

if __name__=="__main__": unittest.main()

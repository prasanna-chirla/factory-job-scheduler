import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from src.generator import build_dataset
from src.reproducibility import same_inputs

class ReproducibilityTests(unittest.TestCase):
    def test_equal_seed_output_manifests_match(self):
        first={"counts":{"orders":1},"files":[{"path":"a.csv","sha256":"abc"}]}
        self.assertTrue(same_inputs(first,dict(first)))
        self.assertFalse(same_inputs(first,{"counts":{"orders":2},"files":first["files"]}))

    def test_generating_twice_with_same_seed_matches_inputs(self):
        with TemporaryDirectory() as first_dir, TemporaryDirectory() as second_dir:
            first=build_dataset(Path(first_dir),seed=20261022,sku_count=4,machine_count=8,order_count=12,material_count=16)
            second=build_dataset(Path(second_dir),seed=20261022,sku_count=4,machine_count=8,order_count=12,material_count=16)
            self.assertEqual(first["validation"]["status"],"PASS")
            self.assertTrue(same_inputs(first["manifest"],second["manifest"]))

if __name__=="__main__": unittest.main()

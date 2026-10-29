import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from src.generator import build_dataset

class GroundTruthEvaluationTests(unittest.TestCase):
    def test_all_five_counterfactuals_are_detected(self):
        with TemporaryDirectory() as tmp:
            result=build_dataset(Path(tmp),seed=20261022,sku_count=8,machine_count=8,order_count=20,material_count=16)
            self.assertEqual(result["ground_truth_evaluation"]["status"],"PASS")
            self.assertEqual(result["ground_truth_evaluation"]["passed_count"],5)

if __name__=="__main__": unittest.main()

import unittest
from scanner.multisector_score import score_candidate

class MultiSectorScoreTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {"ticker": "SYM", "sector": "robotics", "factors": {
            "catalyst": 90, "relative_volume": 90, "momentum": 90,
            "financial_quality": 90, "liquidity": 90, "risk_reward": 90}}

    def test_high_score_is_review_only(self):
        result = score_candidate(self.candidate)
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["opportunity_score"], 90)

    def test_missing_factors_cannot_pass(self):
        self.candidate["factors"].pop("liquidity")
        self.assertEqual(score_candidate(self.candidate)["status"], "WATCH_ONLY")

    def test_risk_flag_blocks(self):
        self.candidate["dilution_risk"] = True
        self.assertEqual(score_candidate(self.candidate)["status"], "WATCH_ONLY")

    def test_invalid_sector(self):
        self.candidate["sector"] = "unknown"
        with self.assertRaises(ValueError):
            score_candidate(self.candidate)

if __name__ == "__main__":
    unittest.main()

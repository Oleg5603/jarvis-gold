import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("lab", ROOT / "app.py")
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class LabTest(unittest.TestCase):
    def test_risk_plan_limits_risk(self):
        plan = lab.risk_plan({"capital": "100000", "risk_pct": "1", "entry": "100", "stop": "95"})
        self.assertEqual(plan["risk_money"], 1000)
        self.assertEqual(plan["quantity"], 200)
        self.assertEqual(plan["position_pct"], 20)

    def test_risk_plan_rejects_equal_entry_and_stop(self):
        with self.assertRaises(ValueError):
            lab.risk_plan({"capital": "100000", "risk_pct": "1", "entry": "100", "stop": "100"})

    def test_search_keeps_lesson_and_timestamp(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lesson.txt"
            path.write_text("[000120.4 - 000125.4] Оцениваем объем и прогресс цены.\n", encoding="utf-8")
            original = lab.TRANSCRIPTS
            lab.TRANSCRIPTS = Path(folder)
            try:
                results = lab.search_transcripts("объем прогресс")
            finally:
                lab.TRANSCRIPTS = original
        self.assertEqual(results[0]["time"], "000120.4")
        self.assertIn("lesson", results[0]["lesson"])

    def test_real_moex_training_fragments_are_complete(self):
        fragments = lab.market_fragments()
        self.assertGreaterEqual(len(fragments), 5)
        self.assertTrue(all(item["source"].startswith("MOEX ISS") for item in fragments))
        self.assertTrue(all(len(item["candles"]) == 156 for item in fragments))
        self.assertTrue(all({"open", "high", "low", "close", "volume"} <= set(item["candles"][0]) for item in fragments))


if __name__ == "__main__":
    unittest.main()

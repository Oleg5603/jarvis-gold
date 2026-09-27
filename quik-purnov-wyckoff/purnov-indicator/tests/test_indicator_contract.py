import re
import unittest
from pathlib import Path


SOURCE = (Path(__file__).parents[1] / "PurnovContext.lua").read_text(encoding="utf-8")


class IndicatorContractTests(unittest.TestCase):
    def test_has_quik_entry_points(self):
        for name in ("Init", "OnCalculate", "OnChangeSettings"):
            self.assertRegex(SOURCE, rf"function\s+{name}\s*\(")

    def test_four_price_scale_lines(self):
        line_block = SOURCE.split("line = {", 1)[1].split("}\n    }", 1)[0]
        self.assertEqual(line_block.count("Name="), 4)
        self.assertNotIn("HISTOGRAM", line_block)

    def test_signal_uses_closed_bar(self):
        on_calculate = SOURCE.split("function OnCalculate", 1)[1].split("function ExplainSignal", 1)[0]
        self.assertIn("evaluate(index-1)", on_calculate)
        self.assertNotRegex(on_calculate, r"evaluate\(index\s*\+\s*1\)")

    def test_levels_exclude_signal_bar(self):
        bounds = SOURCE.split("local function bounds", 1)[1].split("local function atr", 1)[0]
        self.assertIn("i-1", bounds)

    def test_effort_result_filter_is_present(self):
        self.assertIn("volume_ratio", SOURCE)
        self.assertIn("progress_ratio", SOURCE)
        self.assertIn("not buy_result", SOURCE)
        self.assertIn("not sell_result", SOURCE)

    def test_signal_requires_prior_activity(self):
        self.assertIn("local function prior_activity", SOURCE)
        self.assertIn("spring and sell_activity", SOURCE)
        self.assertIn("joc and buy_activity", SOURCE)

    def test_has_risk_disclaimer_in_readme(self):
        readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
        self.assertIn("не открывает сделки", readme)
        self.assertIn("200", readme)


if __name__ == "__main__":
    unittest.main()

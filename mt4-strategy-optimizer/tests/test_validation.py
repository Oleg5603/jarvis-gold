from ea_optimizer_lab.core import SetParameter
from ea_optimizer_lab.validation import stability_neighbours


def test_stability_neighbours_respect_bounds():
    params = [SetParameter("FAST", "7", "5", "1", "8", True), SetParameter("RISK", "1", optimize=False)]
    jobs = stability_neighbours(params, {"FAST": "7", "RISK": "1"})
    assert [name for name, _ in jobs] == ["FAST=-1", "FAST=+1"]
    assert [variant[0].value for _, variant in jobs] == ["6", "8"]


def test_stability_skips_non_numeric_or_disabled():
    params = [SetParameter("MODE", "true", "", "1", "", True), SetParameter("FAST", "7", "1", "1", "10", False)]
    assert stability_neighbours(params, {}) == []

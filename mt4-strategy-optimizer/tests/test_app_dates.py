import pytest
from ea_optimizer_lab.app import parse_top_n, parse_user_date

def test_parse_user_date_accepts_two_formats():
    assert parse_user_date("2026-05-25").isoformat()=="2026-05-25"
    assert parse_user_date("25.05.2026").isoformat()=="2026-05-25"

def test_parse_user_date_explains_typo():
    with pytest.raises(ValueError,match="ГГГГ-ММ-ДД"):
        parse_user_date("20256-05-25")

def test_parse_top_n_accepts_configurable_range():
    assert parse_top_n("1") == 1
    assert parse_top_n("50") == 50
    assert parse_top_n("200") == 200

@pytest.mark.parametrize("value", ["0", "201", "abc", ""])
def test_parse_top_n_rejects_invalid_values(value):
    with pytest.raises(ValueError, match="TOP"):
        parse_top_n(value)

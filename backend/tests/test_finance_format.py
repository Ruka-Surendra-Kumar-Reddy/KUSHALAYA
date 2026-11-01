from types import SimpleNamespace

from app.services.finance_output_service import _display_name, _format_money


def test_display_name_variants():
    assert _display_name("Anita", "Rao") == "Anita Rao"
    assert _display_name("Anita", None) == "Anita"
    assert _display_name(None, "Rao") == "Rao"
    assert _display_name(None, None) == "Unknown"
    assert _display_name("", "") == "Unknown"


def test_format_money_in_and_us():
    inr = _format_money(1234.5, SimpleNamespace(market="IN", country="India"))
    usd = _format_money(1234.5, SimpleNamespace(market="US", country="United States"))
    assert "1,234.50" in inr
    assert "1,234.50" in usd
    assert inr != usd or inr.startswith("₹") or usd.startswith("$")


def test_format_money_without_tenant():
    text = _format_money(10, None)
    assert "10.00" in text

import pytest

from app.core.identity_utils import aadhaar_last4, mask_aadhaar, normalize_aadhaar_digits


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, ""),
        ("", ""),
        ("   ", ""),
        ("1234", "1234"),
        ("1234 5678 9012", "123456789012"),
        ("1234-5678-9012", "123456789012"),
        ("Aadhaar: 1234-5678-9012", "123456789012"),
        ("xxxx-xxxx-1234", "1234"),
        ("12ab34", "1234"),
        ("0000 0000 0000", "000000000000"),
        ("  9 8 7  ", "987"),
    ],
)
def test_normalize_aadhaar_digits(value, expected):
    assert normalize_aadhaar_digits(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("", None),
        ("abc", None),
        ("12", "****"),
        ("123", "****"),
        ("1234", "XXXX-XXXX-1234"),
        ("1234 5678 9012", "XXXX-XXXX-9012"),
        ("xxxx9012", "XXXX-XXXX-9012"),
        ("00001234", "XXXX-XXXX-1234"),
        ("9-8-7-6-5-4-3-2-1-0", "XXXX-XXXX-3210"),
    ],
)
def test_mask_aadhaar(value, expected):
    assert mask_aadhaar(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("", None),
        ("12", None),
        ("123", None),
        ("1234", "1234"),
        ("123456789012", "9012"),
        ("xxxx-xxxx-7788", "7788"),
        ("A 1 B 2 C 3 D 4", "1234"),
    ],
)
def test_aadhaar_last4(value, expected):
    assert aadhaar_last4(value) == expected

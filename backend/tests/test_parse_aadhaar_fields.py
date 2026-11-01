from app.services.document_intelligence_service import _parse_aadhaar_fields


def test_parse_spaced_aadhaar_and_gender_male():
    text = "GOVERNMENT OF INDIA\nRAMESH KUMAR\n1234 5678 9012\nMale\nDOB: 01/02/1980"
    out = _parse_aadhaar_fields(text)
    assert out["aadhaar_number"] == "123456789012"
    assert out["gender"] == "Male"
    assert out["date_of_birth"] == "01/02/1980"
    assert out["full_name"] == "GOVERNMENT OF INDIA"


def test_parse_female_wins_over_male_token():
    out = _parse_aadhaar_fields("SITA DEVI\nFemale\n12/12/1965")
    assert out["gender"] == "Female"
    assert out["date_of_birth"] == "12/12/1965"


def test_parse_dash_dob():
    out = _parse_aadhaar_fields("Name\n15-08-1947")
    assert out["date_of_birth"] == "15-08-1947"


def test_parse_compact_aadhaar():
    out = _parse_aadhaar_fields("123456789012")
    assert out.get("aadhaar_number") == "123456789012"


def test_parse_ignores_short_digit_lines():
    out = _parse_aadhaar_fields("1234\n5678")
    assert "aadhaar_number" not in out


def test_parse_empty():
    assert _parse_aadhaar_fields("") == {}

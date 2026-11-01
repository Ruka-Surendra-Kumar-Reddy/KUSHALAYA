from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("testpass123")
    assert hashed != "testpass123"
    assert verify_password("testpass123", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_access_and_refresh_tokens_decode():
    access = create_access_token("1", role="CARE_MANAGER")
    refresh = create_refresh_token("1")
    access_payload = decode_token(access)
    refresh_payload = decode_token(refresh)
    assert access_payload is not None
    assert refresh_payload is not None
    assert access_payload["sub"] == "1"
    assert access_payload["role"] == "CARE_MANAGER"
    assert refresh_payload["sub"] == "1"
    assert access != refresh

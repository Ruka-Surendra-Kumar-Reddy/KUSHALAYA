"""Privacy helpers for caregiver identity (Aadhaar masking)."""


def normalize_aadhaar_digits(value: str | None) -> str:
    if not value:
        return ""
    return "".join(c for c in value if c.isdigit())


def mask_aadhaar(value: str | None) -> str | None:
    """Display-safe Aadhaar: XXXX-XXXX-1234."""
    digits = normalize_aadhaar_digits(value)
    if not digits:
        return None
    if len(digits) < 4:
        return "****"
    return f"XXXX-XXXX-{digits[-4:]}"


def aadhaar_last4(value: str | None) -> str | None:
    digits = normalize_aadhaar_digits(value)
    if len(digits) < 4:
        return None
    return digits[-4:]

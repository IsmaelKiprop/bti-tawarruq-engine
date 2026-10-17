import re


class IntegrationError(Exception):
    """Raised when an external provider returns an error or is misconfigured."""


def normalize_ke_phone(phone: str) -> str:
    """Normalize to Safaricom format 254XXXXXXXXX."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0") and len(digits) == 10:
        return f"254{digits[1:]}"
    if digits.startswith("254"):
        return digits
    if len(digits) == 9:
        return f"254{digits}"
    return digits

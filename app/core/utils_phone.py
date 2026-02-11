import re

def is_valid_phone(phone: str) -> bool:
    return bool(re.fullmatch(r"\+?[0-9]{10,15}", phone))

def normalize_phone(phone: str) -> str:
    phone = phone.strip()
    if phone.startswith("+"):
        return phone
    return "+91" + phone

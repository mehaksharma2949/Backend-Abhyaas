import random

def generate_otp() -> str:
    return str(random.randint(100000, 999999))

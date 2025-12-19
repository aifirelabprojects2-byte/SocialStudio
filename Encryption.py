# utils/encryption.py  or at the top of main.py
from cryptography.fernet import Fernet
import os

FERNET_KEY = os.getenv("FERNET_KEY") 
if not FERNET_KEY:
    raise ValueError("FERNET_KEY environment variable is required")
fernet = Fernet(FERNET_KEY.encode())

def encrypt_token(token: str | None) -> str | None:
    if not token:
        return None
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted: str | None) -> str | None:
    if not encrypted:
        return None
    return fernet.decrypt(encrypted.encode()).decode()
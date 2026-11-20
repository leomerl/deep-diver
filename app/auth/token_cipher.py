from base64 import urlsafe_b64encode
from hashlib import sha256

from cryptography.fernet import Fernet

from app.config import SECRET_KEY


def _fernet() -> Fernet:
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY is not set; it is needed to store GitHub tokens")
    # Fernet wants exactly 32 url-safe base64 bytes; hashing lets SECRET_KEY be any string.
    return Fernet(urlsafe_b64encode(sha256(SECRET_KEY.encode()).digest()))


def encrypt_token(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()

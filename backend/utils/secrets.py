import base64
import hashlib
import os
from typing import Optional
import importlib


def _derive_fernet_key(raw_key: str) -> bytes:
    """
    Fernet expects 32 urlsafe-base64 bytes.
    We accept any non-empty string and derive a stable key from SHA256.
    """
    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet(master_key: Optional[str] = None):
    mk = master_key or os.getenv("SECRETS_MASTER_KEY", "")
    if not mk:
        raise RuntimeError("SECRETS_MASTER_KEY is not set")
    # Lazy import to avoid tooling issues in environments without cryptography installed
    mod = importlib.import_module("cryptography.fernet")
    FernetCls = getattr(mod, "Fernet")
    return FernetCls(_derive_fernet_key(mk))


def encrypt_secret(plaintext: str, master_key: Optional[str] = None) -> str:
    if plaintext is None:
        raise ValueError("plaintext is None")
    f = get_fernet(master_key)
    token = f.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(ciphertext: str, master_key: Optional[str] = None) -> str:
    if ciphertext is None:
        raise ValueError("ciphertext is None")
    f = get_fernet(master_key)
    pt = f.decrypt(ciphertext.encode("utf-8"))
    return pt.decode("utf-8")



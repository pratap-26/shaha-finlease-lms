
from pwdlib import PasswordHash

# Argon2 is the recommended password-hashing algorithm.
password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Convert a plaintext password into a secure hash."""
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Check a password against its stored hash."""
    return password_hasher.verify(password, password_hash)

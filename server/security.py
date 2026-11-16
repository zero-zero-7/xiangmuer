"""密码哈希与账号校验工具（PBKDF2-SHA256 加盐）。"""
import hashlib
import hmac
import secrets

ITERATIONS = 120000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                salt.encode("utf-8"), ITERATIONS).hex()
    return f"pbkdf2${ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    if not stored or not stored.startswith("pbkdf2$"):
        return False
    try:
        _, iters, salt, digest = stored.split("$", 3)
        calc = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                   salt.encode("utf-8"), int(iters)).hex()
        return hmac.compare_digest(calc, digest)
    except Exception:
        return False

"""HMAC signing/verification (mirror of the CRM's, kept independent per service)."""
import hashlib
import hmac


def sign(body: bytes, secret: str) -> str:
    return f"sha256={hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()}"


def verify(body: bytes, signature: str | None, secret: str) -> bool:
    if not signature:
        return False
    return hmac.compare_digest(sign(body, secret), signature)

"""HMAC signing/verification for the CRM <-> channel-service loop.

Both directions (send requests out, receipts back in) carry an
``X-Signature: sha256=<hex>`` header over the raw JSON body. Using a shared
secret + constant-time compare models how real webhook security works and lets
the two services authenticate each other across hosts.
"""
import hashlib
import hmac


def sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify(body: bytes, signature: str | None, secret: str) -> bool:
    if not signature:
        return False
    expected = sign(body, secret)
    return hmac.compare_digest(expected, signature)

"""Password hashing for app logins.

Passwords used to be stored and compared as plain text. They are now stored as
salted PBKDF2-SHA256 hashes:

    pbkdf2_sha256$<iterations>$<salt>$<hash>

Standard library only, so it also runs on the locked-down VDI, where compiled
packages are blocked.

verify_password() still accepts a legacy plain-text value, and says so, so the
caller can replace it with a hash on the next successful login. That keeps
existing accounts working while the stored values migrate.

deploy/azure/ops/export_live_to_sql.py carries its own copy of the hashing
code, because it runs on the VDI without the rest of the repo. The two must
produce the same format.
"""
import base64
import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
# OWASP's recommendation for PBKDF2-HMAC-SHA256 (2023).
ITERATIONS = 600_000
_SALT_BYTES = 16

_dummy_hash = None


def _b64(raw):
    return base64.b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text):
    return base64.b64decode(text + "=" * (-len(text) % 4))


def hash_password(password, iterations=ITERATIONS):
    """A salted hash of password, in the stored format."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, iterations)
    return f"{ALGORITHM}${iterations}${_b64(salt)}${_b64(digest)}"


def is_hashed(stored):
    return isinstance(stored, str) and stored.startswith(ALGORITHM + "$")


def verify_password(stored, candidate):
    """Check candidate against a stored value.

    Returns (ok, needs_rehash). needs_rehash is True when the login succeeded
    but the stored value should be replaced -- it's legacy plain text, or was
    hashed with fewer iterations than the current setting.
    """
    if not stored or candidate is None:
        return False, False
    candidate = str(candidate).encode("utf-8")

    if not is_hashed(stored):
        # Legacy plain text. Constant-time compare, then ask for an upgrade.
        ok = hmac.compare_digest(str(stored).encode("utf-8"), candidate)
        return ok, ok

    try:
        _, iterations, salt, expected = stored.split("$")
        iterations = int(iterations)
        digest = hashlib.pbkdf2_hmac("sha256", candidate, _unb64(salt), iterations)
        ok = hmac.compare_digest(digest, _unb64(expected))
    except (ValueError, TypeError):  # malformed stored value
        return False, False
    return ok, ok and iterations < ITERATIONS


def spend_equal_time(candidate):
    """Do the work of a real check against a hash, discarding the result.

    Call this when the username doesn't exist, so a failed login takes about
    as long either way and response time can't reveal which usernames exist.
    """
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password(secrets.token_hex(16))
    verify_password(_dummy_hash, candidate)

"""Cryptographically secure credential generation and redaction helpers."""
from __future__ import annotations

import logging
import re
import secrets
import string
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PasswordPolicy:
    length: int = 24
    min_lower: int = 1
    min_upper: int = 1
    min_digit: int = 1
    min_special: int = 1
    special_chars: str = "!@#$%^&*()_+-=[]{};:,.<>?"

    def describe(self) -> str:
        return (
            f"length={self.length}, lower>={self.min_lower}, upper>={self.min_upper}, "
            f"digit>={self.min_digit}, special>={self.min_special}"
        )

    def validate(self) -> None:
        """Raise ValueError when the guaranteed classes exceed the length."""
        guaranteed = (
            self.min_lower + self.min_upper + self.min_digit + self.min_special
        )
        if self.length < guaranteed:
            raise ValueError(
                "Password policy length is smaller than the guaranteed character count"
            )


def policy_to_dict(policy: PasswordPolicy) -> dict:
    return {
        "length": policy.length,
        "min_lower": policy.min_lower,
        "min_upper": policy.min_upper,
        "min_digit": policy.min_digit,
        "min_special": policy.min_special,
    }


def policy_from_dict(data: dict) -> PasswordPolicy:
    policy = PasswordPolicy(
        length=int(data.get("length", PasswordPolicy.length)),
        min_lower=int(data.get("min_lower", PasswordPolicy.min_lower)),
        min_upper=int(data.get("min_upper", PasswordPolicy.min_upper)),
        min_digit=int(data.get("min_digit", PasswordPolicy.min_digit)),
        min_special=int(data.get("min_special", PasswordPolicy.min_special)),
    )
    policy.validate()
    return policy


def _charset_and_guarantees(policy: PasswordPolicy) -> tuple[str, list[str]]:
    buckets: list[str] = [
        string.ascii_lowercase,
        string.ascii_uppercase,
        string.digits,
        policy.special_chars,
    ]
    guarantees: list[str] = [
        *secrets.choice(buckets[0]),
        *[secrets.choice(bucket) for bucket in buckets[1:]],
    ]
    if policy.min_lower > 1:
        guarantees.extend(secrets.choice(buckets[0]) for _ in range(policy.min_lower - 1))
    if policy.min_upper > 1:
        guarantees.extend(secrets.choice(buckets[1]) for _ in range(policy.min_upper - 1))
    if policy.min_digit > 1:
        guarantees.extend(secrets.choice(buckets[2]) for _ in range(policy.min_digit - 1))
    if policy.min_special > 1:
        guarantees.extend(secrets.choice(buckets[3]) for _ in range(policy.min_special - 1))
    remainder = policy.length - len(guarantees)
    if remainder < 0:
        raise ValueError("Password policy length is smaller than the guaranteed character count")
    all_chars = "".join(buckets)
    guarantees.extend(secrets.choice(all_chars) for _ in range(remainder))
    # Fisher-Yates shuffle so guaranteed classes are not trivially positioned.
    pool = list(guarantees)
    for i in range(len(pool) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        pool[i], pool[j] = pool[j], pool[i]
    return all_chars, pool


def generate_password(policy: PasswordPolicy | None = None) -> str:
    """Generate a cryptographically secure random password.

    Uses `secrets` (system CSPRNG). Never derives material from CPE metadata,
    hostnames, serials, site codes or IPs.
    """
    policy = policy or PasswordPolicy()
    all_chars, pool = _charset_and_guarantees(policy)
    password = "".join(pool)

    if not _validate_password(password, policy):
        raise RuntimeError("Generated password failed policy validation")  # pragma: no cover

    logger.info("Generated credential material (value not logged)")
    return password


def _validate_password(password: str, policy: PasswordPolicy) -> bool:
    if len(password) < policy.length:
        return False
    if sum(1 for c in password if c in string.ascii_lowercase) < policy.min_lower:
        return False
    if sum(1 for c in password if c in string.ascii_uppercase) < policy.min_upper:
        return False
    if sum(1 for c in password if c in string.digits) < policy.min_digit:
        return False
    if sum(1 for c in password if c in policy.special_chars) < policy.min_special:
        return False
    return True


_SECRET_LIKE = re.compile(r"(?i)(password|secret|token|credential)([\"']?\s*[:=]\s*[\"'])[^\"'\s,}]+")


def redact_secrets(text: str) -> str:
    """Replace likely secret values with a redaction marker before logging."""
    if not text:
        return text
    return _SECRET_LIKE.sub(lambda m: f"{m.group(1)}{m.group(2)}***REDACTED***", text)


def redact_value(value: str) -> str:
    return "***REDACTED***" if value else value
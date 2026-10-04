"""Identifier generation and sequential counter utilities."""

import time
import os
import uuid


def generate_ulid() -> str:
    """Generate a sortable opaque ULID-like unique identifier for jobs.
    Uses millisecond timestamp prefix + random hex to ensure lexical sortability.
    """
    ms = int(time.time() * 1000)
    # 48-bit timestamp hex (12 chars) + 80-bit random hex (20 chars) -> 32 char sortable ID
    random_bytes = os.urandom(10).hex()
    return f"{ms:012x}{random_bytes}"


def generate_call_id() -> str:
    """Generate a unique call ID for API audit logging."""
    return uuid.uuid4().hex[:16]

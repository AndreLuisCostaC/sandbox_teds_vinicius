from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address


_limit_per_minute = os.getenv("RATE_LIMIT_PER_MINUTE", "60")
AUTH_RATE_LIMIT = f"{_limit_per_minute}/minute"

limiter = Limiter(key_func=get_remote_address)


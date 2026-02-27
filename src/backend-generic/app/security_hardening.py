from __future__ import annotations

import bleach


def sanitize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = bleach.clean(value, tags=[], attributes={}, strip=True)
    return cleaned.strip()

"""
Strict shop isolation enforcement.

THIS IS A CRITICAL SECURITY RULE.

- Explicit shop in message > verified mapping > context
- Never fall back to another shop
- Backend must enforce; never trust client-provided shop_id
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.models import Shop


@dataclass
class ShopResolution:
    code: str | None
    source: str  # "explicit" | "verified_mapping" | "context" | "none"
    candidates: list[str] | None = None  # populated when ambiguous


def normalize_shop_code(raw: str | None) -> str | None:
    """Normalize 'a3', 'A 3', ' a3 ', 'ah', 'A14' → 'A3', 'AH', 'A14'.

    Format validation only — DB existence check by get_shop_by_code().
    Accepts: [A-Z] followed by 0-15 more [A-Z0-9] chars (2-16 total).
    """
    if not raw:
        return None
    s = str(raw).strip().upper().replace(" ", "")
    if not s:
        return None

    import re
    # Accept: A1-A99+, AH, B1, AB12, ... (letter start, alphanumeric rest)
    if re.match(r"^[A-Z][A-Z0-9]{0,15}$", s):
        # If pure A + number, no zero-padding: A01 → A1
        m = re.match(r"^([A-Z])(\d+)$", s)
        if m:
            return f"{m.group(1)}{int(m.group(2))}"
        return s
    return None


def resolve_shop(
    *,
    explicit: str | None,
    verified_codes: Iterable[str] | None,
    context_code: str | None,
) -> ShopResolution:
    """
    Resolve the effective shop using the priority rule:

        1. Explicit shop in current message
        2. Verified Telegram User → Shop mapping
        3. Active conversation Shop context
        4. Ask user (returns source="none")
    """
    # 1. Explicit
    explicit_norm = normalize_shop_code(explicit)
    if explicit_norm:
        return ShopResolution(code=explicit_norm, source="explicit")

    # 2. Verified mapping
    if verified_codes:
        verified_list = list(verified_codes)
        if len(verified_list) == 1:
            return ShopResolution(code=verified_list[0], source="verified_mapping")
        elif len(verified_list) > 1:
            # Ambiguous — do not guess
            return ShopResolution(
                code=None, source="none", candidates=verified_list
            )

    # 3. Context
    ctx_norm = normalize_shop_code(context_code)
    if ctx_norm:
        return ShopResolution(code=ctx_norm, source="context")

    # 4. None
    return ShopResolution(code=None, source="none")


def shop_id_for_code(code: str) -> int | None:
    """Look up a shop's primary key from its code."""
    if not code:
        return None
    shop = Shop.query.filter_by(code=code).first()
    return shop.id if shop else None


def assert_shop_exists(code: str) -> Shop:
    """Raise ValueError if the shop code is invalid."""
    shop = Shop.query.filter_by(code=code).first()
    if not shop:
        raise ValueError(f"Unknown shop code: {code}")
    return shop

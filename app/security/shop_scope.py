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
import re

from app.models import Shop


@dataclass
class ShopResolution:
    code: str | None
    source: str  # "explicit" | "verified_mapping" | "context" | "none"
    candidates: list[str] | None = None  # populated when ambiguous


def normalize_shop_code(raw: str | None) -> str | None:
    """Normalize a shop code.

    Examples:
      "a3"   -> "A3"
      " A 3 " -> "A3"
      "3"    -> "A3"
      "ah"   -> "AH"
      "A14"  -> "A14"
    """
    if not raw:
        return None

    s = str(raw).strip().upper().replace(" ", "")
    if not s:
        return None

    # Numeric-only shop code: "3" means "A3".
    if s.isdigit():
        n = int(s)
        return f"A{n}" if 1 <= n <= 13 else None

    # This system currently has shops A1-A13 only.
    if re.match(r"^A\d+$", s):
        n = int(s[1:])
        return s if 1 <= n <= 13 else None

    # Accept other letter-starting alphanumeric shop codes.
    if re.match(r"^[A-Z][A-Z0-9]{0,15}$", s):
        # Normalize A01 -> A1.
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

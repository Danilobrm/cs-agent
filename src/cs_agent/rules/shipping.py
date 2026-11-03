"""Shipping fees, delivery options and special freight (Policy 5)."""

import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from cs_agent.money import to_money

METRO_CITIES = frozenset({"campo grande"})
FREE_SHIPPING_MIN = Decimal("500.00")
METRO_FEE = Decimal("35.00")
SPECIAL_FREIGHT_CATEGORY_IDS = frozenset({3, 4})  # 3 drums, 4 keyboards / digital pianos


@dataclass(frozen=True)
class ShippingOption:
    carrier: str
    min_days: int
    max_days: int
    insured: bool


@dataclass(frozen=True)
class ShippingQuote:
    metro: bool
    fee: Decimal | None  # None: depends on the destination CEP
    free: bool
    needs_cep_quote: bool
    options: tuple[ShippingOption, ...]  # delivery times are in business days
    special_freight: bool


_METRO_OPTION = ShippingOption("Motoboy próprio", 1, 3, False)
_CARRIER_OPTIONS = (
    ShippingOption("PAC (Correios)", 5, 12, True),
    ShippingOption("SEDEX (Correios)", 2, 5, True),
    ShippingOption("Jadlog (.package)", 3, 8, True),
)


def _normalize_city(city: str) -> str:
    """Lowercase, accent-free, single-spaced."""
    decomposed = unicodedata.normalize("NFKD", city)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(plain.casefold().split())


def shipping_quote(city: str, order_value: Decimal, category_ids: set[int]) -> ShippingQuote:
    """Shipping fee and options for a destination city.

    Policy 5.1 (metro region): free above R$ 500, otherwise a flat R$ 35, 1-3 business days by
    own courier. The policy says "acima"/"abaixo" and leaves exactly R$ 500 undefined; it is
    resolved in the customer's favor (free). Only Campo Grande counts as metro, since the data
    has no other metro cities.

    Policy 5.2 (other cities): PAC, SEDEX or Jadlog, insured; the fee depends on the CEP, so
    `fee` is None and `needs_cep_quote` is True. Large instruments (drums, keyboards / digital
    pianos) may need special freight with an individual quote.
    """
    special = bool(SPECIAL_FREIGHT_CATEGORY_IDS & set(category_ids))
    if _normalize_city(city) in METRO_CITIES:
        free = to_money(order_value) >= FREE_SHIPPING_MIN
        fee = Decimal("0.00") if free else METRO_FEE
        return ShippingQuote(True, fee, free, False, (_METRO_OPTION,), special)
    return ShippingQuote(False, None, False, True, _CARRIER_OPTIONS, special)

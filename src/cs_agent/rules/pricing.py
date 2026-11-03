"""Prices, promotions and the PIX discount (Policy 3, 6.2)."""

from dataclasses import dataclass
from decimal import Decimal

from cs_agent.money import to_money

PIX_DISCOUNT_PERCENT = 5


@dataclass(frozen=True)
class PriceQuote:
    list_price: Decimal
    promo_percent: int | None
    promo_price: Decimal | None
    pix_price: Decimal
    final_card_price: Decimal


def price_quote(list_price: Decimal, promo_percent: int | None) -> PriceQuote:
    """Price a product for card and PIX payment.

    Promotions are not cumulative (Policy 6.2): the 5% PIX discount (Policy 3) applies to the
    list price only when there is no active promotion. With a promotion, the PIX price equals
    the promotional price.
    """
    list_price = to_money(list_price)
    if promo_percent is None:
        pix_price = to_money(list_price * (100 - PIX_DISCOUNT_PERCENT) / 100)
        return PriceQuote(list_price, None, None, pix_price, list_price)
    if not 0 < promo_percent <= 100:
        raise ValueError(f"promo_percent must be in 1..100, got {promo_percent}")
    promo_price = to_money(list_price * (100 - promo_percent) / 100)
    return PriceQuote(list_price, promo_percent, promo_price, promo_price, promo_price)

"""Catalog checks: availability, text normalization and brand/description conflicts."""

import re
import unicodedata
from typing import Literal

Availability = Literal["available", "out_of_stock", "discontinued", "coming_soon"]

KNOWN_BRANDS = (
    "Yamaha",
    "Tagima",
    "Giannini",
    "Rozini",
    "Shelby",
    "Crafter",
    "Martin",
    "Taylor",
    "Takamine",
    "Kala",
    "Ohana",
    "Kalani",
    "Fender",
    "Gibson",
    "Ibanez",
    "PRS",
    "Music Man",
    "Pearl",
    "Tama",
    "Roland",
    "Korg",
    "Nord",
)


def normalize_text(s: str) -> str:
    """Lowercase and strip accents, for search and city comparison."""
    decomposed = unicodedata.normalize("NFKD", s)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _mentions(text: str, brand: str) -> bool:
    """Whole-word match on already normalized text."""
    return re.search(rf"(?<!\w){re.escape(normalize_text(brand))}(?!\w)", text) is not None


def description_conflicts(name: str, description: str) -> bool:
    """True when the description names a known brand that the product name does not.

    The source data has descriptions copied from other products (e.g. a "Music Man" bass
    described as a Fender). The name and specs are trusted over the description.
    """
    name_n, desc_n = normalize_text(name), normalize_text(description)
    return any(_mentions(desc_n, b) and not _mentions(name_n, b) for b in KNOWN_BRANDS)


def availability(status: str, stock: int) -> Availability:
    """Customer-facing availability from the product status and stock."""
    if status == "discontinued":
        return "discontinued"
    if status == "coming_soon":
        return "coming_soon"
    return "available" if stock > 0 else "out_of_stock"

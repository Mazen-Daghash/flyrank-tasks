"""Structure stage: assemble cleaned values into one record shape every
book follows, regardless of what was missing or malformed on its page.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

import clean


@dataclass
class Book:
    title: str
    product_url: str
    category: str | None
    upc: str | None
    product_type: str | None
    rating: int | None
    price_excl_tax: float | None
    price_incl_tax: float | None
    tax: float | None
    currency: str
    in_stock: bool
    stock_count: int | None
    number_of_reviews: int | None
    description: str
    image_url: str | None
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


def build_book(raw: dict) -> Book:
    """raw is the dict returned by parse.parse_book_detail -- untyped strings
    straight off the page. This turns it into a fully typed Book record."""
    in_stock, stock_count = clean.clean_availability(raw.get("availability_text"))

    return Book(
        title=clean.clean_text(raw.get("title")),
        product_url=raw["product_url"],
        category=clean.clean_text(raw.get("category")) or None,
        upc=raw.get("upc"),
        product_type=raw.get("product_type"),
        rating=clean.clean_rating(raw.get("rating_word")),
        price_excl_tax=clean.clean_price(raw.get("price_excl_tax_text")),
        price_incl_tax=clean.clean_price(raw.get("price_incl_tax_text")),
        tax=clean.clean_price(raw.get("tax_text")),
        currency="GBP",
        in_stock=in_stock,
        stock_count=stock_count,
        number_of_reviews=clean.clean_int(raw.get("number_of_reviews_text")),
        description=clean.clean_text(raw.get("description")),
        image_url=raw.get("image_url"),
    )

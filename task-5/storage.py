"""Save stage: write structured Book records to disk as JSON and CSV."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from models import Book

FIELDNAMES = [
    "title", "product_url", "category", "upc", "product_type", "rating",
    "price_excl_tax", "price_incl_tax", "tax", "currency", "in_stock",
    "stock_count", "number_of_reviews", "description", "image_url", "scraped_at",
]


def save_json(books: list[Book], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [book.to_dict() for book in books]
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


def save_csv(books: list[Book], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for book in books:
            writer.writerow(book.to_dict())

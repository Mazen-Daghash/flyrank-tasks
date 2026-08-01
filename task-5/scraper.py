"""Scraper for books.toscrape.com -- a sandbox site built for scraping
practice (its own pages carry the disclaimer "This is a demo website for
web scraping purposes").

Pipeline: fetch -> parse -> extract/clean -> structure -> save.
Each stage lives in its own module (fetch.py, parse.py, clean.py, models.py,
storage.py); this file just wires them together and drives the crawl.

Usage:
    python scraper.py --pages 5 --delay 1.0
    python scraper.py --pages 1 --max-books 5 --delay 0.5   # quick smoke test
"""
from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urljoin

from fetch import PoliteFetcher
from parse import parse_listing_page, parse_book_detail
from models import build_book
from storage import save_json, save_csv

BASE_URL = "https://books.toscrape.com/"
START_URL = urljoin(BASE_URL, "catalogue/page-1.html")


def crawl(fetcher: PoliteFetcher, max_pages: int, max_books: int | None) -> list:
    books = []
    detail_urls: list[str] = []
    page_url = START_URL
    pages_visited = 0

    while page_url and pages_visited < max_pages:
        print(f"[listing] page {pages_visited + 1}: {page_url}")
        resp = fetcher.get(page_url)
        if resp is None:
            break

        urls, next_url = parse_listing_page(resp.content, page_url)
        detail_urls.extend(urls)
        pages_visited += 1
        page_url = next_url

        if max_books is not None and len(detail_urls) >= max_books:
            detail_urls = detail_urls[:max_books]
            break

    print(f"[listing] {len(detail_urls)} book(s) found across {pages_visited} page(s)\n")

    for i, url in enumerate(detail_urls, start=1):
        print(f"[detail {i}/{len(detail_urls)}] {url}")
        resp = fetcher.get(url)
        if resp is None:
            continue
        raw = parse_book_detail(resp.content, url)
        books.append(build_book(raw))

    return books


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pages", type=int, default=5, help="max catalogue listing pages to crawl (default: 5, 20 books/page)")
    parser.add_argument("--max-books", type=int, default=None, help="cap on total books scraped, across all pages")
    parser.add_argument("--delay", type=float, default=1.0, help="minimum seconds between requests (default: 1.0)")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "output")
    args = parser.parse_args()

    fetcher = PoliteFetcher(BASE_URL, delay=args.delay)
    books = crawl(fetcher, max_pages=args.pages, max_books=args.max_books)

    json_path = args.output_dir / "books.json"
    csv_path = args.output_dir / "books.csv"
    save_json(books, json_path)
    save_csv(books, csv_path)

    print(f"\nSaved {len(books)} record(s) to:")
    print(f"  {json_path}")
    print(f"  {csv_path}")


if __name__ == "__main__":
    main()

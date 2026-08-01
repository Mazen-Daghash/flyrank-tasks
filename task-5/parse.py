"""Parse stage: turn raw HTML into the specific fields we care about.

Nothing here converts types or trims whitespace beyond what BeautifulSoup
does automatically -- that normalization belongs to the clean stage. This
stage's only job is locating the right tags and pulling their raw text/attrs.
"""
from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup


def parse_listing_page(html: bytes, page_url: str) -> tuple[list[str], str | None]:
    """Return (book detail URLs on this page, next page URL or None).

    Takes raw response bytes (not response.text) so BeautifulSoup's own
    encoding sniffer can read this site's <meta http-equiv=content-type>
    charset tag -- the HTTP header omits it, which makes `requests` guess
    Latin-1 and mangle non-ASCII text.
    """
    soup = BeautifulSoup(html, "html.parser")

    detail_urls = [
        urljoin(page_url, article.h3.a["href"])
        for article in soup.select("article.product_pod")
    ]

    next_link = soup.select_one("li.next a")
    next_url = urljoin(page_url, next_link["href"]) if next_link else None

    return detail_urls, next_url


def parse_book_detail(html: bytes, url: str) -> dict:
    """Extract raw fields from a single book's detail page."""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("div.product_main")

    breadcrumb = [li.get_text(strip=True) for li in soup.select("ul.breadcrumb li")]
    category = breadcrumb[2] if len(breadcrumb) >= 3 else None

    rating_p = main.select_one("p.star-rating")
    rating_word = next((c for c in rating_p["class"] if c != "star-rating"), None)

    availability_text = main.select_one("p.instock.availability").get_text(" ", strip=True)

    info = {}
    for row in soup.select("table.table-striped tr"):
        info[row.find("th").get_text(strip=True)] = row.find("td").get_text(strip=True)

    desc_heading = soup.find("div", id="product_description")
    description = (
        desc_heading.find_next_sibling("p").get_text(strip=True)
        if desc_heading else ""
    )

    image = soup.select_one("#product_gallery img")
    image_url = urljoin(url, image["src"]) if image else None

    return {
        "product_url": url,
        "title": main.h1.get_text(strip=True),
        "category": category,
        "rating_word": rating_word,
        "availability_text": availability_text,
        "image_url": image_url,
        "description": description,
        "upc": info.get("UPC"),
        "product_type": info.get("Product Type"),
        "price_excl_tax_text": info.get("Price (excl. tax)"),
        "price_incl_tax_text": info.get("Price (incl. tax)"),
        "tax_text": info.get("Tax"),
        "number_of_reviews_text": info.get("Number of reviews"),
    }

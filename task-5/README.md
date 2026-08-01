# Task 5 — Scraper: fetch → parse → extract → clean → structure

FlyRank Backend Track · Week 5

A scraper for [books.toscrape.com](https://books.toscrape.com/) — a sandbox site built
specifically for scraping practice (every page carries the disclaimer *"This is a demo website
for web scraping purposes"*). It crawls the catalogue, visits each book's detail page, and turns
the HTML into clean, typed, structured records saved as JSON and CSV. The output is meant to be
the kind of corpus a RAG pipeline could ingest directly — no raw HTML, no stray whitespace, no
string prices.

## Why this site

Scraping practice needs a target that *wants* to be scraped. books.toscrape.com is built by the
Scrapy/ScrapingHub team for exactly this: consistent markup, no login wall, no anti-bot
measures, and no ambiguity about whether scraping it is welcome. Its `robots.txt` doesn't exist
at all (`404`), which — per the standard convention `urllib.robotparser` itself implements — means
everything is allowed. The scraper still checks it before every request rather than assuming
that, so the same code behaves correctly against a site that *does* publish restrictions.

## Run it

```bash
cd task-5
pip install -r requirements.txt
python scraper.py --pages 5 --delay 1.0
```

```
python scraper.py --pages 1 --max-books 5 --delay 0.5   # quick smoke test
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--pages` | `5` | max catalogue listing pages to walk (20 books/page → 100 books) |
| `--max-books` | none | hard cap on total books scraped |
| `--delay` | `1.0` | minimum seconds between requests |
| `--output-dir` | `output/` | where `books.json` / `books.csv` land |

Output goes to `output/books.json` and `output/books.csv`. A 100-book run at the defaults takes
a little under 2 minutes — one request per second, ~105 requests (5 listing pages + 100 detail
pages).

## The pipeline

Each stage is its own module, matching the fetch → parse → extract/clean → structure → save flow:

| Stage | Module | Job |
|-------|--------|-----|
| Fetch | [`fetch.py`](fetch.py) | `PoliteFetcher` — robots.txt check, custom User-Agent, rate limiting, retries with backoff |
| Parse | [`parse.py`](parse.py) | BeautifulSoup selectors that locate the right tags and pull raw text/attrs, nothing else |
| Clean | [`clean.py`](clean.py) | Turns raw strings into typed values — `"£51.77"` → `51.77`, `"Three"` → `3`, `"In stock (22 available)"` → `(True, 22)` |
| Structure | [`models.py`](models.py) | `Book` dataclass — every record has the same shape, `None` where a page didn't have that field |
| Save | [`storage.py`](storage.py) | Writes the list of `Book` records to JSON and CSV |
| Orchestration | [`scraper.py`](scraper.py) | CLI entry point; walks listing pages for book URLs, then fetches + processes each detail page |

## Behaving like a bot the site owner would allow

- **Identifies itself.** Every request carries a real `User-Agent`:
  `FlyRankEduScraper/1.0 (+mailto:kamalmarie33@gmail.com; practice run on books.toscrape.com...)` —
  not a browser-spoofing string. Anyone looking at their access logs can tell what hit them and
  how to reach whoever's running it.
- **Checks robots.txt before every request**, via `urllib.robotparser`, and also picks up
  `Crawl-delay` if the site publishes one and widens the rate limit to match. This site has no
  robots.txt, but the check runs regardless — the same fetcher would refuse a disallowed path on
  a site that does publish one.
- **Rate-limited.** `PoliteFetcher` enforces a minimum gap between requests (default 1s, plus a
  little jitter) using a monotonic clock, not a flat `sleep()` per call — so retries and slow
  responses don't compound into a faster-than-intended crawl.
- **Retries politely, not aggressively.** Failed requests back off (`delay × attempt`) for up to
  3 attempts, then the scraper logs it and moves on rather than hammering a struggling endpoint.
- **Scoped by default.** `--pages 5` (100 books) is the default, not "crawl all 1000" — pulling
  the full catalogue is one flag away (`--pages 50`) but isn't the out-of-the-box behavior.

## Record schema

```json
{
  "title": "A Light in the Attic",
  "product_url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
  "category": "Poetry",
  "upc": "a897fe39b1053632",
  "product_type": "Books",
  "rating": 3,
  "price_excl_tax": 51.77,
  "price_incl_tax": 51.77,
  "tax": 0.0,
  "currency": "GBP",
  "in_stock": true,
  "stock_count": 22,
  "number_of_reviews": 0,
  "description": "It's hard to imagine a world without A Light in the Attic. ...",
  "image_url": "https://books.toscrape.com/media/cache/fe/72/fe72f0532301ec28892ae79a629a293c.jpg",
  "scraped_at": "2026-08-01T09:59:03.482968+00:00"
}
```

`category` comes from the breadcrumb on the detail page, `rating` is the star-rating word
(`One`–`Five`) mapped to an int, `stock_count` is parsed out of `"In stock (22 available)"` —
`null` if the page doesn't give a number. A full run's output lives in `output/books.json` /
`output/books.csv` (git-ignored, regenerated by running the scraper); a 5-record
[`output/sample_books.json`](output/sample_books.json) /
[`output/sample_books.csv`](output/sample_books.csv) is committed so the shape is visible without
running anything.

## A real bug this caught

First pass through the pipeline, non-English titles came out mangled — `"Soumission"`'s French
description turned `nôtre` into `nÃ´tre`. The page declares its encoding in an HTML
`<meta http-equiv="content-type" content="text/html; charset=UTF-8">` tag, but the HTTP response
header just says `Content-Type: text/html` with no charset. `requests` only trusts the header, so
`response.text` silently decoded UTF-8 bytes as Latin-1. Fix: feed BeautifulSoup the raw
`response.content` bytes instead of the pre-decoded `.text` — BeautifulSoup's own encoding
sniffer reads the `<meta>` tag and gets it right. `parse.py`'s two functions take bytes, not str,
for exactly this reason.

One thing left as-is, deliberately: a few book descriptions (e.g. *A Light in the Attic*,
*Soumission*) contain a repeated chunk of text in the middle. Checked the raw HTML directly —
it's really there on the source page, not something the parser introduced. Scraped text should
match the source, quirks included.

## Notes

- No API exists for this site — everything here is HTML scraping by design, which is the point
  of the exercise.
- `requests.Session` is reused across the whole run (`fetch.py`), so TCP connections to
  `books.toscrape.com` get pooled instead of reconnecting per request.
- This becomes the corpus for later retrieval work: structured, typed records are what makes a
  RAG pipeline's job tractable — no re-scraping or re-parsing raw HTML at query time.

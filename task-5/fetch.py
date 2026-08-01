"""Fetch stage: a polite HTTP client.

Identifies itself with a real User-Agent, checks robots.txt before every
request, and rate-limits so requests go out no faster than one per `delay`
seconds.
"""
from __future__ import annotations

import time
import random
import urllib.robotparser
from urllib.parse import urljoin

import requests

USER_AGENT = (
    "FlyRankEduScraper/1.0 "
    "(+mailto:kamalmarie33@gmail.com; practice run on books.toscrape.com, "
    "a site built for scraping exercises)"
)


class PoliteFetcher:
    """requests.Session wrapper that won't fetch a URL robots.txt disallows
    and won't fetch faster than the configured delay."""

    def __init__(self, base_url: str, delay: float = 1.0, timeout: float = 10.0,
                 max_retries: int = 3):
        self.delay = delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last_request_at = 0.0

        self.robots = urllib.robotparser.RobotFileParser()
        self.robots.set_url(urljoin(base_url, "/robots.txt"))
        try:
            # A missing robots.txt (404) makes RobotFileParser allow
            # everything by default, which is the standard convention.
            self.robots.read()
        except OSError:
            # Robots.txt itself was unreachable (DNS/connection failure) --
            # fail closed rather than assume permission.
            self.robots.disallow_all = True

        crawl_delay = self.robots.crawl_delay(USER_AGENT)
        if crawl_delay is not None:
            self.delay = max(self.delay, float(crawl_delay))

    def allowed(self, url: str) -> bool:
        return self.robots.can_fetch(USER_AGENT, url)

    def get(self, url: str) -> requests.Response | None:
        """Fetch `url`, or return None if robots.txt disallows it, it 404s,
        or every retry fails."""
        if not self.allowed(url):
            print(f"  [robots.txt] disallowed, skipping: {url}")
            return None

        self._throttle()

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                self._last_request_at = time.monotonic()
                if resp.status_code == 200:
                    return resp
                if resp.status_code == 404:
                    print(f"  [fetch] 404, skipping: {url}")
                    return None
                print(f"  [fetch] HTTP {resp.status_code} on {url} "
                      f"(attempt {attempt}/{self.max_retries})")
            except requests.RequestException as exc:
                print(f"  [fetch] {exc} on {url} (attempt {attempt}/{self.max_retries})")
            time.sleep(self.delay * attempt)
        return None

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = self.delay - elapsed
        if wait > 0:
            time.sleep(wait + random.uniform(0, 0.25))

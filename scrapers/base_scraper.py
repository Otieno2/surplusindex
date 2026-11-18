"""Abstract base scraper with rate-limiting, rotation, and retry logic."""

import logging
import os
import random
import time
from abc import ABC, abstractmethod
from typing import Any

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base scraper with built-in anti-detection measures."""

    def __init__(self, delay_range: tuple[float, float] = (2.0, 5.0), max_retries: int = 3):
        self.delay_range = delay_range
        self.max_retries = max_retries
        self.session = requests.Session()
        self._ua = UserAgent(browsers=["chrome", "firefox", "edge"])
        self.browser_enabled = os.getenv("SURPLUSINDEX_BROWSER", "1") != "0"
        self._browser = None
        self._browser_context = None
        self._request_count = 0

    @property
    def headers(self) -> dict[str, str]:
        return {
            "User-Agent": self._ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def _throttle(self) -> None:
        delay = random.uniform(*self.delay_range)
        self._request_count += 1
        if self._request_count % 10 == 0:
            delay *= 2
            logger.info("Extended delay after %d requests", self._request_count)
        time.sleep(delay)

    def fetch_page(self, url: str) -> BeautifulSoup | None:
        for attempt in range(self.max_retries):
            try:
                self._throttle()
                resp = self.session.get(url, headers=self.headers, timeout=30)
                if resp.status_code in {403, 429} and self.browser_enabled:
                    logger.info("HTTP %s for %s; trying compliant browser rendering", resp.status_code, url)
                    rendered = self._fetch_with_browser(url)
                    if rendered is not None:
                        return rendered
                resp.raise_for_status()
                return BeautifulSoup(resp.text, "lxml")
            except requests.RequestException as e:
                logger.warning("Attempt %d failed for %s: %s", attempt + 1, url, e)
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** (attempt + 1))
        return None

    def _fetch_with_browser(self, url: str) -> BeautifulSoup | None:
        """Render a public page with Playwright; do not evade CAPTCHAs or access controls."""
        try:
            from playwright.sync_api import sync_playwright

            if self._browser_context is None:
                self._browser = sync_playwright().start()
                self._browser_context = self._browser.chromium.launch(headless=True).new_context(
                    locale="en-US",
                    user_agent=self.headers["User-Agent"],
                )
            page = self._browser_context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(1_500)
            if response is None or response.status >= 400:
                logger.warning("Browser fetch returned HTTP %s for %s", response.status if response else "unknown", url)
                page.close()
                return None
            html = page.content()
            page.close()
            return BeautifulSoup(html, "lxml")
        except Exception as exc:
            logger.warning("Browser rendering unavailable for %s: %s", url, exc)
            return None

    def close(self) -> None:
        """Release an optional Playwright context."""
        if self._browser_context is not None:
            self._browser_context.browser.close()
            self._browser_context = None
        if self._browser is not None:
            self._browser.stop()
            self._browser = None

    @abstractmethod
    def scrape(self) -> list[dict[str, Any]]:
        """Execute the scraping pipeline. Returns list of structured records."""

    @abstractmethod
    def get_source_name(self) -> str:
        """Return a human-readable name for this data source."""

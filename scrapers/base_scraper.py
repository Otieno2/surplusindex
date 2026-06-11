"""Abstract base scraper with rate-limiting, rotation, and retry logic."""

import logging
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
                resp.raise_for_status()
                return BeautifulSoup(resp.text, "lxml")
            except requests.RequestException as e:
                logger.warning("Attempt %d failed for %s: %s", attempt + 1, url, e)
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** (attempt + 1))
        return None

    @abstractmethod
    def scrape(self) -> list[dict[str, Any]]:
        """Execute the scraping pipeline. Returns list of structured records."""

    @abstractmethod
    def get_source_name(self) -> str:
        """Return a human-readable name for this data source."""

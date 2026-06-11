"""Scraper for liquidation pallet auctions across major platforms."""

import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class PalletScraper(BaseScraper):
    """Scrapes pallet auction listings from liquidation platforms.

    Targets public search/category pages. Extracts:
    - Auction ID, title, platform
    - Total MSRP, current bid
    - Number of items, end time
    - Category/condition
    """

    SOURCES = {
        "liquidation_com": {
            "base_url": "https://www.liquidation.com",
            "categories": [
                "/auctions/computers-networking/",
                "/auctions/consumer-electronics/",
                "/auctions/general-merchandise/",
                "/auctions/apparel/",
                "/auctions/home-garden/",
            ],
        },
        "directliquidation": {
            "base_url": "https://www.directliquidation.com",
            "categories": [
                "/listings/electronics/",
                "/listings/home-and-garden/",
                "/listings/apparel/",
            ],
        },
        "bstock": {
            "base_url": "https://bstock.com",
            "categories": [
                "/listings/",
            ],
        },
    }

    def get_source_name(self) -> str:
        return "Liquidation Pallet Auctions"

    def scrape(self) -> list[dict[str, Any]]:
        """Scrape all configured pallet auction sources."""
        all_listings: list[dict[str, Any]] = []

        for source_name, config in self.SOURCES.items():
            logger.info("Scraping %s...", source_name)
            for category_path in config["categories"]:
                url = urljoin(config["base_url"], category_path)
                soup = self.fetch_page(url)
                if soup is None:
                    logger.warning("Failed to fetch %s", url)
                    continue

                parser = getattr(self, f"_parse_{source_name}", None)
                if parser:
                    listings = parser(soup, config["base_url"], category_path)
                    all_listings.extend(listings)
                    logger.info("Found %d listings from %s%s", len(listings), source_name, category_path)

        return all_listings

    def _parse_liquidation_com(
        self, soup: BeautifulSoup, base_url: str, category_path: str
    ) -> list[dict[str, Any]]:
        listings: list[dict[str, Any]] = []
        cards = soup.select(".auction-item, .lot-card, [data-auction-id]")

        for card in cards:
            if not isinstance(card, Tag):
                continue
            listing = self._extract_listing_data(card, "Liquidation.com", base_url)
            if listing:
                listing["category"] = category_path.strip("/").split("/")[-1]
                listings.append(listing)

        return listings

    def _parse_directliquidation(
        self, soup: BeautifulSoup, base_url: str, category_path: str
    ) -> list[dict[str, Any]]:
        listings: list[dict[str, Any]] = []
        cards = soup.select(".listing-card, .product-item, [data-listing-id]")

        for card in cards:
            if not isinstance(card, Tag):
                continue
            listing = self._extract_listing_data(card, "DirectLiquidation", base_url)
            if listing:
                listing["category"] = category_path.strip("/").split("/")[-1]
                listings.append(listing)

        return listings

    def _parse_bstock(
        self, soup: BeautifulSoup, base_url: str, category_path: str
    ) -> list[dict[str, Any]]:
        listings: list[dict[str, Any]] = []
        cards = soup.select(".listing-card, .auction-card, [data-lot-id]")

        for card in cards:
            if not isinstance(card, Tag):
                continue
            listing = self._extract_listing_data(card, "B-Stock", base_url)
            if listing:
                listing["category"] = "general"
                listings.append(listing)

        return listings

    def _extract_listing_data(
        self, card: Tag, platform: str, base_url: str
    ) -> dict[str, Any] | None:
        """Generic extraction from a listing card element."""
        title_el = card.select_one(
            "h3, h4, .title, .lot-title, .listing-title, [class*='title']"
        )
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            return None

        auction_id = (
            card.get("data-auction-id")
            or card.get("data-listing-id")
            or card.get("data-lot-id")
            or self._generate_id(platform, title)
        )

        msrp = self._extract_price(card, ["msrp", "retail", "original"])
        current_bid = self._extract_price(card, ["bid", "price", "current"])
        item_count = self._extract_number(card, ["items", "units", "quantity", "count"])
        end_time = self._extract_end_time(card)

        if not msrp and not current_bid:
            return None

        msrp_val = msrp or 0.0
        bid_val = current_bid or 0.0
        spread = msrp_val - bid_val if msrp_val > bid_val else 0.0
        cost_per_unit = bid_val / item_count if item_count and item_count > 0 else 0.0

        return {
            "auction_id": str(auction_id),
            "title": title,
            "platform": platform,
            "total_msrp": round(msrp_val, 2),
            "current_bid": round(bid_val, 2),
            "spread": round(spread, 2),
            "number_of_items": item_count or 1,
            "cost_per_unit": round(cost_per_unit, 2),
            "end_time": end_time,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "source_url": base_url,
        }

    def _extract_price(self, card: Tag, keywords: list[str]) -> float | None:
        for kw in keywords:
            el = card.select_one(f"[class*='{kw}'], [data-{kw}]")
            if el:
                text = el.get_text(strip=True)
                match = re.search(r"[\$£€]?([\d,]+\.?\d*)", text)
                if match:
                    return float(match.group(1).replace(",", ""))
            attr_val = card.get(f"data-{kw}")
            if attr_val:
                try:
                    return float(str(attr_val).replace(",", "").replace("$", ""))
                except ValueError:
                    pass
        return None

    def _extract_number(self, card: Tag, keywords: list[str]) -> int | None:
        for kw in keywords:
            el = card.select_one(f"[class*='{kw}'], [data-{kw}]")
            if el:
                text = el.get_text(strip=True)
                match = re.search(r"(\d+)", text)
                if match:
                    return int(match.group(1))
        text = card.get_text()
        patterns = [r"(\d+)\s*(?:items|units|pcs|pieces)", r"Lot of (\d+)"]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def _extract_end_time(self, card: Tag) -> str | None:
        time_el = card.select_one("time, [data-end-time], [class*='countdown'], [class*='timer']")
        if time_el:
            datetime_attr = time_el.get("datetime")
            if datetime_attr:
                return str(datetime_attr)
            data_end = time_el.get("data-end-time")
            if data_end:
                return str(data_end)
        return None

    @staticmethod
    def _generate_id(platform: str, title: str) -> str:
        slug = re.sub(r"[^a-z0-9]", "", title.lower()[:20])
        return f"{platform[:3].upper()}-{slug}-{int(datetime.now(timezone.utc).timestamp()) % 100000}"

"""Scraper for liquidation pallet auctions across major platforms."""

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests
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
                "/wholesale-computers.html",
                "/consumer-electronics.html",
                "/general-merchandise.html",
            ],
        },
        "directliquidation": {
            "base_url": "https://www.directliquidation.com",
            "categories": [
                "/search?sort=newestListings",
                "/electronics",
            ],
        },
        "gsa": {
            "base_url": "https://api.gsa.gov",
            "categories": ["/assets/gsaauctions/v2/auctions"],
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
                if source_name == "gsa":
                    listings = self._fetch_gsa(category_path)
                    all_listings.extend(listings)
                    logger.info("Found %d listings from GSA Auctions", len(listings))
                    continue

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

        self.close()
        return all_listings

    def _parse_liquidation_com(
        self, soup: BeautifulSoup, base_url: str, category_path: str
    ) -> list[dict[str, Any]]:
        listings: list[dict[str, Any]] = []
        cards = self._find_liquidation_cards(soup)

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
        cards = self._find_direct_liquidation_cards(soup)

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

    @staticmethod
    def _find_liquidation_cards(soup: BeautifulSoup) -> list[Tag]:
        cards: list[Tag] = []
        seen: set[str] = set()
        for link in soup.select("a[href*='/auction/view?id=']"):
            href = str(link.get("href", ""))
            if href in seen:
                continue
            seen.add(href)
            container = link.find_parent(
                lambda tag: isinstance(tag, Tag)
                and "Current Bid" in tag.get_text(" ", strip=True)
            )
            cards.append(container or link.parent)
        return cards

    @staticmethod
    def _find_direct_liquidation_cards(soup: BeautifulSoup) -> list[Tag]:
        cards = soup.select(".listing-card, .product-item, [data-listing-id]")
        if cards:
            return [card for card in cards if isinstance(card, Tag)]
        return [
            link.find_parent("article") or link.parent
            for link in soup.select("a[href*='/listing'], a[href*='/product']")
        ]

    def _fetch_gsa(self, path: str) -> list[dict[str, Any]]:
        """Fetch live GSA listings through its documented public API."""
        api_key = os.getenv("GSA_API_KEY", "DEMO_KEY")
        url = f"{self.SOURCES['gsa']['base_url']}{path}"
        try:
            self._throttle()
            response = self.session.get(
                url,
                params={"api_key": api_key, "format": "JSON"},
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("GSA Auctions API failed: %s", exc)
            return []

        listings: list[dict[str, Any]] = []
        for item in payload.get("Results", payload.get("results", [])):
            title = str(item.get("itemName") or item.get("ItemName") or "GSA surplus lot").strip()
            if not title:
                continue
            high_bid = self._parse_money(item.get("highBidAmount") or item.get("HighBidAmount"))
            lot_info = item.get("lotInfo") or item.get("LotInfo") or []
            item_count = len(lot_info) if isinstance(lot_info, list) else 1
            sale_no = item.get("saleNo", item.get("SaleNo", "unknown"))
            lot_no = item.get("lotNo", item.get("LotNo", "unknown"))
            end_time = item.get("aucEndDt") or item.get("AucEndDt")
            listings.append({
                "auction_id": f"GSA-{sale_no}-{lot_no}",
                "title": title,
                "platform": "GSA Auctions",
                "total_msrp": 0.0,
                "current_bid": high_bid,
                "spread": 0.0,
                "spread_pct": 0.0,
                "number_of_items": item_count,
                "cost_per_unit": round(high_bid / item_count, 2),
                "condition": "Mixed",
                "hours_remaining": self._estimate_hours_remaining(end_time),
                "num_bids": int(item.get("biddersCount") or item.get("BiddersCount") or 0),
                "end_time": end_time,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "source_url": item.get("itemDescURL") or item.get("ItemDescURL") or "https://www.gsaauctions.gov/",
                "category": "government-surplus",
            })
        return listings

    @staticmethod
    def _parse_money(value: Any) -> float:
        match = re.search(r"[\d,]+(?:\.\d+)?", str(value or ""))
        return float(match.group(0).replace(",", "")) if match else 0.0

    def _extract_listing_data(
        self, card: Tag, platform: str, base_url: str
    ) -> dict[str, Any] | None:
        """Generic extraction from a listing card element."""
        title_el = card.select_one(
            "h3, h4, .title, .lot-title, .listing-title, [class*='title'], "
            "a[href*='/auction/view?id=']"
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
        text = card.get_text(" ", strip=True)
        msrp = msrp or self._extract_labeled_money(text, ["Est. Retail", "MSRP", "Retail"])
        current_bid = current_bid or self._extract_labeled_money(text, ["Current Bid", "Current Price"])
        item_count = self._extract_number(card, ["items", "units", "quantity", "count"])
        end_time = self._extract_end_time(card)

        if not msrp and not current_bid:
            return None

        msrp_val = msrp or 0.0
        bid_val = current_bid or 0.0
        spread = msrp_val - bid_val if msrp_val > bid_val else 0.0
        spread_pct = (spread / msrp_val * 100) if msrp_val > 0 else 0.0
        cost_per_unit = bid_val / item_count if item_count and item_count > 0 else 0.0

        condition = self._extract_condition(card)
        hours_remaining = self._estimate_hours_remaining(end_time)
        link = card.select_one("a[href]")
        source_url = urljoin(base_url, str(link["href"])) if link and link.get("href") else base_url

        return {
            "auction_id": str(auction_id),
            "title": title,
            "platform": platform,
            "total_msrp": round(msrp_val, 2),
            "current_bid": round(bid_val, 2),
            "spread": round(spread, 2),
            "spread_pct": round(spread_pct, 1),
            "number_of_items": item_count or 1,
            "cost_per_unit": round(cost_per_unit, 2),
            "condition": condition,
            "hours_remaining": hours_remaining,
            "num_bids": self._extract_number(card, ["bids", "bid-count"]) or 0,
            "end_time": end_time,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "source_url": source_url,
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

    @staticmethod
    def _extract_labeled_money(text: str, labels: list[str]) -> float | None:
        label_pattern = "|".join(re.escape(label) for label in labels)
        match = re.search(
            rf"(?:{label_pattern})\s*:?\s*\$?([\d,]+(?:\.\d+)?)",
            text,
            re.IGNORECASE,
        )
        return float(match.group(1).replace(",", "")) if match else None

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
    def _extract_condition(card: Tag) -> str:
        """Extract condition label from the card."""
        cond_el = card.select_one("[class*='condition'], [data-condition]")
        if cond_el:
            attr = cond_el.get("data-condition")
            if attr:
                return str(attr)
            return cond_el.get_text(strip=True)
        text = card.get_text()
        for label in ["Like New", "Refurbished", "Used", "As-Is", "Salvage", "New"]:
            if label.lower() in text.lower():
                return label
        return "Mixed"

    @staticmethod
    def _estimate_hours_remaining(end_time: str | None) -> int:
        """Estimate hours remaining from an ISO end_time string."""
        if not end_time:
            return 0
        try:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            delta = end_dt - datetime.now(timezone.utc)
            return max(int(delta.total_seconds() / 3600), 0)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _generate_id(platform: str, title: str) -> str:
        slug = re.sub(r"[^a-z0-9]", "", title.lower()[:20])
        return f"{platform[:3].upper()}-{slug}-{int(datetime.now(timezone.utc).timestamp()) % 100000}"

"""Scraper for IT Asset Disposition (ITAD) hardware pricing — the 'Blue Book' index."""

import logging
import re
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup, Tag

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


# Enterprise hardware categories with common models to track
HARDWARE_CATEGORIES = {
    "servers": {
        "models": [
            "Dell PowerEdge R740",
            "Dell PowerEdge R640",
            "Dell PowerEdge R750",
            "Dell PowerEdge R650",
            "HP ProLiant DL380 Gen10",
            "HP ProLiant DL360 Gen10",
            "HP ProLiant DL380 Gen11",
            "Lenovo ThinkSystem SR650",
            "Lenovo ThinkSystem SR630",
            "Cisco UCS C220 M5",
            "Cisco UCS C240 M5",
            "Supermicro SYS-6029P",
        ],
        "keywords": ["rack server", "tower server", "blade server"],
    },
    "networking": {
        "models": [
            "Cisco Catalyst 9300",
            "Cisco Catalyst 9200",
            "Cisco Nexus 9000",
            "Cisco ISR 4431",
            "Cisco ASR 1001-X",
            "Juniper EX4300",
            "Juniper SRX340",
            "Arista 7050X",
            "HP Aruba 2930F",
            "Meraki MS250",
            "Ubiquiti USW-Pro-48",
            "Fortinet FortiGate 60F",
        ],
        "keywords": ["network switch", "router", "firewall", "access point"],
    },
    "storage": {
        "models": [
            "Dell EMC PowerStore",
            "NetApp FAS2750",
            "NetApp AFF A250",
            "HPE MSA 2060",
            "Pure Storage FlashArray",
            "Synology RS1221+",
            "QNAP TS-873A",
            "Dell EqualLogic PS6210",
        ],
        "keywords": ["SAN", "NAS", "storage array", "JBOD"],
    },
    "workstations": {
        "models": [
            "Dell Precision 5820",
            "Dell Precision 7920",
            "HP Z6 G4",
            "HP Z8 G4",
            "Lenovo ThinkStation P520",
            "Lenovo ThinkStation P920",
            "Apple Mac Pro 2019",
        ],
        "keywords": ["workstation", "professional desktop"],
    },
    "memory": {
        "models": [
            "DDR4 32GB ECC RDIMM",
            "DDR4 64GB ECC RDIMM",
            "DDR4 16GB ECC RDIMM",
            "DDR5 32GB ECC RDIMM",
            "DDR5 64GB ECC RDIMM",
            "DDR4 32GB SODIMM",
            "DDR4 16GB Desktop",
            "DDR4 8GB Desktop",
            "DDR3 8GB Desktop",
            "DDR3 4GB Desktop",
        ],
        "keywords": ["RAM", "memory module", "DIMM", "SODIMM"],
    },
    "processors": {
        "models": [
            "Intel Xeon Gold 6248",
            "Intel Xeon Gold 6258R",
            "Intel Xeon Silver 4214",
            "Intel Xeon Platinum 8280",
            "AMD EPYC 7742",
            "AMD EPYC 7763",
            "Intel Core i9-13900K",
            "Intel Core i7-13700K",
        ],
        "keywords": ["CPU", "processor", "Xeon", "EPYC"],
    },
    "gpus": {
        "models": [
            "NVIDIA Tesla V100",
            "NVIDIA A100 40GB",
            "NVIDIA A100 80GB",
            "NVIDIA RTX A6000",
            "NVIDIA RTX 4090",
            "NVIDIA RTX 3090",
            "NVIDIA T4",
            "AMD Instinct MI250",
        ],
        "keywords": ["GPU", "graphics card", "accelerator"],
    },
}


class ITADScraper(BaseScraper):
    """Scrapes IT hardware pricing from refurbishers, eBay sold listings, and surplus sites.

    Builds a 'Kelly Blue Book' style index for used enterprise hardware.
    """

    SOURCES = {
        "pcliquidations": {
            "base_url": "https://www.pcliquidations.com",
            "search_path": "/search?q=",
        },
        "servermonkey": {
            "base_url": "https://www.servermonkey.com",
            "search_path": "/search?type=product&q=",
        },
        "govdeals": {
            "base_url": "https://www.govdeals.com",
            "search_path": (
                "/index.cfm?fa=Main.AdvSearchResultsNew"
                "&searchPg=Category&additession=&inv_num=&agency=&state=&description="
            ),
        },
    }

    def get_source_name(self) -> str:
        return "IT Asset Disposition Hardware Index"

    def scrape(self) -> list[dict[str, Any]]:
        """Scrape hardware pricing across all configured sources and models."""
        all_records: list[dict[str, Any]] = []

        for category, config in HARDWARE_CATEGORIES.items():
            logger.info("Scraping category: %s", category)
            for model in config["models"]:
                record = self._scrape_model(model, category)
                if record:
                    all_records.append(record)
                    logger.info("Got pricing for %s", model)

        return all_records

    def _scrape_model(self, model: str, category: str) -> dict[str, Any] | None:
        """Aggregate pricing data for a specific hardware model across sources."""
        prices: dict[str, float | None] = {}

        for source_name, config in self.SOURCES.items():
            url = config["base_url"] + config["search_path"] + model.replace(" ", "+")
            soup = self.fetch_page(url)
            if soup is None:
                continue

            price = self._extract_best_price(soup, source_name)
            prices[source_name] = price

        valid_prices = [p for p in prices.values() if p is not None and p > 0]
        if not valid_prices:
            return None

        avg_price = sum(valid_prices) / len(valid_prices)
        min_price = min(valid_prices)
        max_price = max(valid_prices)

        demand = self._calculate_demand(len(valid_prices), avg_price, category)

        return {
            "component_type": category,
            "model": model,
            # Live sources do not reliably expose MSRP or listing history. Keep
            # the output schema stable so the static renderer can handle it.
            "new_msrp": 0.0,
            "avg_market_price": round(avg_price, 2),
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2),
            "refurbished_retail_price": round(max_price * 1.3, 2),
            "bulk_lot_avg_price_per_unit": round(min_price * 0.7, 2),
            "depreciation_pct": 0.0,
            "price_sources": len(valid_prices),
            "active_listings": 0,
            "price_history": [],
            "market_demand_rating": demand,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "slug": re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-"),
        }

    def _extract_best_price(self, soup: BeautifulSoup, source: str) -> float | None:
        """Extract the most relevant price from a search results page."""
        price_selectors = [
            ".price",
            ".product-price",
            "[class*='price']",
            ".amount",
            "[data-price]",
            ".sale-price",
            ".regular-price",
        ]

        prices_found: list[float] = []
        for selector in price_selectors:
            elements = soup.select(selector)
            for el in elements[:5]:
                if not isinstance(el, Tag):
                    continue
                price_val = el.get("data-price")
                if price_val:
                    try:
                        prices_found.append(float(str(price_val)))
                        continue
                    except ValueError:
                        pass
                text = el.get_text(strip=True)
                match = re.search(r"[\$]?([\d,]+\.?\d*)", text)
                if match:
                    val = float(match.group(1).replace(",", ""))
                    if 1.0 < val < 500000.0:
                        prices_found.append(val)

        if prices_found:
            return sorted(prices_found)[len(prices_found) // 2]
        return None

    @staticmethod
    def _calculate_demand(num_sources: int, avg_price: float, category: str) -> str:
        """Estimate market demand based on data availability and price levels."""
        high_demand_categories = {"gpus", "memory", "processors", "networking"}
        score = num_sources * 2

        if category in high_demand_categories:
            score += 2
        if avg_price < 500:
            score += 1
        elif avg_price > 5000:
            score -= 1

        if score >= 5:
            return "High"
        elif score >= 3:
            return "Medium-High"
        elif score >= 2:
            return "Medium"
        else:
            return "Low"

"""Minimal LLM text generation — produces brief, data-anchored summaries.

Design goal: Keep LLM-generated text to ~15% of page weight.
Each summary is 2-3 sentences, anchored to real numerical data.
Falls back to template-based generation when no LLM API is available.
"""

import hashlib
import logging
import os
import random
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class LLMSummarizer:
    """Generate minimal, data-anchored text summaries for pages."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._use_api = bool(self.api_key)
        if not self._use_api:
            logger.info("No OpenAI API key found; using template-based summaries")

    def summarize_pallet(self, listing: dict[str, Any]) -> str:
        """Generate a brief summary for a pallet auction listing."""
        if self._use_api:
            return self._api_summarize_pallet(listing)
        return self._template_summarize_pallet(listing)

    def summarize_hardware(self, record: dict[str, Any]) -> str:
        """Generate a brief summary for an ITAD hardware listing."""
        if self._use_api:
            return self._api_summarize_hardware(record)
        return self._template_summarize_hardware(record)

    def _api_summarize_pallet(self, listing: dict[str, Any]) -> str:
        """Use OpenAI API to generate a pallet summary."""
        try:
            import requests

            prompt = (
                f"Write exactly 2 sentences about this liquidation auction. "
                f"Include specific numbers. No marketing language.\n"
                f"Title: {listing['title']}\n"
                f"MSRP: ${listing['total_msrp']:,.2f}\n"
                f"Current Bid: ${listing['current_bid']:,.2f}\n"
                f"Items: {listing['number_of_items']}\n"
                f"Platform: {listing['platform']}"
            )

            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100,
                    "temperature": 0.7,
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning("API call failed, falling back to template: %s", e)
            return self._template_summarize_pallet(listing)

    def _api_summarize_hardware(self, record: dict[str, Any]) -> str:
        """Use OpenAI API to generate a hardware summary."""
        try:
            import requests

            prompt = (
                f"Write exactly 2 sentences about this used enterprise hardware price. "
                f"Include specific numbers. No marketing language.\n"
                f"Model: {record['model']}\n"
                f"Average Used Price: ${record['avg_market_price']:,.2f}\n"
                f"New MSRP: ${record.get('new_msrp', 0):,.2f}\n"
                f"Active Listings: {record.get('active_listings', 'N/A')}\n"
                f"Demand: {record['market_demand_rating']}"
            )

            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100,
                    "temperature": 0.7,
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning("API call failed, falling back to template: %s", e)
            return self._template_summarize_hardware(record)

    def _template_summarize_pallet(self, listing: dict[str, Any]) -> str:
        """Generate a template-based pallet summary with randomized phrasing."""
        spread = listing.get("spread", listing["total_msrp"] - listing["current_bid"])
        spread_pct = listing.get("spread_pct", 0)
        if spread_pct == 0 and listing["total_msrp"] > 0:
            spread_pct = round((spread / listing["total_msrp"]) * 100, 1)
        cost_per = listing.get("cost_per_unit", 0)

        seed = int(hashlib.md5(listing.get("auction_id", "").encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)

        openers = [
            f"This {listing['platform']} lot contains {listing['number_of_items']} items "
            f"with a combined retail value of ${listing['total_msrp']:,.0f}.",
            f"Currently listed on {listing['platform']}, this {listing['number_of_items']}-item "
            f"lot carries a total MSRP of ${listing['total_msrp']:,.0f}.",
            f"A {listing['number_of_items']}-unit lot on {listing['platform']} with "
            f"${listing['total_msrp']:,.0f} in combined retail value.",
        ]

        closers = [
            f"At the current bid of ${listing['current_bid']:,.0f}, "
            f"the liquidation spread is ${spread:,.0f} ({spread_pct:.0f}% below MSRP) "
            f"at ${cost_per:,.2f} per unit.",
            f"The active bid of ${listing['current_bid']:,.0f} represents a "
            f"{spread_pct:.0f}% discount from retail, "
            f"pricing each item at approximately ${cost_per:,.2f}.",
            f"Bidding stands at ${listing['current_bid']:,.0f} — a ${spread:,.0f} spread "
            f"that works out to ${cost_per:,.2f} per unit.",
        ]

        return f"{rng.choice(openers)} {rng.choice(closers)}"

    def _template_summarize_hardware(self, record: dict[str, Any]) -> str:
        """Generate a template-based hardware summary with randomized phrasing."""
        depreciation = record.get("depreciation_pct", 0)
        if depreciation == 0 and record.get("new_msrp"):
            depreciation = round(
                (1 - record["avg_market_price"] / record["new_msrp"]) * 100, 1
            )
        listings_count = record.get("active_listings", record.get("price_sources", 0))

        seed = int(hashlib.md5(record["model"].encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)

        today = datetime.now(timezone.utc).strftime("%B %Y")

        openers = [
            f"The average used market price for a {record['model']} is currently "
            f"${record['avg_market_price']:,.2f} as of {today}.",
            f"As of {today}, the {record['model']} trades at an average of "
            f"${record['avg_market_price']:,.2f} on the secondary market.",
            f"Current market data shows the {record['model']} averaging "
            f"${record['avg_market_price']:,.2f} across used and refurbished channels.",
        ]

        closers = [
            f"With {listings_count} active listings tracked across "
            f"{record.get('price_sources', 3)} sources, prices range from "
            f"${record['min_price']:,.2f} to ${record['max_price']:,.2f} "
            f"({depreciation:.0f}% depreciation from ${record.get('new_msrp', 0):,.0f} MSRP).",
            f"Prices span ${record['min_price']:,.2f}–${record['max_price']:,.2f} "
            f"across {record.get('price_sources', 3)} tracked sources, "
            f"reflecting {depreciation:.0f}% depreciation from the original "
            f"${record.get('new_msrp', 0):,.0f} list price.",
            f"Market demand is rated {record['market_demand_rating']} with "
            f"{listings_count} listings ranging ${record['min_price']:,.2f}–"
            f"${record['max_price']:,.2f}, "
            f"a {depreciation:.0f}% decline from ${record.get('new_msrp', 0):,.0f} new.",
        ]

        return f"{rng.choice(openers)} {rng.choice(closers)}"

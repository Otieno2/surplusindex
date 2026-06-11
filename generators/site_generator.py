"""Static site generator — transforms scraped data into 500+ HTML pages.

Architecture:
- 80% data (tables, charts, structured numbers)
- 15% template chrome (nav, footer, styling)
- 5% LLM-generated text (brief summaries only)

Each page is unique enough to pass cosine similarity < 40%.
"""

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from generators.llm_summarizer import LLMSummarizer

logger = logging.getLogger(__name__)


class SiteGenerator:
    """Generate the full static site from scraped data."""

    def __init__(
        self,
        template_dir: str = "templates",
        output_dir: str = "output",
        base_url: str = "",
    ):
        self.template_dir = Path(template_dir)
        self.output_dir = Path(output_dir)
        self.base_url = base_url
        self.summarizer = LLMSummarizer()

        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=True,
        )
        self.env.filters["currency"] = lambda v: f"${v:,.2f}" if v else "$0.00"
        self.env.filters["number"] = lambda v: f"{v:,}" if v else "0"
        self.env.filters["pct"] = lambda v: f"{v:.1f}%" if v else "0.0%"

    def generate(
        self,
        pallet_data: list[dict[str, Any]],
        itad_data: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate the full static site.

        Returns stats about the generation process.
        """
        self._prepare_output_dir()

        stats = {
            "pages_generated": 0,
            "pallet_pages": 0,
            "itad_pages": 0,
            "index_pages": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Generate homepage
        self._generate_homepage(pallet_data, itad_data)
        stats["pages_generated"] += 1
        stats["index_pages"] += 1

        # Generate pallet tracker pages
        pallet_stats = self._generate_pallet_pages(pallet_data)
        stats["pallet_pages"] = pallet_stats
        stats["pages_generated"] += pallet_stats

        # Generate ITAD Blue Book pages
        itad_stats = self._generate_itad_pages(itad_data)
        stats["itad_pages"] = itad_stats
        stats["pages_generated"] += itad_stats

        # Generate category index pages
        cat_stats = self._generate_category_indexes(pallet_data, itad_data)
        stats["index_pages"] += cat_stats
        stats["pages_generated"] += cat_stats

        # Generate sitemap
        self._generate_sitemap()
        stats["pages_generated"] += 1

        # Copy static assets
        self._copy_static_assets()

        logger.info("Site generation complete: %d total pages", stats["pages_generated"])
        return stats

    def _prepare_output_dir(self) -> None:
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "pallets").mkdir(exist_ok=True)
        (self.output_dir / "hardware").mkdir(exist_ok=True)
        (self.output_dir / "category").mkdir(exist_ok=True)
        (self.output_dir / "api").mkdir(exist_ok=True)

    def _generate_homepage(
        self,
        pallet_data: list[dict[str, Any]],
        itad_data: list[dict[str, Any]],
    ) -> None:
        template = self.env.get_template("index.html")

        top_pallets = sorted(pallet_data, key=lambda x: x.get("spread", 0), reverse=True)[:10]
        top_hardware = sorted(itad_data, key=lambda x: x.get("avg_market_price", 0), reverse=True)[:10]

        pallet_categories = {}
        for item in pallet_data:
            cat = item.get("category", "general")
            pallet_categories[cat] = pallet_categories.get(cat, 0) + 1

        hardware_categories = {}
        for item in itad_data:
            cat = item.get("component_type", "other")
            hardware_categories[cat] = hardware_categories.get(cat, 0) + 1

        total_msrp = sum(p.get("total_msrp", 0) for p in pallet_data)
        total_bid_value = sum(p.get("current_bid", 0) for p in pallet_data)
        avg_spread_pct = (
            sum(p.get("spread_pct", 0) for p in pallet_data) / len(pallet_data)
            if pallet_data else 0
        )

        html = template.render(
            top_pallets=top_pallets,
            top_hardware=top_hardware,
            pallet_categories=pallet_categories,
            hardware_categories=hardware_categories,
            total_pallets=len(pallet_data),
            total_hardware=len(itad_data),
            total_msrp=total_msrp,
            total_bid_value=total_bid_value,
            avg_spread_pct=avg_spread_pct,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            base_url=self.base_url,
        )
        (self.output_dir / "index.html").write_text(html, encoding="utf-8")

    def _generate_pallet_pages(self, pallet_data: list[dict[str, Any]]) -> int:
        template = self.env.get_template("pallet_listing.html")
        count = 0

        # Pre-compute category stats for unique per-page analytics
        cat_stats: dict[str, dict[str, Any]] = {}
        for p in pallet_data:
            cat = p.get("category", "general")
            cat_stats.setdefault(cat, {"spreads": [], "msrps": [], "bids": [], "cpus": []})
            cat_stats[cat]["spreads"].append(p.get("spread", 0))
            cat_stats[cat]["msrps"].append(p.get("total_msrp", 0))
            cat_stats[cat]["bids"].append(p.get("current_bid", 0))
            cat_stats[cat]["cpus"].append(p.get("cost_per_unit", 0))

        for listing in pallet_data:
            summary = self.summarizer.summarize_pallet(listing)
            slug = self._slugify(listing.get("auction_id", f"pallet-{count}"))
            cat = listing.get("category", "general")

            # Unique per-page category analytics
            cs = cat_stats.get(cat, {"spreads": [0], "msrps": [0], "bids": [0], "cpus": [0]})
            spread_rank = sorted(cs["spreads"], reverse=True).index(listing.get("spread", 0)) + 1
            avg_cat_spread = sum(cs["spreads"]) / len(cs["spreads"]) if cs["spreads"] else 0
            median_cpu = sorted(cs["cpus"])[len(cs["cpus"]) // 2] if cs["cpus"] else 0
            total_cat_value = sum(cs["msrps"])

            page_analytics = {
                "spread_rank": spread_rank,
                "total_in_category": len(cs["spreads"]),
                "spread_percentile": round((1 - spread_rank / max(len(cs["spreads"]), 1)) * 100, 1),
                "avg_category_spread": round(avg_cat_spread, 2),
                "median_category_cpu": round(median_cpu, 2),
                "total_category_msrp": round(total_cat_value, 2),
                "spread_vs_avg": round(listing.get("spread", 0) - avg_cat_spread, 2),
                "cpu_vs_median": round(listing.get("cost_per_unit", 0) - median_cpu, 2),
            }

            # Different similar listings per page using spread-proximity sorting
            same_cat = [
                p for p in pallet_data
                if p.get("category") == cat
                and p.get("auction_id") != listing.get("auction_id")
            ]
            same_cat.sort(key=lambda p: abs(p.get("spread", 0) - listing.get("spread", 0)))
            similar = same_cat[:5]

            html = template.render(
                listing=listing,
                summary=summary,
                similar_listings=similar,
                analytics=page_analytics,
                base_url=self.base_url,
                generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            )

            filepath = self.output_dir / "pallets" / f"{slug}.html"
            filepath.write_text(html, encoding="utf-8")
            count += 1

        return count

    def _generate_itad_pages(self, itad_data: list[dict[str, Any]]) -> int:
        template = self.env.get_template("itad_listing.html")
        count = 0

        for record in itad_data:
            summary = self.summarizer.summarize_hardware(record)
            slug = record.get("slug", self._slugify(record["model"]))

            # Find related hardware for comparison
            same_type = [
                h for h in itad_data
                if h.get("component_type") == record.get("component_type")
                and h.get("model") != record.get("model")
            ][:8]

            html = template.render(
                record=record,
                summary=summary,
                related_hardware=same_type,
                base_url=self.base_url,
                generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            )

            filepath = self.output_dir / "hardware" / f"{slug}.html"
            filepath.write_text(html, encoding="utf-8")
            count += 1

        return count

    def _generate_category_indexes(
        self,
        pallet_data: list[dict[str, Any]],
        itad_data: list[dict[str, Any]],
    ) -> int:
        index_template = self.env.get_template("pallet_index.html")
        itad_index_template = self.env.get_template("itad_index.html")
        count = 0

        # Pallet category indexes
        pallet_cats: dict[str, list] = {}
        for item in pallet_data:
            cat = item.get("category", "general")
            pallet_cats.setdefault(cat, []).append(item)

        for cat, items in pallet_cats.items():
            items_sorted = sorted(items, key=lambda x: x.get("spread", 0), reverse=True)
            avg_spread = sum(i.get("spread", 0) for i in items) / len(items) if items else 0
            total_value = sum(i.get("total_msrp", 0) for i in items)

            html = index_template.render(
                category=cat,
                listings=items_sorted,
                total_listings=len(items),
                avg_spread=avg_spread,
                total_value=total_value,
                base_url=self.base_url,
                generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            )
            filepath = self.output_dir / "category" / f"pallets-{self._slugify(cat)}.html"
            filepath.write_text(html, encoding="utf-8")
            count += 1

        # ITAD category indexes
        itad_cats: dict[str, list] = {}
        for item in itad_data:
            cat = item.get("component_type", "other")
            itad_cats.setdefault(cat, []).append(item)

        for cat, items in itad_cats.items():
            items_sorted = sorted(items, key=lambda x: x.get("avg_market_price", 0), reverse=True)
            avg_price = sum(i.get("avg_market_price", 0) for i in items) / len(items) if items else 0

            html = itad_index_template.render(
                category=cat,
                hardware_items=items_sorted,
                total_items=len(items),
                avg_price=avg_price,
                base_url=self.base_url,
                generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            )
            filepath = self.output_dir / "category" / f"hardware-{self._slugify(cat)}.html"
            filepath.write_text(html, encoding="utf-8")
            count += 1

        return count

    def _generate_sitemap(self) -> None:
        """Generate sitemap.xml for search engine indexing."""
        pages: list[str] = []
        for html_file in self.output_dir.rglob("*.html"):
            rel_path = html_file.relative_to(self.output_dir)
            pages.append(str(rel_path))

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        sitemap_entries = []
        for page in sorted(pages):
            priority = "1.0" if page == "index.html" else "0.8"
            freq = "daily" if "index" in page else "daily"
            sitemap_entries.append(
                f"  <url>\n"
                f"    <loc>{self.base_url}/{page}</loc>\n"
                f"    <lastmod>{now}</lastmod>\n"
                f"    <changefreq>{freq}</changefreq>\n"
                f"    <priority>{priority}</priority>\n"
                f"  </url>"
            )

        sitemap = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(sitemap_entries)
            + "\n</urlset>"
        )
        (self.output_dir / "sitemap.xml").write_text(sitemap, encoding="utf-8")

        # Also generate a JSON API endpoint with summary data
        api_data = {
            "total_pages": len(pages),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "categories": list(set(
                str(Path(p).parent) for p in pages if str(Path(p).parent) != "."
            )),
        }
        (self.output_dir / "api" / "stats.json").write_text(
            json.dumps(api_data, indent=2), encoding="utf-8"
        )

    def _copy_static_assets(self) -> None:
        """Copy any static assets (CSS, images) to the output directory."""
        static_dir = self.template_dir / "static"
        if static_dir.exists():
            shutil.copytree(static_dir, self.output_dir / "static", dirs_exist_ok=True)

    @staticmethod
    def _slugify(text: str) -> str:
        import re
        slug = text.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        return slug.strip("-")[:80]

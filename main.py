"""SurplusIndex CLI — Automated liquidation price tracker and static site generator.

Usage:
    python main.py scrape       # Run scrapers (or generate demo data)
    python main.py generate     # Generate static site from data
    python main.py build        # Full pipeline: scrape + generate + check similarity
    python main.py check        # Run similarity check on generated pages
    python main.py demo         # Generate demo data and build site
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
import pandas as pd

from generators.similarity_checker import SimilarityChecker
from generators.site_generator import SiteGenerator
from scrapers.demo_data import generate_demo_itad, generate_demo_pallets
from scrapers.itad_scraper import ITADScraper
from scrapers.pallet_scraper import PalletScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("surplusindex")

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(exist_ok=True)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def cli(verbose: bool) -> None:
    """SurplusIndex — Automated Liquidation Price Tracker"""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--demo", is_flag=True, help="Use demo/synthetic data instead of live scraping")
@click.option("--pallet-count", default=200, help="Number of demo pallet listings")
@click.option("--itad-count", default=None, type=int, help="Number of demo ITAD records (all if not set)")
def scrape(demo: bool, pallet_count: int, itad_count: int | None) -> None:
    """Run data scrapers or generate demo data."""
    ensure_data_dir()

    if demo:
        logger.info("Generating demo data...")
        pallets = generate_demo_pallets(pallet_count)
        itad = generate_demo_itad(itad_count)
    else:
        logger.info("Running live scrapers...")
        pallet_scraper = PalletScraper()
        itad_scraper = ITADScraper()

        pallets = pallet_scraper.scrape()
        itad = itad_scraper.scrape()

        if not pallets:
            logger.warning("No pallet data from live scraping; falling back to demo data")
            pallets = generate_demo_pallets(pallet_count)
        if not itad:
            logger.warning("No ITAD data from live scraping; falling back to demo data")
            itad = generate_demo_itad(itad_count)

    # Save to CSV
    pallet_df = pd.DataFrame(pallets)
    itad_df = pd.DataFrame(itad)

    pallet_df.to_csv(DATA_DIR / "pallets.csv", index=False)
    itad_df.to_csv(DATA_DIR / "itad.csv", index=False)

    # Also save as JSON for the API
    (DATA_DIR / "pallets.json").write_text(json.dumps(pallets, indent=2, default=str))
    (DATA_DIR / "itad.json").write_text(json.dumps(itad, indent=2, default=str))

    logger.info("Saved %d pallet listings and %d ITAD records", len(pallets), len(itad))


@cli.command()
@click.option("--base-url", default="", help="Base URL for the generated site")
def generate(base_url: str) -> None:
    """Generate static site from scraped data."""
    pallet_file = DATA_DIR / "pallets.json"
    itad_file = DATA_DIR / "itad.json"

    if not pallet_file.exists() or not itad_file.exists():
        logger.error("No data files found. Run 'scrape' first.")
        sys.exit(1)

    pallets = json.loads(pallet_file.read_text())
    itad = json.loads(itad_file.read_text())

    logger.info("Generating site from %d pallets and %d hardware records...", len(pallets), len(itad))

    generator = SiteGenerator(
        template_dir="templates",
        output_dir=str(OUTPUT_DIR),
        base_url=base_url,
    )
    stats = generator.generate(pallets, itad)

    logger.info("Generation complete!")
    logger.info("  Pages generated: %d", stats["pages_generated"])
    logger.info("  Pallet pages: %d", stats["pallet_pages"])
    logger.info("  ITAD pages: %d", stats["itad_pages"])
    logger.info("  Index pages: %d", stats["index_pages"])


@cli.command()
@click.option("--sample-size", default=100, help="Number of pages to sample for comparison")
def check(sample_size: int) -> None:
    """Run cosine similarity check on generated pages."""
    if not OUTPUT_DIR.exists():
        logger.error("No output directory found. Run 'generate' first.")
        sys.exit(1)

    checker = SimilarityChecker()
    result = checker.check_pages(str(OUTPUT_DIR), sample_size=sample_size)

    logger.info("Similarity Check Results:")
    logger.info("  Pages checked: %d", result["sample_size"])
    logger.info("  Pairs compared: %d", result["pairs_checked"])
    logger.info("  Avg similarity: %.2f%%", result["avg_similarity"] * 100)
    logger.info("  Max similarity: %.2f%%", result["max_similarity"] * 100)
    logger.info("  Threshold: %.0f%%", result["threshold"] * 100)
    logger.info("  Violations: %d", result["total_violations"])
    logger.info("  PASSED: %s", result["passed"])

    if not result["passed"]:
        logger.error("FAIL: %d page pairs exceed the similarity threshold", result["total_violations"])
        for v in result["violations"][:5]:
            logger.error("  %s <-> %s: %.2f%%", v["page_a"], v["page_b"], v["similarity"] * 100)
        raise click.ClickException("similarity check failed")


@cli.command()
@click.option("--base-url", default="", help="Base URL for the generated site")
@click.option("--pallet-count", default=200, help="Number of demo pallet listings")
def build(base_url: str, pallet_count: int) -> None:
    """Full pipeline: generate demo data + build site + run similarity check."""
    ensure_data_dir()

    # Step 1: Generate data
    logger.info("Step 1: Generating demo data...")
    pallets = generate_demo_pallets(pallet_count)
    itad = generate_demo_itad()

    pallet_df = pd.DataFrame(pallets)
    itad_df = pd.DataFrame(itad)
    pallet_df.to_csv(DATA_DIR / "pallets.csv", index=False)
    itad_df.to_csv(DATA_DIR / "itad.csv", index=False)
    (DATA_DIR / "pallets.json").write_text(json.dumps(pallets, indent=2, default=str))
    (DATA_DIR / "itad.json").write_text(json.dumps(itad, indent=2, default=str))
    logger.info("  Generated %d pallets + %d hardware records", len(pallets), len(itad))

    # Step 2: Generate site
    logger.info("Step 2: Generating static site...")
    generator = SiteGenerator(
        template_dir="templates",
        output_dir=str(OUTPUT_DIR),
        base_url=base_url,
    )
    stats = generator.generate(pallets, itad)
    logger.info("  Generated %d pages", stats["pages_generated"])

    # Step 3: Similarity check
    logger.info("Step 3: Running similarity check...")
    checker = SimilarityChecker()
    result = checker.check_pages(str(OUTPUT_DIR), sample_size=80)
    logger.info("  Avg similarity: %.2f%% | Max: %.2f%% | Threshold: %.0f%%",
                result["avg_similarity"] * 100,
                result["max_similarity"] * 100,
                result["threshold"] * 100)

    # Write build report
    report = {
        "build_time": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "similarity": result,
    }
    (OUTPUT_DIR / "api" / "build-report.json").write_text(
        json.dumps(report, indent=2, default=str)
    )

    if not result["passed"]:
        logger.error("BUILD FAILED — %d page pairs exceed similarity threshold", result["total_violations"])
        raise click.ClickException("similarity check failed")

    logger.info("BUILD SUCCESSFUL — All pages pass similarity check")


@cli.command()
def demo() -> None:
    """Quick demo: generate data and build site with defaults."""
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(build, ["--pallet-count", "200"])
    if result.output:
        click.echo(result.output)


if __name__ == "__main__":
    cli()

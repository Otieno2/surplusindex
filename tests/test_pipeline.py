from pathlib import Path

from bs4 import BeautifulSoup

from generators.similarity_checker import SimilarityChecker
from generators.site_generator import SiteGenerator
from scrapers.itad_scraper import ITADScraper
from scrapers.pallet_scraper import PalletScraper


def test_live_itad_record_renders_without_demo_only_fields(tmp_path: Path) -> None:
    scraper = ITADScraper(delay_range=(0, 0))
    scraper.fetch_page = lambda url: BeautifulSoup('<div class="price">$1200</div>', "lxml")

    record = scraper._scrape_model("Dell PowerEdge R740", "servers")
    assert record is not None
    assert {"new_msrp", "depreciation_pct", "active_listings", "price_history"} <= record.keys()

    SiteGenerator(output_dir=str(tmp_path)).generate([], [record])
    assert (tmp_path / "hardware" / "dell-poweredge-r740.html").exists()


def test_pallet_source_url_uses_card_link() -> None:
    scraper = PalletScraper(delay_range=(0, 0))
    card = BeautifulSoup(
        '<div><h3>Lot</h3><span class="msrp">$1000</span>'
        '<span class="bid">$100</span><a href="/auction/A1">Details</a></div>',
        "lxml",
    ).div

    listing = scraper._extract_listing_data(card, "Liquidation.com", "https://liquidation.com")
    assert listing is not None
    assert listing["source_url"] == "https://liquidation.com/auction/A1"


def test_template_slug_matches_generated_filename(tmp_path: Path) -> None:
    listing = {
        "auction_id": "A/1?x",
        "title": "Lot",
        "category": "general merchandise",
        "platform": "Example",
        "condition": "New",
        "total_msrp": 100.0,
        "current_bid": 10.0,
        "spread": 90.0,
        "spread_pct": 90.0,
        "number_of_items": 1,
        "cost_per_unit": 10.0,
        "hours_remaining": 1,
        "num_bids": 0,
        "source_url": "https://example.test/auction/A1",
    }
    SiteGenerator(output_dir=str(tmp_path)).generate([listing], [])

    detail = (tmp_path / "pallets" / "a-1-x.html").read_text()
    assert "/pallets/a-1-x.html" in detail
    assert "/category/pallets-general-merchandise.html" in detail


def test_similarity_sampling_is_deterministic(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f"{i}.html").write_text(f"<main>Unique page content {i} with enough words to inspect.</main>")

    checker = SimilarityChecker()
    first = checker.check_pages(str(tmp_path), sample_size=3)
    second = checker.check_pages(str(tmp_path), sample_size=3)
    assert first == second


def test_similarity_checker_marks_violations_as_failed(tmp_path: Path) -> None:
    content = "<main>Same page content repeated enough words for similarity checking.</main>"
    (tmp_path / "a.html").write_text(content)
    (tmp_path / "b.html").write_text(content)

    result = SimilarityChecker(max_similarity=0.4).check_pages(str(tmp_path))
    assert result["total_violations"] == 1
    assert result["passed"] is False

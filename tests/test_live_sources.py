from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from scrapers.itad_scraper import ITADScraper
from scrapers.pallet_scraper import PalletScraper


def test_current_liquidation_page_parser_extracts_live_card() -> None:
    html = """
    <a href="/auction/view?id=123">Laptops, 100 Units, MSRP $85,065</a>
    <div>Closing: Today</div><div>Returns | 1 Pallet | 100 Items</div>
    <div>Current Bid: $1,400.00 (0 Bids)</div><div>Est. Retail: $85,065.00</div>
    """
    soup = BeautifulSoup(html, "lxml")
    cards = PalletScraper._find_liquidation_cards(soup)
    assert len(cards) == 1
    scraper = PalletScraper(delay_range=(0, 0))
    listing = scraper._extract_listing_data(cards[0], "Liquidation.com", "https://www.liquidation.com")
    assert listing is not None
    assert listing["current_bid"] == 1400.0
    assert listing["total_msrp"] == 85065.0
    assert listing["source_url"].endswith("/auction/view?id=123")


def test_gsa_api_payload_is_normalized() -> None:
    scraper = PalletScraper(delay_range=(0, 0))
    response = Mock()
    response.json.return_value = {
        "results": [{
            "SaleNo": "A1",
            "LotNo": 7,
            "ItemName": "Dell servers and switches",
            "HighBidAmount": "$250.00",
            "BiddersCount": 2,
            "LotInfo": [{"LotSequence": 1}],
            "ItemDescURL": "https://gsaauctions.gov/item/A1/7",
        }]
    }
    response.raise_for_status.return_value = None
    with patch.object(scraper.session, "get", return_value=response):
        records = scraper._fetch_gsa("/assets/gsaauctions/v2/auctions")
    assert records[0]["auction_id"] == "GSA-A1-7"
    assert records[0]["current_bid"] == 250.0
    assert records[0]["source_url"].endswith("A1/7")


def test_ebay_browse_results_are_used_when_credentials_exist(monkeypatch) -> None:
    monkeypatch.setenv("EBAY_CLIENT_ID", "client")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "secret")
    scraper = ITADScraper(delay_range=(0, 0))
    token_response = Mock()
    token_response.json.return_value = {"access_token": "token"}
    token_response.raise_for_status.return_value = None
    search_response = Mock()
    search_response.json.return_value = {
        "itemSummaries": [{"price": {"value": "125.50"}}, {"price": {"value": "200"}}]
    }
    search_response.raise_for_status.return_value = None
    with patch.object(scraper.session, "post", return_value=token_response), patch.object(
        scraper.session, "get", return_value=search_response
    ):
        assert scraper._search_ebay("Dell PowerEdge R740") == [125.5, 200.0]

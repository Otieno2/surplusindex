# SurplusIndex

**Automated liquidation price tracker and IT hardware market index.**

Live data dashboard that tracks pallet auction spreads across Liquidation.com, B-Stock, and DirectLiquidation — plus a "Blue Book" pricing index for used enterprise IT hardware.

## Architecture

```
surplusindex/
├── scrapers/                # Data collection (BeautifulSoup + Playwright)
│   ├── base_scraper.py      # Abstract base with rate-limiting & anti-detection
│   ├── pallet_scraper.py    # Track 1: Liquidation pallet auctions
│   ├── itad_scraper.py      # Track 2: IT hardware pricing ("Blue Book")
│   └── demo_data.py         # Realistic synthetic data generator
├── generators/              # Static site generation
│   ├── site_generator.py    # Jinja2 → 500+ static HTML pages
│   ├── llm_summarizer.py    # Minimal text (15% page weight, data-anchored)
│   └── similarity_checker.py # Cosine similarity < 40% enforcement
├── templates/               # Tailwind CSS dashboard-style templates
│   ├── base.html            # Base layout with Chart.js + sortable tables
│   ├── index.html           # Homepage dashboard
│   ├── pallet_listing.html  # Individual pallet auction page
│   ├── itad_listing.html    # Individual hardware price page
│   ├── pallet_index.html    # Pallet category index
│   └── itad_index.html      # Hardware category index
├── .github/workflows/
│   └── daily_build.yml      # Daily automated scrape → build → deploy
├── main.py                  # CLI entry point
└── data/                    # Scraped data (CSV + JSON)
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Generate demo data and build the site
python main.py build

# Or step by step:
python main.py scrape --demo          # Generate demo data
python main.py generate               # Build static HTML pages
python main.py check                  # Verify similarity < 40%

# Serve locally
cd output && python -m http.server 8000
```

## Content Strategy: Data-to-LLM Ratio

Each page is weighted to survive Google's March 2026 spam classifiers:

| Content Type | Target Weight | Implementation |
|---|---|---|
| Structured numerical data | 55% | Sortable tables, price charts, spread calculations |
| Template chrome | 30% | Navigation, layout, Chart.js visualizations |
| LLM-generated text | 15% | 2-3 sentence data-anchored summaries only |

### Anti-Duplicate Measures

- **Cosine similarity checker** ensures no two pages exceed 40% similarity
- **Deterministic randomization** varies summary phrasing per page using content-based seeds
- **Unique data per page** — each page features different comparison sets, charts, and metrics

## Tracks

### Track 1: Pallet Tracker

Calculates the "Liquidation Spread" (MSRP − Current Bid) for active pallet auctions.

**Metrics per listing:**
- Total MSRP vs. current bid
- Spread (absolute $ and %)
- Cost per unit
- Time remaining
- Condition classification

### Track 2: ITAD Hardware Blue Book

Enterprise IT hardware pricing index — the "Kelly Blue Book" for used servers, networking gear, GPUs, memory, and more.

**Metrics per model:**
- Average used market price
- New MSRP comparison
- Depreciation percentage
- 6-month price history
- Market demand rating
- Price across refurbished / bulk / retail channels

## Monetization Matrix

| Type | Network | Trigger |
|---|---|---|
| Auction Referrals | Liquidation.com Affiliate | "Bid Now" tracking links |
| Wholesale Sourcing | Faire Wholesale | Business signup ($250/referral) |
| B2B Financing | National Business Capital (CJ) | Funded loan referrals |
| Hardware Components | eBay Partner Network (EPN) | Active listing affiliate links |
| Cloud Migration | PartnerStack / CJ Affiliate | Enterprise SaaS referrals |
| Freight Shipping | ShareASale | Heavy equipment shipping referrals |

## Deployment

### GitHub Pages (Free)

The GitHub Actions workflow runs daily at 3:00 AM UTC:

1. Runs Python scrapers to fetch fresh prices
2. Generates 200+ static HTML pages
3. Runs cosine similarity verification
4. Deploys to GitHub Pages

### Manual Trigger

You can trigger a build manually from the Actions tab with options for demo data and pallet count.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | No | For LLM-generated summaries (falls back to templates) |

## License

MIT

## Live scraper sources

The live scraper uses current public source paths. Pallet data comes from Liquidation.com, Direct Liquidation, and the documented GSA Auctions API. ITAD pricing uses the official eBay Browse API when `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` are set, with public HTML sources as additional fallbacks.

Install the Playwright browser before live runs:

```bash
python -m playwright install chromium
```

Optional credentials are read from `GSA_API_KEY`, `EBAY_CLIENT_ID`, and `EBAY_CLIENT_SECRET`. The browser fallback renders public JavaScript pages when a normal request is blocked or incomplete; it does not solve CAPTCHAs, defeat authentication, or evade access controls.

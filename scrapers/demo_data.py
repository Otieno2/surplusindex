"""Generate realistic demo/seed data for development and initial site population.

This creates synthetic data modeled after real liquidation auctions and IT hardware
pricing. Used during development and as seed data before live scrapers are activated.
"""

import random
from datetime import datetime, timedelta, timezone
from typing import Any


def generate_demo_pallets(count: int = 200) -> list[dict[str, Any]]:
    """Generate realistic pallet auction listings."""
    categories = {
        "consumer-electronics": {
            "items": [
                "Assorted Apple Products (MacBooks, iPads, AirPods)",
                "Mixed Lot Samsung Galaxy Phones & Tablets",
                "Amazon Customer Returns - Electronics",
                "Walmart Overstock - Bluetooth Speakers & Headphones",
                "Target Shelf-Pull - Smart Home Devices",
                "Mixed Lot Gaming Consoles & Accessories",
                "Assorted Laptops (Dell, HP, Lenovo)",
                "Customer Returns - Wireless Earbuds & Headphones",
                "Overstock - 4K Smart TVs (Various Sizes)",
                "Mixed Lot Tablets (iPad, Samsung, Amazon Fire)",
            ],
            "msrp_range": (3000, 45000),
            "item_count_range": (10, 150),
        },
        "computers-networking": {
            "items": [
                "Lot of Dell OptiPlex Desktop Computers",
                "Cisco Networking Equipment Pallet",
                "HP ProBook & EliteBook Laptop Lot",
                "Mixed Enterprise Switches & Routers",
                "Lenovo ThinkPad Lot - Various Models",
                "Server Components - RAM, CPUs, HDDs",
                "Mixed Lot Monitors (Dell, HP, LG)",
                "Ubiquiti & Netgear Networking Gear",
                "Enterprise UPS Systems Pallet",
                "Mixed Lot Printers & Scanners",
            ],
            "msrp_range": (5000, 60000),
            "item_count_range": (5, 80),
        },
        "home-garden": {
            "items": [
                "Dyson Vacuum & Air Purifier Returns",
                "Kitchen Appliance Lot (KitchenAid, Cuisinart)",
                "Smart Home Bundle - Nest, Ring, Ecobee",
                "Outdoor Furniture Pallet - Patio Sets",
                "Mixed Lot Power Tools (DeWalt, Milwaukee)",
                "Robot Vacuum Lot (Roomba, Roborock, Shark)",
                "Premium Cookware Set Overstock",
                "Mixed Lot Small Kitchen Appliances",
                "Home Security Camera Systems",
                "Lighting Fixtures & Smart Bulbs Lot",
            ],
            "msrp_range": (2000, 25000),
            "item_count_range": (8, 60),
        },
        "apparel": {
            "items": [
                "Designer Brand Clothing Lot (Nike, Adidas)",
                "Amazon Fashion Returns - Mixed Apparel",
                "Premium Footwear Pallet (Nike, New Balance)",
                "Target Clearance - Seasonal Clothing",
                "Mixed Lot Luxury Handbags & Accessories",
                "Activewear Lot (Lululemon, Under Armour)",
                "Children's Clothing Overstock",
                "Men's Dress Shirts & Business Attire",
                "Winter Jacket & Outerwear Lot",
                "Mixed Jewelry & Watches Pallet",
            ],
            "msrp_range": (5000, 35000),
            "item_count_range": (50, 500),
        },
        "general-merchandise": {
            "items": [
                "Amazon Warehouse Deals - Mixed General",
                "Walmart Liquidation - Toys & Games",
                "Target Overstock - Home Decor",
                "Mixed Lot Office Supplies & Furniture",
                "Pet Supplies Pallet (Food, Toys, Beds)",
                "Baby & Toddler Products Lot",
                "Sports & Fitness Equipment Pallet",
                "Mixed Lot Books, Media & Entertainment",
                "Health & Beauty Products Overstock",
                "Automotive Parts & Accessories Lot",
            ],
            "msrp_range": (2000, 20000),
            "item_count_range": (20, 200),
        },
    }

    platforms = ["Liquidation.com", "DirectLiquidation", "B-Stock"]
    conditions = ["New", "Like New", "Refurbished", "Mixed Condition", "Shelf-Pull", "Customer Returns"]

    listings: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for i in range(count):
        category = random.choice(list(categories.keys()))
        cat_config = categories[category]
        title = random.choice(cat_config["items"])
        platform = random.choice(platforms)

        msrp = round(random.uniform(*cat_config["msrp_range"]), 2)
        bid_ratio = random.uniform(0.05, 0.35)
        current_bid = round(msrp * bid_ratio, 2)
        num_items = random.randint(*cat_config["item_count_range"])
        end_time = now + timedelta(hours=random.randint(1, 72))

        spread = round(msrp - current_bid, 2)
        cost_per_unit = round(current_bid / num_items, 2) if num_items > 0 else 0.0

        listings.append({
            "auction_id": f"{platform[:3].upper()}-{100000 + i}",
            "title": f"{title} - Lot #{i + 1}",
            "platform": platform,
            "category": category,
            "condition": random.choice(conditions),
            "total_msrp": msrp,
            "current_bid": current_bid,
            "spread": spread,
            "spread_pct": round((spread / msrp) * 100, 1) if msrp > 0 else 0.0,
            "number_of_items": num_items,
            "cost_per_unit": cost_per_unit,
            "end_time": end_time.isoformat(),
            "hours_remaining": round((end_time - now).total_seconds() / 3600, 1),
            "num_bids": random.randint(0, 25),
            "scraped_at": now.isoformat(),
            "source_url": f"https://example.com/auction/{100000 + i}",
        })

    return sorted(listings, key=lambda x: x["spread"], reverse=True)


def generate_demo_itad(count: int | None = None) -> list[dict[str, Any]]:
    """Generate realistic IT hardware pricing data."""
    hardware_data = [
        # Servers
        {"model": "Dell PowerEdge R740", "type": "servers", "new_msrp": 12000, "used_range": (2800, 5500)},
        {"model": "Dell PowerEdge R640", "type": "servers", "new_msrp": 9500, "used_range": (2200, 4200)},
        {"model": "Dell PowerEdge R750", "type": "servers", "new_msrp": 15000, "used_range": (5500, 9000)},
        {"model": "Dell PowerEdge R650", "type": "servers", "new_msrp": 11000, "used_range": (4000, 7000)},
        {"model": "HP ProLiant DL380 Gen10", "type": "servers", "new_msrp": 10500, "used_range": (2500, 5000)},
        {"model": "HP ProLiant DL360 Gen10", "type": "servers", "new_msrp": 8500, "used_range": (2000, 4000)},
        {"model": "HP ProLiant DL380 Gen11", "type": "servers", "new_msrp": 16000, "used_range": (7000, 11000)},
        {"model": "Lenovo ThinkSystem SR650", "type": "servers", "new_msrp": 9800, "used_range": (2400, 4800)},
        {"model": "Lenovo ThinkSystem SR630", "type": "servers", "new_msrp": 7500, "used_range": (1800, 3500)},
        {"model": "Cisco UCS C220 M5", "type": "servers", "new_msrp": 8000, "used_range": (1500, 3200)},
        # Networking
        {"model": "Cisco Catalyst 9300-48P", "type": "networking", "new_msrp": 8500, "used_range": (2200, 4500)},
        {"model": "Cisco Catalyst 9200-48P", "type": "networking", "new_msrp": 5500, "used_range": (1500, 3000)},
        {"model": "Cisco Nexus 9336C-FX2", "type": "networking", "new_msrp": 25000, "used_range": (8000, 15000)},
        {"model": "Cisco ISR 4431", "type": "networking", "new_msrp": 12000, "used_range": (2800, 5500)},
        {"model": "Juniper EX4300-48T", "type": "networking", "new_msrp": 6000, "used_range": (1200, 2800)},
        {"model": "Arista 7050X3-48YC8", "type": "networking", "new_msrp": 18000, "used_range": (5000, 10000)},
        {"model": "HP Aruba 2930F-48G", "type": "networking", "new_msrp": 3500, "used_range": (800, 1800)},
        {"model": "Meraki MS250-48FP", "type": "networking", "new_msrp": 9000, "used_range": (2500, 5000)},
        {"model": "Fortinet FortiGate 60F", "type": "networking", "new_msrp": 1200, "used_range": (400, 800)},
        {"model": "Ubiquiti USW-Pro-48-POE", "type": "networking", "new_msrp": 800, "used_range": (350, 600)},
        # Storage
        {"model": "Dell EMC PowerStore 1200T", "type": "storage", "new_msrp": 45000, "used_range": (12000, 25000)},
        {"model": "NetApp FAS2750", "type": "storage", "new_msrp": 20000, "used_range": (4000, 9000)},
        {"model": "HPE MSA 2060", "type": "storage", "new_msrp": 8000, "used_range": (2000, 4500)},
        {"model": "Synology RS1221+", "type": "storage", "new_msrp": 1200, "used_range": (600, 900)},
        {"model": "QNAP TS-873A-8G", "type": "storage", "new_msrp": 1000, "used_range": (500, 800)},
        # Memory
        {"model": "DDR4 32GB ECC RDIMM 2666MHz", "type": "memory", "new_msrp": 180, "used_range": (45, 90)},
        {"model": "DDR4 64GB ECC RDIMM 2933MHz", "type": "memory", "new_msrp": 350, "used_range": (95, 180)},
        {"model": "DDR4 16GB ECC RDIMM 2400MHz", "type": "memory", "new_msrp": 95, "used_range": (18, 40)},
        {"model": "DDR5 32GB ECC RDIMM 4800MHz", "type": "memory", "new_msrp": 250, "used_range": (120, 200)},
        {"model": "DDR4 32GB SODIMM 3200MHz", "type": "memory", "new_msrp": 120, "used_range": (50, 85)},
        {"model": "DDR4 16GB Desktop 3200MHz", "type": "memory", "new_msrp": 55, "used_range": (20, 38)},
        {"model": "DDR4 8GB Desktop 2666MHz", "type": "memory", "new_msrp": 30, "used_range": (8, 18)},
        {"model": "DDR3 8GB Desktop 1600MHz", "type": "memory", "new_msrp": 35, "used_range": (6, 14)},
        {"model": "DDR3 4GB Desktop 1333MHz", "type": "memory", "new_msrp": 20, "used_range": (3, 8)},
        # Processors
        {"model": "Intel Xeon Gold 6248 (20C/40T)", "type": "processors", "new_msrp": 3000, "used_range": (400, 900)},
        {"model": "Intel Xeon Gold 6258R (28C/56T)", "type": "processors", "new_msrp": 3950, "used_range": (600, 1200)},
        {"model": "Intel Xeon Silver 4214 (12C/24T)", "type": "processors", "new_msrp": 700, "used_range": (120, 280)},
        {
            "model": "Intel Xeon Platinum 8280 (28C/56T)",
            "type": "processors", "new_msrp": 10000, "used_range": (1500, 3500),
        },
        {"model": "AMD EPYC 7742 (64C/128T)", "type": "processors", "new_msrp": 6950, "used_range": (1800, 3800)},
        {"model": "AMD EPYC 7763 (64C/128T)", "type": "processors", "new_msrp": 7890, "used_range": (2500, 5000)},
        # GPUs
        {"model": "NVIDIA Tesla V100 32GB", "type": "gpus", "new_msrp": 10000, "used_range": (2000, 4500)},
        {"model": "NVIDIA A100 40GB PCIe", "type": "gpus", "new_msrp": 11000, "used_range": (5000, 8000)},
        {"model": "NVIDIA A100 80GB SXM", "type": "gpus", "new_msrp": 15000, "used_range": (7000, 11000)},
        {"model": "NVIDIA RTX A6000 48GB", "type": "gpus", "new_msrp": 4650, "used_range": (2200, 3500)},
        {"model": "NVIDIA T4 16GB", "type": "gpus", "new_msrp": 2200, "used_range": (700, 1400)},
        {"model": "NVIDIA RTX 4090 24GB", "type": "gpus", "new_msrp": 1600, "used_range": (1100, 1450)},
        {"model": "NVIDIA RTX 3090 24GB", "type": "gpus", "new_msrp": 1500, "used_range": (650, 950)},
        # Workstations
        {"model": "Dell Precision 5820 Tower", "type": "workstations", "new_msrp": 4500, "used_range": (800, 2000)},
        {"model": "Dell Precision 7920 Tower", "type": "workstations", "new_msrp": 8000, "used_range": (1500, 3500)},
        {"model": "HP Z6 G4 Workstation", "type": "workstations", "new_msrp": 5500, "used_range": (1000, 2500)},
        {"model": "HP Z8 G4 Workstation", "type": "workstations", "new_msrp": 9000, "used_range": (2000, 4500)},
        {"model": "Lenovo ThinkStation P520", "type": "workstations", "new_msrp": 3800, "used_range": (700, 1800)},
    ]

    now = datetime.now(timezone.utc)
    records: list[dict[str, Any]] = []

    data_to_process = hardware_data[:count] if count else hardware_data

    for item in data_to_process:
        used_min, used_max = item["used_range"]
        avg_price = round(random.uniform(used_min, used_max), 2)
        min_price = round(used_min * random.uniform(0.85, 1.0), 2)
        max_price = round(used_max * random.uniform(1.0, 1.15), 2)

        demand_categories = {"gpus", "memory", "processors", "networking"}
        base_demand = 3 if item["type"] in demand_categories else 2
        demand_score = base_demand + random.randint(0, 3)

        if demand_score >= 5:
            demand = "High"
        elif demand_score >= 4:
            demand = "Medium-High"
        elif demand_score >= 3:
            demand = "Medium"
        else:
            demand = "Low"

        depreciation = round((1 - avg_price / item["new_msrp"]) * 100, 1)
        price_history = []
        for month_offset in range(6):
            hist_date = now - timedelta(days=30 * month_offset)
            variation = random.uniform(-0.08, 0.08)
            hist_price = round(avg_price * (1 + variation), 2)
            price_history.append({
                "date": hist_date.strftime("%Y-%m"),
                "avg_price": hist_price,
            })

        records.append({
            "component_type": item["type"],
            "model": item["model"],
            "new_msrp": item["new_msrp"],
            "avg_market_price": avg_price,
            "min_price": min_price,
            "max_price": max_price,
            "refurbished_retail_price": round(max_price * 1.25, 2),
            "bulk_lot_avg_price_per_unit": round(min_price * 0.7, 2),
            "depreciation_pct": depreciation,
            "market_demand_rating": demand,
            "price_sources": random.randint(3, 8),
            "active_listings": random.randint(5, 45),
            "price_history": price_history,
            "last_updated": now.isoformat(),
            "slug": item["model"].lower().replace(" ", "-").replace("/", "-").replace("(", "").replace(")", ""),
        })

    return records

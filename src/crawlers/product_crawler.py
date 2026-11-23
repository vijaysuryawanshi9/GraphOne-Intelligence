
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import aiohttp


# --------------------------------------------------
# Paths
# --------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[2]

RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
LOG_DIR = ROOT_DIR / "logs"

for folder in [RAW_DIR, PROCESSED_DIR, LOG_DIR]:
    folder.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# Logging
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(
            LOG_DIR / "product_crawler.log",
            encoding="utf-8"
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# --------------------------------------------------
# Public catalog API
# --------------------------------------------------

BASE_URL = "https://submitmysaas.com"

START_URL = (
    "https://submitmysaas.com/api/public/products?page=1"
)


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def first_value(record, *keys):
    for key in keys:
        value = record.get(key)

        if value is not None and value != "":
            return value

    return None


def normalize_name(name):
    if not name:
        return ""

    return "".join(
        character.lower()
        for character in str(name)
        if character.isalnum()
    )


def normalize_product(record):
    name = first_value(
        record,
        "name",
        "title",
        "product_name"
    )

    if not name:
        return None

    product_url = first_value(
        record,
        "url",
        "product_url",
        "canonical_url",
        "slug_url"
    )

    if product_url and product_url.startswith("/"):
        product_url = urljoin(BASE_URL, product_url)

    slug = first_value(record, "slug")

    if not product_url and slug:
        product_url = urljoin(
            BASE_URL,
            f"/products/{slug}"
        )

    description = first_value(
        record,
        "description",
        "short_description",
        "tagline"
    )

    category = first_value(
        record,
        "category",
        "categories",
        "topic"
    )

    pricing = first_value(
        record,
        "pricing",
        "price",
        "pricing_model"
    )

    company = first_value(
        record,
        "company",
        "maker",
        "developer"
    )

    return {
        "product_id": (
            str(record.get("id"))
            if record.get("id") is not None
            else slug or normalize_name(name)
        ),
        "product_name": str(name).strip(),
        "description": description,
        "product_url": product_url,
        "category": category,
        "pricing": pricing,
        "company": company,
        "source_url": product_url or BASE_URL,
        "source_dataset": BASE_URL,
        "source_updated_at": datetime.now(
            timezone.utc
        ).isoformat()
    }


# --------------------------------------------------
# Fetch all pages
# --------------------------------------------------

async def fetch_products():

    logger.info("Starting product catalog download...")

    products = []
    next_url = START_URL
    page_number = 1

    timeout = aiohttp.ClientTimeout(total=90)

    headers = {
        "User-Agent": "GraphOneIntelligence/1.0"
    }

    async with aiohttp.ClientSession(
        timeout=timeout,
        headers=headers
    ) as session:

        while next_url:

            logger.info(
                "Fetching product page %s",
                page_number
            )

            async with session.get(next_url) as response:

                if response.status == 429:
                    retry_after = int(
                        response.headers.get(
                            "Retry-After", "5"
                        )
                    )

                    logger.warning(
                        "Rate limited. Waiting %s seconds",
                        retry_after
                    )

                    await asyncio.sleep(retry_after)
                    continue

                response.raise_for_status()
                data = await response.json(
                    content_type=None
                )

            if isinstance(data, list):
                page_records = data
                next_url = None

            elif isinstance(data, dict):

                page_records = (
                    data.get("products")
                    or data.get("data")
                    or data.get("results")
                    or []
                )

                next_url = data.get("next")

                if next_url:
                    next_url = urljoin(
                        BASE_URL,
                        next_url
                    )

            else:
                raise ValueError(
                    "Unexpected API response format"
                )

            products.extend(page_records)

            logger.info(
                "Page %s returned %s products",
                page_number,
                len(page_records)
            )

            page_number += 1

            if next_url:
                await asyncio.sleep(1)

    logger.info(
        "Total raw product records: %s",
        len(products)
    )

    return products


# --------------------------------------------------
# Clean and deduplicate
# --------------------------------------------------

def process_products(raw_products):

    logger.info("Normalizing product records...")

    cleaned = []
    seen = set()

    for record in raw_products:

        if not isinstance(record, dict):
            continue

        product = normalize_product(record)

        if not product:
            continue

        key = normalize_name(
            product["product_name"]
        )

        if not key or key in seen:
            continue

        seen.add(key)
        cleaned.append(product)

    logger.info(
        "Unique products: %s",
        len(cleaned)
    )

    return cleaned


# --------------------------------------------------
# Save
# --------------------------------------------------

def save_json(data, filepath):

    with open(
        filepath,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )

    logger.info("Saved: %s", filepath)


# --------------------------------------------------
# Main
# --------------------------------------------------

async def main():

    try:

        raw_products = await fetch_products()

        save_json(
            raw_products,
            RAW_DIR / "products_raw.json"
        )

        products = process_products(
            raw_products
        )

        save_json(
            products,
            PROCESSED_DIR / "products.json"
        )

        logger.info(
            "Product crawler completed."
        )

        logger.info(
            "Final product count: %s",
            len(products)
        )

        if len(products) >= 1000:
            logger.info(
                "Assignment requirement satisfied: "
                "1000+ products"
            )
        else:
            logger.warning(
                "Catalog returned fewer than 1000 "
                "unique products. We will add another "
                "verified source if required."
            )

    except Exception:
        logger.exception(
            "Product crawler failed."
        )


if __name__ == "__main__":
    asyncio.run(main())

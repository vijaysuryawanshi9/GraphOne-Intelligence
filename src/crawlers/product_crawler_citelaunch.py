
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import aiohttp


ROOT_DIR = Path(__file__).resolve().parents[2]

RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
LOG_DIR = ROOT_DIR / "logs"

for folder in [RAW_DIR, PROCESSED_DIR, LOG_DIR]:
    folder.mkdir(parents=True, exist_ok=True)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(
            LOG_DIR / "product_citelaunch_crawler.log",
            encoding="utf-8"
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

BASE_URL = "https://www.citelaunch.com"
START_URL = f"{BASE_URL}/api/public/products?page=1&limit=100"


def get_value(record, *keys):
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def normalize_name(name):
    if not name:
        return ""
    return "".join(
        ch.lower() for ch in str(name)
        if ch.isalnum()
    )


def normalize_product(record):
    name = get_value(
        record, "name", "title", "product_name"
    )

    if not name:
        return None

    canonical_url = get_value(
        record, "canonicalUrl", "canonical_url",
        "url", "product_url"
    )

    if canonical_url:
        canonical_url = urljoin(
            BASE_URL, canonical_url
        )

    website = get_value(
        record, "website", "website_url",
        "maker_website"
    )

    return {
        "product_id": str(
            get_value(record, "id", "slug")
            or normalize_name(name)
        ),
        "product_name": str(name).strip(),
        "description": get_value(
            record, "description", "tagline",
            "short_description"
        ),
        "product_url": canonical_url,
        "website": website,
        "category": get_value(
            record, "category", "categories"
        ),
        "tags": get_value(record, "tags"),
        "pricing": get_value(
            record, "pricing", "price"
        ),
        "company": get_value(
            record, "maker", "company", "developer"
        ),
        "source_url": canonical_url or BASE_URL,
        "source_dataset": BASE_URL,
        "source_updated_at": datetime.now(
            timezone.utc
        ).isoformat()
    }


async def fetch_products():
    all_records = []
    next_url = START_URL
    page = 1

    timeout = aiohttp.ClientTimeout(total=90)

    headers = {
        "User-Agent": "GraphOneIntelligence/1.0"
    }

    async with aiohttp.ClientSession(
        timeout=timeout,
        headers=headers
    ) as session:

        while next_url:
            logger.info("Fetching CiteLaunch page %s", page)

           
            for attempt in range(1, 6):

                async with session.get(next_url) as response:

                    if response.status in (429, 503):
                        retry_after = response.headers.get(
                            "Retry-After"
                        )

                        try:
                            wait_seconds = int(retry_after)
                        except (TypeError, ValueError):
                            wait_seconds = min(
                                5 * attempt, 30
                            )

                        logger.warning(
                            "HTTP %s. Retry %s/5 after %s seconds",
                            response.status,
                            attempt,
                            wait_seconds
                        )

                        if attempt == 5:
                            response.raise_for_status()

                        await asyncio.sleep(wait_seconds)
                        continue

                    response.raise_for_status()
                    data = await response.json(
                        content_type=None
                    )
                    break

            else:
                raise RuntimeError(
                    "Product API retries exhausted"
                )


            if isinstance(data, list):
                records = data
                next_url = None

            elif isinstance(data, dict):
                records = (
                    data.get("products")
                    or data.get("data")
                    or data.get("results")
                    or data.get("items")
                    or []
                )

                next_url = data.get("next")

                if next_url:
                    next_url = urljoin(
                        BASE_URL, next_url
                    )

            else:
                raise ValueError(
                    "Unexpected API response structure"
                )

            all_records.extend(records)

            logger.info(
                "Page %s: %s records",
                page, len(records)
            )

            page += 1

            if next_url:
                await asyncio.sleep(1)

    return all_records


def merge_products(new_records):
    existing_file = (
        PROCESSED_DIR / "products.json"
    )

    existing = []

    if existing_file.exists():
        with open(
            existing_file, "r", encoding="utf-8"
        ) as file:
            existing = json.load(file)

    combined = existing.copy()
    seen = set()

    for product in combined:
        name_key = normalize_name(
            product.get("product_name")
        )
        url_key = (
            product.get("product_url") or ""
        ).lower().rstrip("/")

        if name_key:
            seen.add(("name", name_key))
        if url_key:
            seen.add(("url", url_key))

    added = 0

    for record in new_records:
        product = normalize_product(record)

        if not product:
            continue

        name_key = normalize_name(
            product["product_name"]
        )
        url_key = (
            product.get("product_url") or ""
        ).lower().rstrip("/")

        if (
            ("name", name_key) in seen
            or (
                url_key
                and ("url", url_key) in seen
            )
        ):
            continue

        combined.append(product)
        seen.add(("name", name_key))

        if url_key:
            seen.add(("url", url_key))

        added += 1

    return combined, added


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )

    logger.info("Saved: %s", path)


async def main():
    try:
        raw = await fetch_products()

        save_json(
            raw,
            RAW_DIR / "products_citelaunch_raw.json"
        )

        combined, added = merge_products(raw)

        save_json(
            combined,
            PROCESSED_DIR / "products.json"
        )

        logger.info(
            "New unique products added: %s",
            added
        )
        logger.info(
            "Combined product count: %s",
            len(combined)
        )

        if len(combined) >= 1000:
            logger.info(
                "Product requirement satisfied: 1000+"
            )
        else:
            logger.warning(
                "Still below 1000 unique products."
            )

    except Exception:
        logger.exception(
            "CiteLaunch product crawler failed."
        )


if __name__ == "__main__":
    asyncio.run(main())

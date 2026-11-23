
import asyncio
import json
import logging
from pathlib import Path

import aiohttp


API_URL = "https://vibeking.fun/api/products"
PAGE_SIZE = 100

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_PATH = ROOT_DIR / "data" / "raw" / "products_vibeking_raw.json"
PROCESSED_PATH = (
    ROOT_DIR / "data" / "processed" / "products_vibeking.json"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def fetch_page(session, offset):
    params = {
        "limit": PAGE_SIZE,
        "offset": offset,
    }

    for attempt in range(1, 4):
        try:
            async with session.get(
                API_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=45),
            ) as response:

                if response.status in (429, 503):
                    wait = min(10 * attempt, 30)
                    logger.warning(
                        "HTTP %s at offset %s. Waiting %s sec",
                        response.status,
                        offset,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                payload = await response.json(
                    content_type=None
                )

                return payload

        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning(
                "Attempt %s failed at offset %s: %s",
                attempt,
                offset,
                exc,
            )
            await asyncio.sleep(3 * attempt)

    raise RuntimeError(
        f"Failed to fetch VibeKing offset {offset}"
    )


async def fetch_products():
    all_products = []
    seen_ids = set()
    offset = 0
    total = None

    headers = {
        "User-Agent": "GraphOne-Intelligence-Research-Crawler/1.0"
    }

    async with aiohttp.ClientSession(
        headers=headers
    ) as session:

        while True:
            logger.info(
                "Fetching VibeKing offset %s",
                offset,
            )

            payload = await fetch_page(session, offset)
            records = payload.get("data", [])

            if total is None:
                total = payload.get("total", 0)
                logger.info(
                    "API reports total products: %s",
                    total,
                )

            if not records:
                break

            new_records = 0

            for product in records:
                product_id = product.get("id")

                if not product_id:
                    continue

                if product_id in seen_ids:
                    continue

                seen_ids.add(product_id)
                all_products.append(product)
                new_records += 1

            logger.info(
                "Page records: %s | Unique collected: %s",
                len(records),
                len(all_products),
            )

            if new_records == 0:
                logger.warning(
                    "No new records received; stopping pagination."
                )
                break

            offset += len(records)

            if total and offset >= total:
                break

            await asyncio.sleep(0.5)

    return all_products


def normalize_product(product):
    return {
        "source": "VibeKing",
        "source_id": product.get("id"),
        "name": product.get("name"),
        "tagline": product.get("tagline"),
        "description": product.get("description"),
        "website": product.get("url"),
        "maker": product.get("maker"),
        "category": product.get("category"),
        "pricing": product.get("pricing"),
        "pricing_note": product.get("pricing_note"),
        "pricing_url": product.get("pricing_url"),
        "upvotes": product.get("upvotes"),
        "created_at": product.get("created_at"),
        "approved": product.get("approved"),
        "source_url": product.get("url"),
    }


async def main():
    raw_products = await fetch_products()

    if not raw_products:
        logger.error("No VibeKing products fetched.")
        return

    # Preserve the complete original API records.
    RAW_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with RAW_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            raw_products,
            file,
            indent=2,
            ensure_ascii=False,
        )

    # Keep only approved catalog products in normalized output.
    approved_products = [
        product
        for product in raw_products
        if product.get("approved") is True
        or product.get("approved") == 1
    ]

    normalized = [
        normalize_product(product)
        for product in approved_products
    ]

    PROCESSED_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with PROCESSED_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            normalized,
            file,
            indent=2,
            ensure_ascii=False,
        )

    logger.info("Raw products fetched: %s", len(raw_products))
    logger.info("Approved products: %s", len(normalized))
    logger.info("Raw saved: %s", RAW_PATH)
    logger.info("Normalized saved: %s", PROCESSED_PATH)


if __name__ == "__main__":
    asyncio.run(main())

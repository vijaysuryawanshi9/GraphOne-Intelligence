
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import aiohttp


# --------------------------------------------------
# Project paths
# --------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[2]

RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
LOG_DIR = ROOT_DIR / "logs"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# Logging
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(
            LOG_DIR / "startup_crawler.log",
            encoding="utf-8"
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# --------------------------------------------------
# Public YC dataset
# --------------------------------------------------

API_URL = (
    "https://yc-oss.github.io/api/companies/all.json"
)

API_SOURCE_URL = (
    "https://github.com/yc-oss/api"
)

YC_DIRECTORY_URL = (
    "https://www.ycombinator.com/companies/"
)


# --------------------------------------------------
# Utility functions
# --------------------------------------------------

def get_value(record, *keys):
    """Return the first available value from possible keys."""

    for key in keys:
        value = record.get(key)

        if value is not None and value != "":
            return value

    return None


def normalize_name(name):
    """Create a normalized name for duplicate detection."""

    if not name:
        return ""

    name = str(name).lower().strip()
    name = re.sub(r"[^a-z0-9]+", "", name)

    return name


def normalize_record(record):
    """Convert source record into our standard schema."""

    name = get_value(
        record,
        "name",
        "company_name",
        "title"
    )

    if not name:
        return None

    slug = get_value(
        record,
        "slug",
        "company_slug"
    )

    website = get_value(
        record,
        "website",
        "url",
        "company_website"
    )

    one_liner = get_value(
        record,
        "one_liner",
        "description",
        "short_description"
    )

    long_description = get_value(
        record,
        "long_description",
        "about",
        "details"
    )

    batch = get_value(
        record,
        "batch",
        "batch_name"
    )

    industries = get_value(
        record,
        "industries",
        "industry"
    )

    tags = get_value(
        record,
        "tags"
    )

    city = get_value(
        record,
        "city",
        "location"
    )

    country = get_value(
        record,
        "country"
    )

    founded_year = get_value(
        record,
        "year_founded",
        "founded_year"
    )

    company_status = get_value(
        record,
        "status"
    )

    yc_profile = get_value(
        record,
        "yc_url",
        "company_url",
        "profile_url"
    )

    if not yc_profile and slug:
        yc_profile = f"{YC_DIRECTORY_URL}{slug}/"

    if not yc_profile:
        yc_profile = YC_DIRECTORY_URL

    return {
        "startup_id": slug or normalize_name(name),
        "startup_name": str(name).strip(),
        "description": one_liner,
        "long_description": long_description,
        "website": website,
        "industry": industries,
        "tags": tags,
        "batch": batch,
        "location": city,
        "country": country,
        "founded_year": founded_year,
        "status": company_status,
        "yc_profile_url": yc_profile,
        "source_url": yc_profile,
        "source_dataset": API_SOURCE_URL,
        "source_updated_at": datetime.now(
            timezone.utc
        ).isoformat()
    }


# --------------------------------------------------
# Fetch dataset
# --------------------------------------------------

async def fetch_startups():
    logger.info("Downloading YC startup dataset...")

    timeout = aiohttp.ClientTimeout(total=120)

    headers = {
        "User-Agent": "GraphOneIntelligence/1.0"
    }

    async with aiohttp.ClientSession(
        timeout=timeout,
        headers=headers
    ) as session:

        async with session.get(API_URL) as response:
            response.raise_for_status()
            data = await response.json(content_type=None)

    # Support common JSON response structures
    if isinstance(data, list):
        records = data

    elif isinstance(data, dict):
        records = (
            data.get("companies")
            or data.get("data")
            or data.get("results")
            or []
        )

    else:
        raise ValueError(
            "Unexpected API response format"
        )

    logger.info(
        "Downloaded %s source records",
        len(records)
    )

    return records


# --------------------------------------------------
# Clean and deduplicate
# --------------------------------------------------

def process_startups(records):
    logger.info("Normalizing startup records...")

    processed = []
    seen_names = set()

    for record in records:

        if not isinstance(record, dict):
            continue

        startup = normalize_record(record)

        if not startup:
            continue

        normalized_name = normalize_name(
            startup["startup_name"]
        )

        if not normalized_name:
            continue

        if normalized_name in seen_names:
            continue

        seen_names.add(normalized_name)
        processed.append(startup)

    logger.info(
        "Unique startup records: %s",
        len(processed)
    )

    return processed


# --------------------------------------------------
# Save JSON
# --------------------------------------------------

def save_json(data, filepath):
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )

    logger.info("Saved data to %s", filepath)


# --------------------------------------------------
# Main pipeline
# --------------------------------------------------

async def main():

    try:
        raw_records = await fetch_startups()

        raw_file = RAW_DIR / "startups_yc_raw.json"

        save_json(
            raw_records,
            raw_file
        )

        startups = process_startups(
            raw_records
        )

        output_file = (
            PROCESSED_DIR / "startups.json"
        )

        save_json(
            startups,
            output_file
        )

        logger.info(
            "Startup crawler completed successfully."
        )

        logger.info(
            "Final startup count: %s",
            len(startups)
        )

        if len(startups) >= 1000:
            logger.info(
                "Assignment requirement satisfied: "
                "1000+ startups"
            )
        else:
            logger.warning(
                "Less than 1000 startup records found."
            )

    except Exception:
        logger.exception(
            "Startup crawler failed."
        )


if __name__ == "__main__":
    asyncio.run(main())

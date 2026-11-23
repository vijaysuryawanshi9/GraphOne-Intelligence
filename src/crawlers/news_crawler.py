
import asyncio
import calendar
import json
import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import aiohttp
import feedparser
import trafilatura


FEEDS = {
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "WIRED AI": "https://www.wired.com/feed/tag/ai/latest/rss",
    "Ars Technica AI": "https://arstechnica.com/ai/feed/",
    "MIT Technology Review AI": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
}

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_PATH = ROOT_DIR / "data" / "raw" / "news_raw.json"
OUTPUT_PATH = ROOT_DIR / "data" / "processed" / "news.json"

HEADERS = {
    "User-Agent": "GraphOne-Intelligence-News-Crawler/1.0"
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def parse_published_date(entry):
    """Return publication datetime in UTC, or None if unavailable."""
    published = entry.get("published") or entry.get("updated")

    if published:
        try:
            parsed = parsedate_to_datetime(published)

            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)

            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            pass

    parsed_tuple = entry.get("published_parsed") or entry.get(
        "updated_parsed"
    )

    if parsed_tuple:
        timestamp = calendar.timegm(parsed_tuple)
        return datetime.fromtimestamp(timestamp, timezone.utc)

    return None


def normalize_url(url):
    if not url:
        return ""

    parts = urlsplit(url.strip())

    # Remove tracking query parameters while retaining meaningful paths.
    return urlunsplit((
        parts.scheme.lower(),
        parts.netloc.lower(),
        parts.path.rstrip("/"),
        "",
        "",
    ))


async def fetch_feed(session, source, feed_url):
    for attempt in range(1, 4):
        try:
            async with session.get(feed_url) as response:
                if response.status in (429, 503):
                    wait = min(5 * attempt, 20)
                    logger.warning(
                        "%s returned HTTP %s. Waiting %s sec",
                        source,
                        response.status,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                content = await response.read()

                parsed = feedparser.parse(content)

                logger.info(
                    "%s | RSS entries: %s",
                    source,
                    len(parsed.entries),
                )

                return parsed.entries

        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning(
                "%s feed attempt %s failed: %s",
                source,
                attempt,
                exc,
            )
            await asyncio.sleep(2 * attempt)

    logger.error("Could not fetch feed: %s", source)
    return []


async def fetch_article(session, url, semaphore):
    async with semaphore:
        for attempt in range(1, 4):
            try:
                async with session.get(url) as response:
                    if response.status in (429, 503):
                        await asyncio.sleep(3 * attempt)
                        continue

                    response.raise_for_status()
                    html = await response.text(errors="ignore")

                    text = trafilatura.extract(
                        html,
                        url=url,
                        include_comments=False,
                        include_tables=True,
                    )

                    return text or ""

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.warning(
                    "Article fetch attempt %s failed: %s",
                    attempt,
                    exc,
                )
                await asyncio.sleep(attempt)

    return ""


async def main():
    now_utc = datetime.now(timezone.utc)
    cutoff_utc = now_utc - timedelta(hours=24)

    logger.info("Current UTC: %s", now_utc.isoformat())
    logger.info("24-hour cutoff: %s", cutoff_utc.isoformat())

    timeout = aiohttp.ClientTimeout(total=45)
    semaphore = asyncio.Semaphore(8)

    all_articles = []
    seen_urls = set()
    missing_dates = 0
    outside_window = 0

    async with aiohttp.ClientSession(
        headers=HEADERS,
        timeout=timeout,
    ) as session:

        for source, feed_url in FEEDS.items():
            entries = await fetch_feed(
                session,
                source,
                feed_url,
            )

            for entry in entries:
                article_url = entry.get("link", "").strip()
                title = entry.get("title", "").strip()

                if not article_url or not title:
                    continue

                url_key = normalize_url(article_url)

                if not url_key or url_key in seen_urls:
                    continue

                published_at = parse_published_date(entry)

                if published_at is None:
                    missing_dates += 1
                    logger.warning(
                        "Skipping article with missing date: %s",
                        title,
                    )
                    continue

                # Strictly include only articles within last 24 hours.
                if published_at < cutoff_utc or published_at > now_utc:
                    outside_window += 1
                    continue

                seen_urls.add(url_key)

                article = {
                    "title": title,
                    "source": source,
                    "url": article_url,
                    "published_at": published_at.isoformat(),
                    "published_date_utc": published_at.strftime(
                        "%Y-%m-%d"
                    ),
                    "published_time_utc": published_at.strftime(
                        "%H:%M:%S"
                    ),
                    "crawl_time_utc": now_utc.isoformat(),
                    "content": "",
                    "content_status": "pending",
                }

                all_articles.append(article)

        logger.info(
            "Articles inside 24-hour window: %s",
            len(all_articles),
        )

        tasks = [
            fetch_article(
                session,
                article["url"],
                semaphore,
            )
            for article in all_articles
        ]

        contents = await asyncio.gather(*tasks)

        for article, content in zip(all_articles, contents):
            article["content"] = content
            article["content_status"] = (
                "full_text_extracted"
                if content
                else "full_text_unavailable"
            )

    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with RAW_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            all_articles,
            file,
            indent=2,
            ensure_ascii=False,
        )

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            all_articles,
            file,
            indent=2,
            ensure_ascii=False,
        )

    extracted = sum(
        1 for article in all_articles
        if article["content"]
    )

    logger.info("News records saved: %s", len(all_articles))
    logger.info("Full text extracted: %s", extracted)
    logger.info("Missing publication dates skipped: %s", missing_dates)
    logger.info("Outside 24-hour window skipped: %s", outside_window)
    logger.info("Raw output: %s", RAW_PATH)
    logger.info("Processed output: %s", OUTPUT_PATH)


if __name__ == "__main__":
    asyncio.run(main())

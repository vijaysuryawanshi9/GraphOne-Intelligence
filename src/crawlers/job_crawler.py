
import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import feedparser
import trafilatura


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

BASE_DIR = Path(__file__).resolve().parents[2]

RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

KEYWORDS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "data scientist",
    "data analyst",
    "data engineer",
    "python",
    "llm",
    "generative ai",
    "computer vision",
    "nlp",
    "ai engineer",
    "ml engineer",
    "business intelligence",
    "power bi",
    "sql",
]

SOURCES = {
    "Remotive": "https://remotive.com/api/remote-jobs",
    "Remote OK": "https://remoteok.com/api",
    "Jobicy": "https://jobicy.com/api/v2/remote-jobs",
    "Himalayas": "https://himalayas.app/jobs/api?limit=100",
    "We Work Remotely": "https://weworkremotely.com/remote-jobs.rss",
}


def parse_date(value):
    """Convert supported date strings to timezone-aware UTC datetime."""

    if not value:
        return None

    try:
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except (ValueError, TypeError):
        pass

    try:
        dt = parsedate_to_datetime(str(value))

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except (ValueError, TypeError, OverflowError):
        return None


def normalize_job(job, source):
    """Normalize different job-source schemas."""

    if source == "Remotive":
        return {
            "title": job.get("title"),
            "company": job.get("company_name"),
            "location": job.get("candidate_required_location"),
            "url": job.get("url"),
            "description": job.get("description"),
            "published_at": job.get("publication_date"),
            "source": source,
        }

    if source == "Remote OK":
        return {
            "title": job.get("position"),
            "company": job.get("company"),
            "location": job.get("location"),
            "url": job.get("url"),
            "description": job.get("description"),
            "published_at": job.get("date"),
            "source": source,
        }

    if source == "Jobicy":
        return {
            "title": job.get("jobTitle"),
            "company": job.get("companyName"),
            "location": job.get("jobGeo"),
            "url": job.get("url"),
            "description": job.get("jobDescription"),
            "published_at": job.get("pubDate"),
            "source": source,
        }

    if source == "Himalayas":
        return {
            "title": job.get("title"),
            "company": job.get("companyName"),
            "location": job.get("location"),
            "url": job.get("applicationLink")
            or job.get("url"),
            "description": job.get("description"),
            "published_at": job.get("pubDate")
            or job.get("publishedAt"),
            "source": source,
        }

    return {
        "title": job.get("title"),
        "company": job.get("company"),
        "location": job.get("location"),
        "url": job.get("link"),
        "description": job.get("description"),
        "published_at": job.get("published"),
        "source": source,
    }


def is_relevant(job):
    text = (
        str(job.get("title") or "")
        + " "
        + str(job.get("description") or "")
    ).lower()

    return any(keyword in text for keyword in KEYWORDS)


async def fetch_json(session, url, source):
    async with session.get(url) as response:
        response.raise_for_status()
        data = await response.json(content_type=None)

    if source == "Remote OK":
        return data[1:] if isinstance(data, list) else []

    return data.get("jobs", [])


async def fetch_rss(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        content = await response.read()

    feed = feedparser.parse(content)
    jobs = []

    for entry in feed.entries:
        jobs.append({
            "title": entry.get("title"),
            "company": None,
            "location": None,
            "url": entry.get("link"),
            "description": entry.get("summary"),
            "published_at": entry.get("published")
            or entry.get("updated"),
            "source": "We Work Remotely",
        })

    return jobs


async def fetch_source(session, source, url):
    try:
        if source == "We Work Remotely":
            jobs = await fetch_rss(session, url)
        else:
            raw_jobs = await fetch_json(session, url, source)
            jobs = [
                normalize_job(job, source)
                for job in raw_jobs
            ]

        logging.info(
            "%s | Fetched: %s",
            source,
            len(jobs),
        )

        return jobs

    except Exception as exc:
        logging.error(
            "%s | Fetch failed: %s",
            source,
            exc,
        )

        return []


async def extract_description(session, job, semaphore):
    url = job.get("url")

    if not url:
        return job

    async with semaphore:
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=25),
            ) as response:

                if response.status != 200:
                    return job

                html = await response.text(errors="ignore")

            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
            )

            if text and len(text) > len(
                str(job.get("description") or "")
            ):
                job["description"] = text

        except Exception:
            pass

    return job


async def main():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    logging.info("Current UTC: %s", now.isoformat())
    logging.info("24-hour cutoff: %s", cutoff.isoformat())

    headers = {
        "User-Agent": "GraphOne-Intelligence/1.0"
    }

    async with aiohttp.ClientSession(
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=40),
    ) as session:

        tasks = [
            fetch_source(session, source, url)
            for source, url in SOURCES.items()
        ]

        results = await asyncio.gather(*tasks)

        all_jobs = [
            job
            for source_jobs in results
            for job in source_jobs
        ]

        raw_path = RAW_DIR / "jobs_raw.json"

        with open(raw_path, "w", encoding="utf-8") as file:
            json.dump(
                all_jobs,
                file,
                indent=2,
                ensure_ascii=False,
            )

        logging.info("Total raw jobs: %s", len(all_jobs))

        filtered_jobs = []
        missing_dates = 0
        outside_window = 0
        irrelevant = 0

        for job in all_jobs:
            published = parse_date(job.get("published_at"))

            if published is None:
                missing_dates += 1
                continue

            if published < cutoff or published > now:
                outside_window += 1
                continue

            if not is_relevant(job):
                irrelevant += 1
                continue

            job["published_at"] = published.isoformat()
            job["date_utc"] = published.strftime("%Y-%m-%d")
            job["time_utc"] = published.strftime("%H:%M:%S")
            job["crawl_time"] = now.isoformat()

            filtered_jobs.append(job)

        # Deduplicate by URL
        unique_jobs = {}
        for job in filtered_jobs:
            url = job.get("url")

            if url:
                key = url.strip().lower()
            else:
                key = (
                    str(job.get("title")).lower()
                    + "|"
                    + str(job.get("company")).lower()
                )

            unique_jobs[key] = job

        jobs = list(unique_jobs.values())

        logging.info(
            "Jobs within 24 hours and relevant: %s",
            len(filtered_jobs),
        )
        logging.info("Unique jobs: %s", len(jobs))
        logging.info("Missing dates skipped: %s", missing_dates)
        logging.info("Outside window skipped: %s", outside_window)
        logging.info("Irrelevant jobs skipped: %s", irrelevant)

        # Fetch full job description where possible
        semaphore = asyncio.Semaphore(8)

        description_tasks = [
            extract_description(session, job, semaphore)
            for job in jobs
        ]

        jobs = await asyncio.gather(*description_tasks)

        processed_path = PROCESSED_DIR / "jobs.json"

        with open(
            processed_path,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                jobs,
                file,
                indent=2,
                ensure_ascii=False,
            )

        logging.info("Final jobs saved: %s", len(jobs))
        logging.info("Raw output: %s", raw_path)
        logging.info("Processed output: %s", processed_path)


if __name__ == "__main__":
    asyncio.run(main())

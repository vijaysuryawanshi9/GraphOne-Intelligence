
import asyncio
import aiohttp
import feedparser
import json
import logging
import os

from src.crawlers.github_client import search_repository


# ==================================================
# PROJECT SETUP
# ==================================================

os.makedirs("logs", exist_ok=True)
os.makedirs("data/processed", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(
            "logs/arxiv_crawler.log",
            encoding="utf-8"
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"


# AI / ML categories
CATEGORIES = [
    "cs.AI",
    "cs.LG",
    "cs.CL",
    "cs.CV",
    "cs.RO",
    "cs.MA"
]


# ==================================================
# FETCH PAPERS FROM ARXIV
# ==================================================

async def fetch_papers(max_results=100):

    all_papers = []
    seen_ids = set()

    timeout = aiohttp.ClientTimeout(total=60)

    async with aiohttp.ClientSession(
        timeout=timeout
    ) as session:

        for index, category in enumerate(CATEGORIES):

            logger.info(
                "Fetching arXiv category: %s",
                category
            )

            params = {
                "search_query": f"cat:{category}",
                "start": 0,
                "max_results": max_results,
                "sortBy": "submittedDate",
                "sortOrder": "descending"
            }

            try:

                async with session.get(
                    ARXIV_API,
                    params=params
                ) as response:

                    response.raise_for_status()

                    content = await response.text()

                feed = feedparser.parse(content)

                logger.info(
                    "%s returned %s papers",
                    category,
                    len(feed.entries)
                )

                for entry in feed.entries:

                    arxiv_id = entry.get(
                        "id", ""
                    ).split("/")[-1]

                    # Skip invalid IDs
                    if not arxiv_id:
                        continue

                    # Remove duplicate papers
                    if arxiv_id in seen_ids:
                        continue

                    seen_ids.add(arxiv_id)

                    paper = {
                        "title": entry.get(
                            "title", ""
                        ).replace("\n", " ").strip(),

                        "authors": [
                            author.name
                            for author in entry.get(
                                "authors", []
                            )
                        ],

                        "abstract": entry.get(
                            "summary", ""
                        ).replace("\n", " ").strip(),

                        "paper_url": entry.get(
                            "link", ""
                        ),

                        "arxiv_id": arxiv_id,

                        "published_date": entry.get(
                            "published", ""
                        ),

                        "updated_date": entry.get(
                            "updated", ""
                        ),

                        "categories": entry.get(
                            "arxiv_primary_category", {}
                        ).get("term", category),

                        "source": "arXiv",

                        "github_repo": None,

                        "github_url": None,

                        "github_stars": None
                    }

                    all_papers.append(paper)

            except Exception as error:

                logger.error(
                    "Failed to fetch category %s: %s",
                    category,
                    error
                )

            # Respect arXiv API request interval
            if index < len(CATEGORIES) - 1:

                await asyncio.sleep(3)

    logger.info(
        "Total unique papers fetched: %s",
        len(all_papers)
    )

    return all_papers


# ==================================================
# GITHUB ENRICHMENT
# ==================================================

async def enrich_with_github(
    papers,
    github_limit=30
):

    enriched_papers = []

    total_papers = len(papers)

    search_limit = min(
        github_limit,
        total_papers
    )

    logger.info(
        "GitHub enrichment started: %s papers",
        search_limit
    )

    for index, paper in enumerate(papers):

        # Search GitHub only for limited papers
        if index < github_limit:

            title = paper.get(
                "title", ""
            )

            logger.info(
                "GitHub search %s/%s: %s",
                index + 1,
                search_limit,
                title[:70]
            )

            try:

                github_data = await search_repository(
                    title
                )

                if github_data:

                    paper["github_repo"] = (
                        github_data.get(
                            "github_repo"
                        )
                    )

                    paper["github_url"] = (
                        github_data.get(
                            "github_url"
                        )
                    )

                    paper["github_stars"] = (
                        github_data.get(
                            "github_stars"
                        )
                    )

                else:

                    paper["github_repo"] = None
                    paper["github_url"] = None
                    paper["github_stars"] = None

            except Exception as error:

                logger.warning(
                    "GitHub search failed for paper: %s",
                    error
                )

                paper["github_repo"] = None
                paper["github_url"] = None
                paper["github_stars"] = None

            # Delay between GitHub requests
            await asyncio.sleep(1)

        # Preserve all remaining papers
        else:

            paper["github_repo"] = None
            paper["github_url"] = None
            paper["github_stars"] = None

        enriched_papers.append(paper)

    logger.info(
        "GitHub enrichment completed. "
        "Papers preserved: %s",
        len(enriched_papers)
    )

    return enriched_papers


# ==================================================
# SAVE PAPERS TO JSON
# ==================================================

def save_papers(papers):

    output_path = (
        "data/processed/research_papers.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            papers,
            file,
            indent=4,
            ensure_ascii=False
        )

    logger.info(
        "Saved %s papers to %s",
        len(papers),
        output_path
    )


# ==================================================
# MAIN PIPELINE
# ==================================================

async def main():

    logger.info(
        "Starting arXiv research paper crawler"
    )

    # Fetch papers from all categories
    papers = await fetch_papers(
        max_results=250
    )

    # Research papers are not restricted
    # to the last 24 hours.
    # Keep original publication dates.

    if papers:

        papers = await enrich_with_github(
            papers,
            github_limit=30
        )

    else:

        logger.warning(
            "No research papers fetched."
        )

    # Save complete dataset
    save_papers(papers)

    logger.info(
        "Crawler finished. Total research papers: %s",
        len(papers)
    )


# ==================================================
# ENTRY POINT
# ==================================================

if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:

        logger.warning(
            "Crawler stopped by user."
        )

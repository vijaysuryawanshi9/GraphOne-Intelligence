
import os
import asyncio
import aiohttp
import logging
from dotenv import load_dotenv

load_dotenv()

GITHUB_API = "https://api.github.com"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"


async def search_repository(paper_title):
    """
    Search GitHub for a repository related to a research paper.
    Returns verified repository details or None.
    """

    params = {
        "q": paper_title,
        "sort": "stars",
        "order": "desc",
        "per_page": 5,
    }

    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(
        headers=HEADERS,
        timeout=timeout
    ) as session:

        try:
            async with session.get(
                f"{GITHUB_API}/search/repositories",
                params=params
            ) as response:

                if response.status == 403:
                    logging.warning("GitHub API rate limit reached.")
                    return None

                response.raise_for_status()
                data = await response.json()

        except aiohttp.ClientError as error:
            logging.error("GitHub request failed: %s", error)
            return None

    repositories = data.get("items", [])

    if not repositories:
        return None

    repo = repositories[0]

    return {
        "github_repo": repo["full_name"],
        "github_url": repo["html_url"],
        "github_stars": repo["stargazers_count"],
    }


async def main():
    test_title = "Attention Is All You Need"

    result = await search_repository(test_title)

    if result:
        print("Repository found:")
        print(result)
    else:
        print("No repository found or API request failed.")


if __name__ == "__main__":
    asyncio.run(main())

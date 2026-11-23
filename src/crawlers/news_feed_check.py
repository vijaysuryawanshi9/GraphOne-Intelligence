
import asyncio
import aiohttp
import feedparser

FEEDS = {
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "WIRED AI": "https://www.wired.com/feed/tag/ai/latest/rss",
    "Ars Technica AI": "https://arstechnica.com/ai/feed/",
    "MIT Technology Review AI": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
}


async def main():
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for name, url in FEEDS.items():
            try:
                async with session.get(url) as response:
                    content = await response.read()

                    parsed = feedparser.parse(content)

                    dated = sum(
                        1 for entry in parsed.entries
                        if entry.get("published")
                        or entry.get("updated")
                    )

                    print(
                        f"{name} | HTTP {response.status}"
                        f" | Entries: {len(parsed.entries)}"
                        f" | Dated: {dated}"
                    )

            except Exception as error:
                print(f"{name} | ERROR: {error}")


if __name__ == "__main__":
    asyncio.run(main())


import asyncio
import json
import logging

import aiohttp
import feedparser


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

SOURCES = {
    "Remote OK": {
        "url": "https://remoteok.com/api",
        "type": "json",
    },
    "Remotive": {
        "url": "https://remotive.com/api/remote-jobs",
        "type": "json",
    },
    "Jobicy": {
        "url": "https://jobicy.com/api/v2/remote-jobs",
        "type": "json",
    },
    "Himalayas": {
        "url": "https://himalayas.app/jobs/api?limit=20",
        "type": "json",
    },
    "We Work Remotely": {
        "url": "https://weworkremotely.com/remote-jobs.rss",
        "type": "rss",
    },
}


async def check_source(session, name, source):
    try:
        async with session.get(
            source["url"],
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:

            if response.status != 200:
                logging.error(
                    "%s | HTTP %s",
                    name,
                    response.status,
                )
                return

            content = await response.read()

            if source["type"] == "rss":
                parsed = feedparser.parse(content)
                count = len(parsed.entries)

            else:
                data = json.loads(content)

                if name == "Remote OK":
                    # First item is usually API notice
                    count = max(len(data) - 1, 0)

                elif name == "Remotive":
                    count = len(data.get("jobs", []))

                elif name == "Jobicy":
                    count = len(data.get("jobs", []))

                elif name == "Himalayas":
                    count = len(data.get("jobs", []))

                else:
                    count = len(data)

            logging.info(
                "%s | HTTP 200 | Records: %s",
                name,
                count,
            )

    except Exception as exc:
        logging.error("%s | Failed: %s", name, exc)


async def main():
    headers = {
        "User-Agent": "GraphOne-Intelligence/1.0",
    }

    connector = aiohttp.TCPConnector(limit=5)

    async with aiohttp.ClientSession(
        headers=headers,
        connector=connector,
    ) as session:

        tasks = [
            check_source(session, name, source)
            for name, source in SOURCES.items()
        ]

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())

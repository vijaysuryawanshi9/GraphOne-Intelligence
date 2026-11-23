
import json
from pathlib import Path

folder = Path("data/processed")

files = [
    "startups.json",
    "products.json",
    "research_papers.json",
    "jobs.json",
    "news.json",
]

for filename in files:
    path = folder / filename

    if not path.exists():
        print(f"\n{filename}: NOT FOUND")
        continue

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"\nFILE: {filename}")

    if isinstance(data, list):
        print("Records:", len(data))

        if data:
            print("Fields:", list(data[0].keys()))

    elif isinstance(data, dict):
        print("Fields:", list(data.keys()))

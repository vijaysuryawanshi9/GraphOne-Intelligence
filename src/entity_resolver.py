
import json
import logging
import re
from collections import Counter
from pathlib import Path

from rapidfuzz import fuzz, process


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = BASE_DIR / "data" / "processed"
CONFIG_DIR = BASE_DIR / "config"

CONFIG_DIR.mkdir(parents=True, exist_ok=True)

SEED_FILE = CONFIG_DIR / "canonical_entities.json"
LOG_FILE = DATA_DIR / "entity_mapping_log.json"
SUMMARY_FILE = DATA_DIR / "entity_resolution_summary.json"

STARTUPS_FILE = DATA_DIR / "startups.json"
PRODUCTS_FILE = DATA_DIR / "products.json"
JOBS_FILE = DATA_DIR / "jobs.json"
PAPERS_FILE = DATA_DIR / "research_papers.json"

FUZZY_THRESHOLD = 94
AMBIGUITY_MARGIN = 5


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def normalize_name(name):
    """Normalize names for exact matching."""

    if not name:
        return ""

    name = str(name).lower().strip()
    name = re.sub(r"\b(inc|llc|ltd|limited|corp|corporation)\b", "", name)
    name = re.sub(r"[^a-z0-9]+", " ", name)

    return " ".join(name.split())


def collect_entities():
    """Collect organization names from available datasets."""

    entities = []

    startups = load_json(STARTUPS_FILE)
    products = load_json(PRODUCTS_FILE)
    jobs = load_json(JOBS_FILE)
    papers = load_json(PAPERS_FILE)

    for row in startups:
        name = row.get("startup_name")
        if name:
            entities.append({
                "name": str(name).strip(),
                "source": "startups",
            })

    for row in products:
        name = row.get("company")
        if name:
            entities.append({
                "name": str(name).strip(),
                "source": "products",
            })

    for row in jobs:
        name = row.get("company")
        if name:
            entities.append({
                "name": str(name).strip(),
                "source": "jobs",
            })

    # GitHub repository owner is a possible organization entity.
    for row in papers:
        repo = row.get("github_repo")

        if repo and "/" in str(repo):
            owner = str(repo).split("/", 1)[0].strip()

            if owner:
                entities.append({
                    "name": owner,
                    "source": "research_papers_github",
                })

    return entities


def build_seed_list(entities):
    """
    Create a canonical seed list.

    Startup names are preferred as canonical names.
    Remaining companies and GitHub owners are added.
    """

    if SEED_FILE.exists():
        logging.info("Existing canonical seed list found.")
        return load_json(SEED_FILE)

    startup_names = []
    other_names = []

    for entity in entities:
        if entity["source"] == "startups":
            startup_names.append(entity["name"])
        else:
            other_names.append(entity["name"])

    names = startup_names + other_names

    unique_names = {}
    for name in names:
        normalized = normalize_name(name)

        if normalized and normalized not in unique_names:
            unique_names[normalized] = name

    seed = [
        {
            "canonical_name": name,
            "normalized_name": normalized,
        }
        for normalized, name in unique_names.items()
    ]

    save_json(SEED_FILE, seed)

    logging.info("Canonical seed entities: %s", len(seed))

    return seed


def resolve_name(name, seed):
    """Resolve a name using exact and fuzzy matching."""

    normalized = normalize_name(name)

    if not normalized:
        return {
            "canonical_name": None,
            "match_score": 0,
            "match_type": "empty",
            "status": "unmatched",
        }

    seed_lookup = {
        item["normalized_name"]: item["canonical_name"]
        for item in seed
    }

    # Exact normalized match
    if normalized in seed_lookup:
        return {
            "canonical_name": seed_lookup[normalized],
            "match_score": 100,
            "match_type": "exact",
            "status": "matched",
        }

    choices = [
        item["normalized_name"]
        for item in seed
    ]

    matches = process.extract(
        normalized,
        choices,
        scorer=fuzz.ratio,
        limit=2,
    )

    if not matches:
        return {
            "canonical_name": name,
            "match_score": 0,
            "match_type": "new_entity",
            "status": "new",
        }

    best_name, best_score, _ = matches[0]

    second_score = (
        matches[1][1]
        if len(matches) > 1
        else 0
    )

    if best_score >= FUZZY_THRESHOLD:

        if best_score - second_score < AMBIGUITY_MARGIN:
            return {
                "canonical_name": None,
                "match_score": best_score,
                "match_type": "fuzzy_ambiguous",
                "status": "review",
            }

        return {
            "canonical_name": seed_lookup[best_name],
            "match_score": best_score,
            "match_type": "fuzzy",
            "status": "matched",
        }

    return {
        "canonical_name": name,
        "match_score": best_score,
        "match_type": "new_entity",
        "status": "new",
    }


def main():
    entities = collect_entities()

    logging.info("Entity mentions collected: %s", len(entities))

    seed = build_seed_list(entities)

    mapping_log = []
    summary = Counter()

    for entity in entities:
        result = resolve_name(
            entity["name"],
            seed,
        )

        mapping_log.append({
            "original_name": entity["name"],
            "source": entity["source"],
            **result,
        })

        summary[result["status"]] += 1
        summary[result["match_type"]] += 1

    save_json(LOG_FILE, mapping_log)
    save_json(SUMMARY_FILE, dict(summary))

    logging.info("Mapping log records: %s", len(mapping_log))
    logging.info("Summary: %s", dict(summary))
    logging.info("Seed file: %s", SEED_FILE)
    logging.info("Mapping log: %s", LOG_FILE)


if __name__ == "__main__":
    main()


import json
import shutil
from pathlib import Path
from urllib.parse import urlparse, urlunparse

ROOT = Path(__file__).resolve().parent

EXISTING_FILE = ROOT / "data" / "processed" / "products.json"
VIBEKING_FILE = ROOT / "data" / "processed" / "products_vibeking.json"
OUTPUT_FILE = EXISTING_FILE
BACKUP_FILE = ROOT / "data" / "processed" / "products_backup.json"


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def normalize_url(url):
    if not url:
        return ""

    url = url.strip().lower()

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)

    hostname = (parsed.hostname or "").replace("www.", "")
    path = parsed.path.rstrip("/")

    return urlunparse((
        "https",
        hostname,
        path,
        "",
        "",
        "",
    ))


def normalize_existing(product):
    return {
        "product_id": product.get("product_id"),
        "product_name": product.get("product_name"),
        "description": product.get("description"),
        "product_url": product.get("product_url"),
        "category": product.get("category"),
        "pricing": product.get("pricing"),
        "company": product.get("company"),
        "source_url": product.get("source_url")
        or product.get("product_url"),
        "source_dataset": product.get("source_dataset")
        or "SubmitMySaas",
        "source_updated_at": product.get("source_updated_at"),
    }


def normalize_vibeking(product):
    return {
        "product_id": product.get("source_id"),
        "product_name": product.get("name"),
        "description": product.get("description")
        or product.get("tagline"),
        "product_url": product.get("website"),
        "category": product.get("category"),
        "pricing": product.get("pricing"),
        "company": product.get("maker"),
        "source_url": product.get("source_url")
        or product.get("website"),
        "source_dataset": "VibeKing",
        "source_updated_at": product.get("created_at"),
    }


def main():
    existing = load_json(EXISTING_FILE)
    vibeking = load_json(VIBEKING_FILE)

    # Create backup only once; never overwrite the first backup.
    if not BACKUP_FILE.exists():
        shutil.copy2(EXISTING_FILE, BACKUP_FILE)
        print("Backup created:", BACKUP_FILE)

    merged = []
    seen = set()

    for product in existing:
        normalized = normalize_existing(product)

        url_key = normalize_url(normalized.get("product_url"))
        name_key = (normalized.get("product_name") or "").strip().lower()

        key = url_key or name_key

        if key and key not in seen:
            seen.add(key)
            merged.append(normalized)

    vibeking_added = 0
    duplicates = 0

    for product in vibeking:
        normalized = normalize_vibeking(product)

        url_key = normalize_url(normalized.get("product_url"))
        name_key = (normalized.get("product_name") or "").strip().lower()

        key = url_key or name_key

        if not key:
            continue

        if key in seen:
            duplicates += 1
            continue

        seen.add(key)
        merged.append(normalized)
        vibeking_added += 1

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            merged,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("\nMerge completed successfully")
    print("SubmitMySaas original:", len(existing))
    print("VibeKing source:", len(vibeking))
    print("VibeKing added:", vibeking_added)
    print("Duplicates skipped:", duplicates)
    print("Final unique products:", len(merged))
    print("Saved to:", OUTPUT_FILE)


if __name__ == "__main__":
    main()

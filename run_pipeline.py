
import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "pipeline.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

REQUIRED_FILES = [
    "data/processed/startups.json",
    "data/processed/products.json",
    "data/processed/research_papers.json",
    "data/processed/jobs.json",
    "data/processed/news.json",
]


def run_stage(name, command):
    logging.info("Starting stage: %s", name)

    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.stdout:
        logging.info(result.stdout.strip())

    if result.stderr:
        logging.warning(result.stderr.strip())

    if result.returncode != 0:
        raise RuntimeError(
            f"Stage '{name}' failed with exit code {result.returncode}"
        )

    logging.info("Completed stage: %s", name)


def validate_data():
    logging.info("Validating processed datasets...")

    missing = [
        file for file in REQUIRED_FILES
        if not (ROOT / file).exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing processed files:\n" + "\n".join(missing)
        )

    logging.info("All five processed datasets are present.")


def main():
    logging.info("=" * 50)
    logging.info("GraphOne Intelligence Pipeline Started")
    logging.info("=" * 50)

    validate_data()

    run_stage(
        "Entity Resolution",
        [sys.executable, "-m", "src.entity_resolver"],
    )

    run_stage(
        "Google Sheets Upload",
        [sys.executable, "-m", "src.google_sheets_uploader"],
    )

    logging.info("PIPELINE COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("PIPELINE FAILED")
        sys.exit(1)

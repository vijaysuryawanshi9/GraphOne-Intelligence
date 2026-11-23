
import json
import logging
import os
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "processed"

CREDENTIALS_PATH = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    "credentials/google_service_account.json",
)

SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

DATASETS = {
    "Startups": "startups.json",
    "Products": "products.json",
    "Research Papers": "research_papers.json",
    "Jobs": "jobs.json",
    "News": "news.json",
    "Entity Mapping Log": "entity_mapping_log.json",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def normalize_value(value):
    """Convert nested values into Google Sheets-compatible text."""

    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        return json.dumps(
            value,
            ensure_ascii=False,
        )

    return value


def records_to_rows(records):
    """Convert list of dictionaries to header + rows."""

    if not records:
        return [["No records available"]]

    headers = []

    for record in records:
        for key in record.keys():
            if key not in headers:
                headers.append(key)

    rows = [headers]

    for record in records:
        row = [
            normalize_value(record.get(header))
            for header in headers
        ]
        rows.append(row)

    return rows


def get_client():
    credentials_file = BASE_DIR / CREDENTIALS_PATH

    if not credentials_file.exists():
        raise FileNotFoundError(
            f"Credentials file not found: {credentials_file}"
        )

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_file(
        str(credentials_file),
        scopes=scopes,
    )

    return gspread.authorize(credentials)


def upload_tab(spreadsheet, tab_name, filename):
    file_path = DATA_DIR / filename

    if not file_path.exists():
        logging.warning(
            "Skipping %s: file not found (%s)",
            tab_name,
            file_path,
        )
        return

    records = load_json(file_path)

    if not isinstance(records, list):
        logging.warning(
            "Skipping %s: expected a JSON list",
            tab_name,
        )
        return

    rows = records_to_rows(records)

    try:
        worksheet = spreadsheet.worksheet(tab_name)

    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=tab_name,
            rows=max(len(rows), 100),
            cols=max(len(rows[0]), 20),
        )

    # Resize before upload.
    worksheet.resize(
        rows=max(len(rows), 1),
        cols=max(len(rows[0]), 1),
    )

    worksheet.clear()

    # Upload in batches to avoid oversized requests.
    batch_size = 500

    for start in range(0, len(rows), batch_size):
        batch = rows[start:start + batch_size]

        worksheet.update(
            values=batch,
            range_name=f"A{start + 1}",
            value_input_option="RAW",
        )

    logging.info(
        "%s | Uploaded records: %s",
        tab_name,
        len(records),
    )


def main():
    if not SHEET_ID:
        raise ValueError(
            "GOOGLE_SHEET_ID is missing from .env"
        )

    client = get_client()

    spreadsheet = client.open_by_key(SHEET_ID)

    logging.info(
        "Connected to spreadsheet: %s",
        spreadsheet.title,
    )

    for tab_name, filename in DATASETS.items():
        upload_tab(
            spreadsheet,
            tab_name,
            filename,
        )

    logging.info("Google Sheets upload completed.")


if __name__ == "__main__":
    main()

# GraphOne Intelligence

An AI-powered data collection and processing project that brings
together startup, product, research paper, job, and AI news information
into structured datasets and Google Sheets.

## Project Overview

GraphOne Intelligence collects information from public sources,
normalizes records, performs entity resolution, and publishes the
processed datasets to a Google Sheets workbook.

### Dataset snapshot

The latest successful pipeline run uploaded the following records
(excluding header rows):

  Dataset                   Records
  -------------------- ------------
  Startups                    6,300
  Products                    3,270
  Research Papers             1,258
  Jobs                           66
  News                            8
  Entity Mapping Log          8,968
  **Total**              **19,870**

These counts describe the last recorded run and may change when data is
refreshed.

## Features

-   Startup dataset collection from the YC public community dataset
-   Product collection from SubmitMySaas and VibeKing sources
-   Research paper collection from selected arXiv categories
-   AI news collection from five RSS sources
-   AI job collection from five job sources
-   Entity resolution and mapping-log generation
-   LLM extraction with provider fallback (Gemini → Groq → DeepSeek)
-   Google Sheets upload in batches
-   Pipeline logging and processed-data validation

## Data Sources

### Startups

-   YC public community data

### Products

-   SubmitMySaas
-   VibeKing

### Research papers

-   arXiv categories: `cs.AI`, `cs.LG`, `cs.CL`, `cs.CV`, `cs.RO`,
    `cs.MA`
-   GitHub repository association is included where available.
    Repository matches and star counts should be validated before
    claiming complete verified coverage.

### News

-   TechCrunch AI
-   The Verge AI
-   WIRED AI
-   Ars Technica AI
-   MIT Technology Review AI

The crawler applies a strict 24-hour publication window based on the
source's available publication timestamp and extracts article text where
possible.

### Jobs

-   Remotive
-   Remote OK
-   Jobicy
-   Himalayas
-   We Work Remotely

The job crawler filters records by its available date fields and
relevance. Some source dates may represent updates rather than original
publication dates; validate this when using the dataset for
time-sensitive analysis.

## Project Structure

``` text
GraphOne_Intelligence/
├── config/
│   └── canonical_entities.json
├── credentials/                 # Private; never commit
├── data/
│   ├── raw/
│   └── processed/
├── logs/
├── src/
│   ├── crawlers/
│   │   ├── startup_crawler.py
│   │   ├── product_crawler.py
│   │   ├── product_crawler_vibeking.py
│   │   ├── arxiv_crawler.py
│   │   ├── news_crawler.py
│   │   └── job_crawler.py
│   ├── entity_resolver.py
│   ├── llm_extractor.py
│   └── google_sheets_uploader.py
├── settings.py
├── run_pipeline.py
├── merge_products.py
├── requirements.txt
├── .env                        # Private; never commit
└── README.md
```

## Setup

### 1. Clone the repository

``` bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd GraphOne_Intelligence
```

### 2. Create and activate a virtual environment

Windows PowerShell:

``` powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

``` powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root. Add your own API keys and
Google Sheets configuration. Never put secret values in this README or
commit them to Git.

Expected configuration keys include:

``` dotenv
GEMINI_API_KEY=
GROQ_API_KEY=
DEEPSEEK_API_KEY=

GEMINI_MODEL=
GROQ_MODEL=
DEEPSEEK_MODEL=

GOOGLE_SERVICE_ACCOUNT_FILE=credentials/google_service_account.json
GOOGLE_SHEET_ID=
```

Place the Google service-account JSON key at the configured path and
share the spreadsheet with the service-account email as an Editor.

## Run the Existing Pipeline

The current pipeline reuses the processed JSON files, runs entity
resolution, and uploads the datasets to Google Sheets. It does not
automatically rerun all crawlers.

``` powershell
python run_pipeline.py
```

Pipeline logs are written to:

``` text
logs/pipeline.log
```

## Test LLM Provider Fallback

Run the extractor's smoke test:

``` powershell
python -m src.llm_extractor
```

The configured provider order is Gemini, Groq, and DeepSeek. The test
confirmed Groq fallback after Gemini returned a temporary HTTP 503
response. Confirm that the configured Groq model meets the assignment's
Llama-model requirement before final submission.

## Processed Data Files

Typical processed files:

``` text
data/processed/startups.json
data/processed/products.json
data/processed/research_papers.json
data/processed/jobs.json
data/processed/news.json
data/processed/entity_mapping_log.json
data/processed/entity_resolution_summary.json
```

Raw source outputs are stored under `data/raw/`.

## Google Sheets

The project publishes six tabs to the configured workbook:

-   Startups
-   Products
-   Research Papers
-   Jobs
-   News
-   Entity Mapping Log

Workbook: [GraphOne Intelligence
Dataset](https://docs.google.com/spreadsheets/d/14q6kT4l72HsHL2cisX8Rv-fiM87viZlWMXAbMop0UzI/edit)

## Security

-   Do not commit `.env`.
-   Do not commit `credentials/` or service-account JSON files.
-   Keep API keys private.
-   Review `.gitignore` before pushing to GitHub.

## Known Limitations / Validation Notes

-   The recorded dataset counts are a snapshot, not a guarantee of
    future crawler output.
-   Entity resolution reported 8,953 exact matches and 15
    unmatched/empty mentions in the last run. Matching quality should be
    reviewed against representative samples; exact string matches do not
    automatically prove that two records refer to the same real-world
    entity.
-   GitHub repository associations and star counts require validation
    and a retrieval timestamp before being described as fully
    verified/current.
-   Job publication dates can be source-dependent and may sometimes be
    update dates.
-   LLM extraction fallback has been smoke-tested; extraction should be
    evaluated on representative real records before making quality
    claims.

## License

Add the license required by your project or assignment before public
release.

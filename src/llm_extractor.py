
import json
import logging
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types
from groq import Groq
from openai import OpenAI


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# Model IDs can be changed in .env without editing Python.
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL", "gemini-3.7-flash"
)

GROQ_MODEL = os.getenv(
    "GROQ_MODEL", "openai/gpt-oss-120b"
)

DEEPSEEK_MODEL = os.getenv(
    "DEEPSEEK_MODEL", "deepseek-flash"
)

gemini_client = (
    genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    if os.getenv("GEMINI_API_KEY")
    else None
)

groq_client = (
    Groq(api_key=os.getenv("GROQ_API_KEY"))
    if os.getenv("GROQ_API_KEY")
    else None
)

deepseek_client = (
    OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )
    if os.getenv("DEEPSEEK_API_KEY")
    else None
)


SYSTEM_PROMPT = """
You are a reliable structured data extraction assistant.

Extract information only from the supplied text.
Do not invent missing facts.
Use null for unavailable values.
Return valid JSON only.

Use this structure:
{
  "summary": "short summary",
  "entities": [
    {
      "name": "entity name",
      "entity_type": "organization/person/product/technology/location",
      "description": "fact supported by source"
    }
  ],
  "facts": []
}
"""


def parse_json_response(response_text):
    """Parse model output and reject invalid JSON."""

    if not response_text:
        raise ValueError("Model returned empty response")

    response_text = response_text.strip()

    # Remove markdown fences if a provider returns them.
    if response_text.startswith("```"):
        response_text = response_text.replace(
            "```json", "", 1
        )
        response_text = response_text.replace(
            "```", ""
        ).strip()

    return json.loads(response_text)


def call_gemini(text):
    if not gemini_client:
        raise RuntimeError("Gemini API key missing")

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=SYSTEM_PROMPT + "\n\nSOURCE TEXT:\n" + text,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0,
        ),
    )

    return parse_json_response(response.text)


def call_groq(text):
    if not groq_client:
        raise RuntimeError("Groq API key missing")

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    return parse_json_response(
        response.choices[0].message.content
    )


def call_deepseek(text):
    if not deepseek_client:
        raise RuntimeError("DeepSeek API key missing")

    response = deepseek_client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    return parse_json_response(
        response.choices[0].message.content
    )


PROVIDERS = [
    ("Gemini Flash", call_gemini),
    ("Groq", call_groq),
    ("DeepSeek", call_deepseek),
]


def get_error_status(error):
    """Read HTTP status from common SDK exceptions."""

    return (
        getattr(error, "status_code", None)
        or getattr(error, "code", None)
    )


def split_text(text):
    """Split long text near its midpoint."""

    midpoint = len(text) // 2

    split_at = text.rfind(" ", 0, midpoint)

    if split_at <= 0:
        split_at = midpoint

    return text[:split_at], text[split_at:]


def extract_structured(text, depth=0):
    """
    Provider fallback:
    Gemini -> Groq -> DeepSeek.

    Handles rate limits and large payloads.
    """

    if not text or not text.strip():
        return {
            "summary": "",
            "entities": [],
            "facts": [],
        }

    if depth > 8:
        raise RuntimeError("Maximum chunk depth reached")

    errors = []

    for provider_name, provider_function in PROVIDERS:

        logging.info(
            "Trying provider: %s",
            provider_name,
        )

        for attempt in range(3):

            try:
                result = provider_function(text)

                logging.info(
                    "Provider successful: %s",
                    provider_name,
                )

                result["_provider"] = provider_name

                return result

            except Exception as error:

                status = get_error_status(error)
                error_text = str(error).lower()

                # Handle HTTP 413 / payload too large.
                if (
                    status == 413
                    or "payload too large" in error_text
                    or "request entity too large" in error_text
                ):
                    logging.warning(
                        "%s returned 413. Splitting text.",
                        provider_name,
                    )

                    first, second = split_text(text)

                    result_first = extract_structured(
                        first, depth + 1
                    )

                    result_second = extract_structured(
                        second, depth + 1
                    )

                    return {
                        "summary": (
                            str(result_first.get("summary", ""))
                            + " "
                            + str(result_second.get("summary", ""))
                        ).strip(),
                        "entities": (
                            result_first.get("entities", [])
                            + result_second.get("entities", [])
                        ),
                        "facts": (
                            result_first.get("facts", [])
                            + result_second.get("facts", [])
                        ),
                        "_provider": "chunked_fallback",
                    }

                # Handle HTTP 429 rate limits.
                if (
                    status == 429
                    or "rate limit" in error_text
                    or "too many requests" in error_text
                ):
                    wait_seconds = 2 ** (attempt + 1)

                    logging.warning(
                        "%s rate limited. Retry %s/3 after %s sec.",
                        provider_name,
                        attempt + 1,
                        wait_seconds,
                    )

                    time.sleep(wait_seconds)
                    continue

                logging.error(
                    "%s failed: %s",
                    provider_name,
                    error,
                )

                errors.append(
                    f"{provider_name}: {error}"
                )

                # Other errors move to the next provider.
                break

    raise RuntimeError(
        "All LLM providers failed:\n"
        + "\n".join(errors)
    )


if __name__ == "__main__":
    sample_text = """
    GraphOne Intelligence is an AI data collection project.
    It collects startup, product, research paper, job and news data.
    """

    result = extract_structured(sample_text)

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )

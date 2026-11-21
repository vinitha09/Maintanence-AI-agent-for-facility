import json
import logging
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass
from urllib.parse import quote

import httpx


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
logger = logging.getLogger(__name__)


class AnswerGenerationError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise AnswerGenerationError(
            "Gemini API key is not configured. Set GEMINI_API_KEY in the backend environment."
        )
    return key


def _build_payload(question: str, matches: list[dict]) -> dict:
    if not matches:
        raise ValueError("Answer generation requires at least one source.")

    context_parts = []
    for match in matches:
        if match["source_type"] == "maintenance_log":
            source = (
                f"Maintenance log #{match['log_id']}, "
                f"{match['record_type']} record, "
                f"date {match['recorded_on']}"
            )
        else:
            source = f"Manual: {match['filename']}, page {match['page_number']}"
        context_parts.append(f"Source: {source}\nContent: {match['text']}")

    system_instruction = """
    You are an industrial maintenance assistant.

    Answer using only the supplied maintenance logs and manual excerpts.
    Consider the maintenance logs first, then use manuals to explain
    or verify relevant information.

    Write exactly two concise paragraphs:
    - Paragraph 1: synthesize the relevant events in natural, plain language
      and chronological order. Use dates such as "9 November 2026". It is
      fine to refer naturally to "the repair log", but do not narrate each
      log separately or repeat database-style IDs, record labels, or dates.
    - Paragraph 2: state what the records do not establish, such as the cause
      or whether a repair is permanent, and what further inspection is needed.

    Do not add a heading, bullets, citations, an "Insufficient information"
    closing line, or a Sources section. The application displays sources
    separately below the answer. Do not call an issue one-time or resolved
    permanently unless the sources explicitly establish that.

    Never invent repair procedures, measurements, or historical events.

    For hazardous maintenance, direct the worker to the approved
    procedure and a qualified technician.
    """

    context = "\n\n".join(context_parts)
    return {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            f"Worker's question:\n{question}\n\n"
                            "Retrieved machine maintenance history, followed "
                            f"by manual excerpts:\n{context}"
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 256,
        },
    }


def _endpoint(method: str) -> str:
    model = quote(GEMINI_MODEL, safe=".-")
    return f"{GEMINI_API_BASE_URL}/{model}:{method}"


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": _api_key(),
    }


def _raise_http_error(error: httpx.HTTPStatusError) -> AnswerGenerationError:
    status = error.response.status_code
    if status in (401, 403):
        message = "Gemini rejected the API key. Check GEMINI_API_KEY and its API access."
    elif status == 429:
        message = "Gemini request quota or rate limit was reached. Please try again later."
    elif status == 404:
        message = f"Gemini model '{GEMINI_MODEL}' was not found or is unavailable."
    else:
        message = f"Gemini returned HTTP {status} while generating an answer."
    return AnswerGenerationError(message)


def _response_text(result: dict) -> str:
    if not isinstance(result, dict):
        raise AnswerGenerationError("Gemini returned an invalid response.")
    candidates = result.get("candidates") or []
    if isinstance(candidates, list) and candidates:
        candidate = candidates[0]
        if not isinstance(candidate, dict):
            raise AnswerGenerationError("Gemini returned an invalid response.")
        content = candidate.get("content") or {}
        if not isinstance(content, dict):
            raise AnswerGenerationError("Gemini returned an invalid response.")
        parts = content.get("parts") or []
        answer = "".join(
            part.get("text", "")
            for part in parts
            if isinstance(part, dict) and not part.get("thought", False)
        )
        if answer.strip():
            return answer
    raise AnswerGenerationError(
        "Gemini returned no answer. The response may have been blocked or empty."
    )


@dataclass
class GeminiAnswerStream:
    client: httpx.Client
    response: httpx.Response
    metrics: dict | None = None

    def close(self) -> None:
        self.response.close()
        self.client.close()

    def tokens(self) -> Iterator[str]:
        try:
            for line in self.response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError as error:
                    raise AnswerGenerationError(
                        "Gemini returned an invalid streaming response."
                    ) from error

                if not isinstance(chunk, dict):
                    raise AnswerGenerationError(
                        "Gemini returned an invalid streaming response."
                    )
                if chunk.get("error"):
                    raise AnswerGenerationError(
                        "Gemini reported an error while generating the answer."
                    )

                usage = chunk.get("usageMetadata")
                if isinstance(usage, dict):
                    self.metrics = usage

                candidates = chunk.get("candidates") or []
                if isinstance(candidates, list) and candidates:
                    candidate = candidates[0]
                    if not isinstance(candidate, dict):
                        raise AnswerGenerationError(
                            "Gemini returned an invalid streaming response."
                        )
                    content = candidate.get("content") or {}
                    if not isinstance(content, dict):
                        raise AnswerGenerationError(
                            "Gemini returned an invalid streaming response."
                        )
                    for part in content.get("parts") or []:
                        if not isinstance(part, dict):
                            continue
                        text = part.get("text", "")
                        if text and not part.get("thought", False):
                            yield text
        except httpx.HTTPError as error:
            raise AnswerGenerationError(
                "The Gemini answer stream was interrupted."
            ) from error


def open_answer_stream(
    question: str,
    matches: list[dict],
) -> GeminiAnswerStream:
    headers = _headers()
    client = httpx.Client(timeout=180.0)
    try:
        request = client.build_request(
            "POST",
            _endpoint("streamGenerateContent") + "?alt=sse",
            headers=headers,
            json=_build_payload(question, matches),
        )
        response = client.send(request, stream=True)
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        client.close()
        raise _raise_http_error(error) from error
    except httpx.RequestError as error:
        client.close()
        raise AnswerGenerationError(
            "Could not connect to the Gemini API. Check the backend's internet access."
        ) from error
    except (TypeError, ValueError):
        client.close()
        raise
    return GeminiAnswerStream(client=client, response=response)


def log_generation_metrics(result: dict, started_at: float) -> None:
    elapsed = time.perf_counter() - started_at
    usage = result if isinstance(result, dict) else {}
    logger.info(
        "Gemini generation completed in %.2f seconds (prompt tokens: %s, "
        "candidate tokens: %s).",
        elapsed,
        usage.get("promptTokenCount"),
        usage.get("candidatesTokenCount"),
    )


def generate_answer(question: str, matches: list[dict]) -> str:
    headers = _headers()
    payload = _build_payload(question, matches)
    started_at = time.perf_counter()
    try:
        response = httpx.post(
            _endpoint("generateContent"),
            headers=headers,
            json=payload,
            timeout=180.0,
        )
        response.raise_for_status()
        result = response.json()
    except httpx.HTTPStatusError as error:
        raise _raise_http_error(error) from error
    except httpx.RequestError as error:
        raise AnswerGenerationError(
            "Could not connect to the Gemini API. Check the backend's internet access."
        ) from error
    except (httpx.DecodingError, json.JSONDecodeError) as error:
        raise AnswerGenerationError(
            "Gemini returned an invalid response."
        ) from error

    answer = _response_text(result)
    usage = result.get("usageMetadata") or {}
    log_generation_metrics(usage, started_at)
    return answer


import json
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass

import httpx


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")


class AnswerGenerationError(RuntimeError):
    pass


def _build_payload(question: str, matches: list[dict], stream: bool) -> dict:
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
            source = (
                f"Manual: {match['filename']}, "
                f"page {match['page_number']}"
            )

        context_parts.append(
            f"Source: {source}\nContent: {match['text']}"
        )

    context = "\n\n".join(context_parts)

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

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_instruction
            },
            {
                "role": "user",
                "content": (
                    f"Worker's question:\n{question}\n\n"
                    f"Retrieved machine maintenance history, followed "
                    f"by manual excerpts:\n{context}"
                )
            }
        ],
        "stream": stream,
        "options": {
            "temperature": 0.2,
            "num_predict": 256
        }
    }
    return payload


def _raise_http_error(error: httpx.HTTPStatusError) -> AnswerGenerationError:
    detail = error.response.text.strip()
    message = (
        f"Ollama returned HTTP {error.response.status_code}. "
        "Verify OLLAMA_BASE_URL and that OLLAMA_MODEL is available."
    )
    if detail:
        message = f"{message} {detail[:500]}"
    return AnswerGenerationError(message)


@dataclass
class OllamaAnswerStream:
    client: httpx.Client
    response: httpx.Response
    metrics: dict | None = None

    def close(self) -> None:
        self.response.close()
        self.client.close()

    def tokens(self) -> Iterator[str]:
        try:
            for line in self.response.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError as error:
                    raise AnswerGenerationError(
                        "Ollama returned an invalid streaming response."
                    ) from error
                if chunk.get("error"):
                    raise AnswerGenerationError(str(chunk["error"]))

                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content

                if chunk.get("done"):
                    self.metrics = chunk
                    return
        except httpx.HTTPError as error:
            raise AnswerGenerationError(
                "The Ollama stream was interrupted."
            ) from error


def open_answer_stream(
    question: str,
    matches: list[dict],
) -> OllamaAnswerStream:
    client = httpx.Client(timeout=180.0)
    try:
        request = client.build_request(
            "POST",
            f"{OLLAMA_BASE_URL}/api/chat",
            json=_build_payload(question, matches, stream=True),
        )
        response = client.send(request, stream=True)
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        client.close()
        raise _raise_http_error(error) from error
    except httpx.RequestError as error:
        client.close()
        raise AnswerGenerationError(
            "Could not connect to Ollama. Verify that it is running and "
            "that OLLAMA_BASE_URL is correct."
        ) from error
    except (TypeError, ValueError):
        client.close()
        raise
    return OllamaAnswerStream(client=client, response=response)


def log_generation_metrics(result: dict, started_at: float) -> None:
    print("Load duration:",
        result.get("load_duration", 0) / 1e9, "seconds")

    print("Prompt tokens:", result.get("prompt_eval_count"))

    print("Generated tokens:", result.get("eval_count"))

    print(
        "Tokens per second:",
        result.get("eval_count", 0) / (result.get("eval_duration", 1) / 1e9),
    )

    elapsed = time.perf_counter() - started_at

    print(f"Ollama request time: {elapsed:.2f} seconds")

    print(
        f"Prompt evaluation: "
        f"{result.get('prompt_eval_duration', 0) / 1e9:.2f} seconds"
    )

    print(
        f"Answer generation: "
        f"{result.get('eval_duration', 0) / 1e9:.2f} seconds"
    )


def generate_answer(question: str, matches: list[dict]) -> str:
    payload = _build_payload(question, matches, stream=False)
    start_time = time.perf_counter()
    try:
        response = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=180.0,
        )
        response.raise_for_status()
        result = response.json()
        log_generation_metrics(result, start_time)
        answer = result.get("message", {}).get("content")
        if not answer:
            return "The AI could not generate an answer. Please try again."
        return answer
    except httpx.HTTPStatusError as error:
        raise _raise_http_error(error) from error
    except httpx.RequestError as error:
        raise AnswerGenerationError(
            "Could not connect to Ollama. Verify that it is running and "
            "that OLLAMA_BASE_URL is correct."
        ) from error
    except httpx.HTTPError as error:
        raise AnswerGenerationError("The Ollama request failed.") from error

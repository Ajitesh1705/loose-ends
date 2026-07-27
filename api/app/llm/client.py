"""The one module every LLM call goes through (plan.md §OpenAI usage rules).

Owns:
  - retries with exponential backoff (3 attempts) on transient API errors
  - a per-request timeout
  - a schema-repair pass (one retry, feeding the validation error back) before giving up
  - response caching by sha256(prompt_version + model + input) in `llm_cache`
  - token / latency / cost logging to `llm_calls`

Structured calls use the **Responses API with a strict JSON schema** (via
`responses.parse(text_format=...)`, which converts the Pydantic model to a strict schema
and guarantees schema-conformant output). We never parse free text; we never use
json_mode.

Cache and log writes use their own short-lived sessions so they persist independently of
the caller's transaction.
"""

import hashlib
import json
import time
from typing import TypeVar

from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.models import LLMCache, LLMCall

T = TypeVar("T", bound=BaseModel)

MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_S = 45.0

# Approximate USD per 1M tokens (input, output). Cost logging is best-effort; update
# alongside OpenAI's pricing. Unknown models log null cost rather than a wrong number.
PRICING = {
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
}


def _cost(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    price = PRICING.get(model)
    if price is None:
        return None
    return prompt_tokens / 1e6 * price[0] + completion_tokens / 1e6 * price[1]


def _cache_key(prompt_version: str, model: str, payload: str) -> str:
    return hashlib.sha256(f"{prompt_version}|{model}|{payload}".encode()).hexdigest()


class LLMClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.client = OpenAI(
            api_key=self.settings.openai_api_key,
            timeout=REQUEST_TIMEOUT_S,
            max_retries=0,  # we own retries
        )

    # --- cache / logging (independent sessions) ---
    def _cache_get(self, key: str) -> dict | None:
        with SessionLocal() as db:
            row = db.get(LLMCache, key)
            return row.response if row else None

    def _cache_set(self, key: str, response: dict) -> None:
        with SessionLocal() as db:
            if db.get(LLMCache, key) is None:
                db.add(LLMCache(key=key, response=response))
                db.commit()

    def _log(self, **kwargs) -> None:
        with SessionLocal() as db:
            db.add(LLMCall(**kwargs))
            db.commit()

    # --- structured (Responses API, strict schema) ---
    def structured(
        self,
        *,
        kind: str,
        model: str,
        system: str,
        user: str,
        schema: type[T],
        temperature: float,
    ) -> T:
        key = _cache_key(self.settings.prompt_version, model, f"{system}\n----\n{user}")
        cached = self._cache_get(key)
        if cached is not None:
            self._log(
                kind=kind,
                model=model,
                prompt_version=self.settings.prompt_version,
                cache_hit=True,
            )
            return schema.model_validate(cached)

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        last_err: Exception | None = None

        for attempt in range(MAX_ATTEMPTS):
            try:
                t0 = time.monotonic()
                resp = self.client.responses.parse(
                    model=model,
                    input=messages,
                    text_format=schema,
                    temperature=temperature,
                )
                latency_ms = int((time.monotonic() - t0) * 1000)
                parsed = resp.output_parsed
                if parsed is None:
                    raise ValueError("empty parsed output (possible refusal)")

                usage = resp.usage
                p_tok = getattr(usage, "input_tokens", None)
                c_tok = getattr(usage, "output_tokens", None)
                self._log(
                    kind=kind,
                    model=model,
                    prompt_version=self.settings.prompt_version,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    latency_ms=latency_ms,
                    cost_usd=_cost(model, p_tok or 0, c_tok or 0),
                    repaired=attempt > 0,
                )
                self._cache_set(key, parsed.model_dump(mode="json"))
                return parsed

            except (
                RateLimitError,
                APITimeoutError,
                APIConnectionError,
                InternalServerError,
            ) as e:
                last_err = e
                time.sleep(2**attempt)  # 1s, 2s, 4s
                continue
            except (ValidationError, ValueError) as e:
                # schema-repair pass: one retry with the error fed back
                last_err = e
                if attempt == 0:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Your previous response failed validation: "
                                f"{e}. Return JSON matching the schema exactly."
                            ),
                        }
                    )
                    continue
                break

        self._log(
            kind=kind,
            model=model,
            prompt_version=self.settings.prompt_version,
            error=str(last_err),
        )
        raise RuntimeError(f"LLM {kind} call failed after retries: {last_err}")

    # --- embeddings ---
    def embed(self, text: str) -> list[float]:
        model = self.settings.openai_model_embed
        key = _cache_key(self.settings.prompt_version, model, text)
        cached = self._cache_get(key)
        if cached is not None:
            self._log(kind="embed", model=model, cache_hit=True)
            return cached["embedding"]

        last_err: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                t0 = time.monotonic()
                resp = self.client.embeddings.create(model=model, input=text)
                latency_ms = int((time.monotonic() - t0) * 1000)
                vec = resp.data[0].embedding
                p_tok = resp.usage.prompt_tokens
                self._log(
                    kind="embed",
                    model=model,
                    prompt_tokens=p_tok,
                    completion_tokens=0,
                    latency_ms=latency_ms,
                    cost_usd=_cost(model, p_tok, 0),
                )
                self._cache_set(key, {"embedding": vec})
                return vec
            except (
                RateLimitError,
                APITimeoutError,
                APIConnectionError,
                InternalServerError,
            ) as e:
                last_err = e
                time.sleep(2**attempt)

        self._log(kind="embed", model=model, error=str(last_err))
        raise RuntimeError(f"LLM embed call failed after retries: {last_err}")


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client

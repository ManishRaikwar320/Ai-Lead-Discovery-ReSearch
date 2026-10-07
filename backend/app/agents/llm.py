from functools import lru_cache
from time import sleep

from langchain_groq import ChatGroq
from pydantic import BaseModel

from app.config import get_settings


@lru_cache
def get_llm() -> ChatGroq:
    settings = get_settings()

    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0,
    )


def invoke_structured(
    schema: type[BaseModel],
    prompt: str,
    *,
    retries: int | None = None,
    backoff: float | None = None,
) -> BaseModel:
    """Invoke the LLM with a JSON schema, retrying transient failures."""
    settings = get_settings()

    attempts = (settings.max_retries if retries is None else retries) + 1
    delay = settings.retry_backoff if backoff is None else backoff

    structured_llm = get_llm().with_structured_output(
        schema,
        method="json_mode",
    )

    last_error: Exception | None = None

    for attempt in range(max(1, attempts)):
        try:
            return structured_llm.invoke(prompt)
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller
            last_error = exc

            if attempt < attempts - 1 and delay > 0:
                sleep(min(delay * (2**attempt), 30))

    raise last_error  # type: ignore[misc]

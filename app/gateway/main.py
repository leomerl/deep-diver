"""The AI gateway: POST /v1/chat on top of the Anthropic API. Run: uvicorn app.gateway.main:app --port 8080

The app talks only to this contract; provider, keys, provider retries, prompt caching and refusal fallbacks
live here.
"""
import hmac
from collections.abc import Callable
from functools import cache, partial
from typing import Annotated

import anthropic
from fastapi import Depends, FastAPI, Header, HTTPException, status
from sqlmodel import create_engine

from app.llm.gateway_contract import CHAT_PATH, Caller, ChatRequest, ChatResponse, Usage

from .from_anthropic import from_anthropic
from .record_call import record_call
from .settings import DATABASE_URL, GATEWAY_KEY
from .to_anthropic import anthropic_messages, anthropic_tools, output_config, system_prompt

# On a policy refusal the API re-runs the request on a fallback model it picks by refusal category.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODE = "default"
BEARER_PREFIX = "Bearer "

type Recorder = Callable[[str, Usage, Caller | None], None]  # (model, usage, caller)

app = FastAPI(title="deep-diver AI gateway")


@cache
def get_client() -> anthropic.Anthropic:
    # Reads ANTHROPIC_API_KEY; retries 429/5xx/connection errors itself (max_retries=2 by default).
    return anthropic.Anthropic()


def check_key(authorization: Annotated[str | None, Header()] = None) -> None:
    if not GATEWAY_KEY:
        return
    # compare_digest: a plain == leaks, through timing, how many leading characters matched.
    if not hmac.compare_digest(authorization or "", f"{BEARER_PREFIX}{GATEWAY_KEY}"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid gateway key")


@cache
def get_recorder() -> Recorder:
    return partial(record_call, create_engine(DATABASE_URL))


ClientDep = Annotated[anthropic.Anthropic, Depends(get_client)]
RecorderDep = Annotated[Recorder, Depends(get_recorder)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(CHAT_PATH, dependencies=[Depends(check_key)])
def chat(request: ChatRequest, client: ClientDep, record: RecorderDep) -> ChatResponse:
    """One model turn. 4xx = the request is wrong (don't retry); 429/502 = retry later."""
    try:
        message = client.beta.messages.create(
            model=request.model,
            max_tokens=request.max_tokens,
            system=system_prompt(request.messages),
            messages=anthropic_messages(request.messages),
            tools=anthropic_tools(request.tools),
            output_config=output_config(request.response_schema),
            # Agents resend the whole history every turn; caching it makes each later turn far cheaper.
            cache_control={"type": "ephemeral"},
            betas=[FALLBACK_BETA],
            fallbacks=FALLBACK_MODE,
        )
    except anthropic.RateLimitError as e:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, e.message) from e
    except anthropic.BadRequestError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, e.message) from e
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"provider error: {e}") from e
    try:
        response = from_anthropic(message)
    except ValueError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    # message.model, not request.model: a refusal fallback answers with a different model and its own rates.
    record(message.model, response.usage, request.caller)
    return response

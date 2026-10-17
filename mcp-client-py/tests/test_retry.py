"""RetryPolicy behaviour: retries retryable errors, fails fast otherwise."""

from __future__ import annotations

import pytest

from mcp_client.utils.retry import RetryPolicy


async def test_retries_until_success() -> None:
    attempts = {"n": 0}

    async def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ConnectionError("transient")
        return "ok"

    policy = RetryPolicy(
        max_retries=3,
        base_delay=0.0,
        max_delay=0.0,
        jitter=False,
        retryable_exceptions=(ConnectionError,),
        non_retryable_exceptions=(ValueError,),
    )
    assert await policy.execute(flaky) == "ok"
    assert attempts["n"] == 3


async def test_non_retryable_error_fails_immediately() -> None:
    attempts = {"n": 0}

    async def broken() -> str:
        attempts["n"] += 1
        raise ValueError("permanent")

    policy = RetryPolicy(
        max_retries=3,
        base_delay=0.0,
        max_delay=0.0,
        jitter=False,
        retryable_exceptions=(ConnectionError,),
        non_retryable_exceptions=(ValueError,),
    )
    with pytest.raises(ValueError):
        await policy.execute(broken)
    assert attempts["n"] == 1


async def test_gives_up_after_max_retries() -> None:
    attempts = {"n": 0}

    async def always_down() -> str:
        attempts["n"] += 1
        raise ConnectionError("down")

    policy = RetryPolicy(
        max_retries=2,
        base_delay=0.0,
        max_delay=0.0,
        jitter=False,
        retryable_exceptions=(ConnectionError,),
    )
    with pytest.raises(ConnectionError):
        await policy.execute(always_down)
    assert attempts["n"] == 3  # first attempt + 2 retries

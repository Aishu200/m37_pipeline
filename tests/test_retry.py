import asyncio

import pytest

from mention_pipeline.exceptions import (
    InvalidRequestError,
    RateLimitError,
    RetryableError,
)
from mention_pipeline.retry import RetryHandler


# ============================================================
# Helpers
# ============================================================


async def successful_operation(value: str) -> str:
    return f"processed-{value}"


# ============================================================
# Constructor validation
# ============================================================


def test_max_attempts_must_be_at_least_one():
    with pytest.raises(ValueError, match="max_attempts"):
        RetryHandler(max_attempts=0)


def test_base_delay_cannot_be_negative():
    with pytest.raises(ValueError, match="base_delay"):
        RetryHandler(base_delay=-1)


def test_max_delay_must_be_greater_than_or_equal_to_base_delay():
    with pytest.raises(ValueError, match="max_delay"):
        RetryHandler(
            base_delay=10,
            max_delay=5,
        )


def test_equal_base_and_max_delay_is_allowed():
    handler = RetryHandler(
        base_delay=5,
        max_delay=5,
    )

    assert handler.base_delay == 5
    assert handler.max_delay == 5


# ============================================================
# Successful execution
# ============================================================


def test_successful_operation_does_not_retry():
    calls = 0

    async def operation(value: str) -> str:
        nonlocal calls
        calls += 1
        return f"processed-{value}"

    handler = RetryHandler(
        max_attempts=3,
        base_delay=0,
    )

    result = asyncio.run(
        handler.execute(operation, "test")
    )

    assert result == "processed-test"
    assert calls == 1


# ============================================================
# Retry behavior
# ============================================================


def test_retryable_error_is_retried(monkeypatch):
    calls = 0
    sleep_calls = []

    async def operation(value: str) -> str:
        nonlocal calls

        calls += 1

        if calls < 3:
            raise RetryableError("temporary failure")

        return "success"

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)

    monkeypatch.setattr(
        "mention_pipelines.retry.asyncio.sleep",
        fake_sleep,
    )

    monkeypatch.setattr(
        "mention_pipelines.retry.random.uniform",
        lambda start, end: 0,
    )

    handler = RetryHandler(
        max_attempts=3,
        base_delay=1,
        max_delay=30,
    )

    result = asyncio.run(
        handler.execute(operation, "test")
    )

    assert result == "success"
    assert calls == 3
    assert sleep_calls == [1, 2]


def test_retryable_error_exhausts_attempts(monkeypatch):
    calls = 0
    sleep_calls = []

    async def operation(value: str) -> str:
        nonlocal calls
        calls += 1
        raise RetryableError("temporary failure")

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)

    monkeypatch.setattr(
        "mention_pipelines.retry.asyncio.sleep",
        fake_sleep,
    )

    monkeypatch.setattr(
        "mention_pipelines.retry.random.uniform",
        lambda start, end: 0,
    )

    handler = RetryHandler(
        max_attempts=3,
        base_delay=1,
        max_delay=30,
    )

    with pytest.raises(RetryableError, match="temporary failure"):
        asyncio.run(
            handler.execute(operation, "test")
        )

    assert calls == 3
    assert sleep_calls == [1, 2]


def test_max_attempts_one_does_not_retry(monkeypatch):
    calls = 0
    sleep_calls = []

    async def operation(value: str) -> str:
        nonlocal calls
        calls += 1
        raise RetryableError("temporary failure")

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)

    monkeypatch.setattr(
        "mention_pipelines.retry.asyncio.sleep",
        fake_sleep,
    )

    handler = RetryHandler(
        max_attempts=1,
        base_delay=1,
    )

    with pytest.raises(RetryableError):
        asyncio.run(
            handler.execute(operation, "test")
        )

    assert calls == 1
    assert sleep_calls == []


# ============================================================
# Exponential backoff
# ============================================================


def test_exponential_backoff(monkeypatch):
    sleep_calls = []

    async def operation(value: str) -> str:
        raise RetryableError("temporary failure")

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)

    monkeypatch.setattr(
        "mention_pipelines.retry.asyncio.sleep",
        fake_sleep,
    )

    # Remove jitter from the calculation.
    monkeypatch.setattr(
        "mention_pipelines.retry.random.uniform",
        lambda start, end: 0,
    )

    handler = RetryHandler(
        max_attempts=4,
        base_delay=2,
        max_delay=100,
    )

    with pytest.raises(RetryableError):
        asyncio.run(
            handler.execute(operation, "test")
        )

    assert sleep_calls == [
        2,
        4,
        8,
    ]


def test_backoff_respects_max_delay(monkeypatch):
    sleep_calls = []

    async def operation(value: str) -> str:
        raise RetryableError("temporary failure")

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)

    monkeypatch.setattr(
        "mention_pipelines.retry.asyncio.sleep",
        fake_sleep,
    )

    monkeypatch.setattr(
        "mention_pipelines.retry.random.uniform",
        lambda start, end: 0,
    )

    handler = RetryHandler(
        max_attempts=5,
        base_delay=10,
        max_delay=15,
    )

    with pytest.raises(RetryableError):
        asyncio.run(
            handler.execute(operation, "test")
        )

    assert sleep_calls == [
        10,
        15,
        15,
        15,
    ]


# ============================================================
# Jitter
# ============================================================


def test_jitter_is_added_to_backoff(monkeypatch):
    sleep_calls = []

    async def operation(value: str) -> str:
        raise RetryableError("temporary failure")

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)

    monkeypatch.setattr(
        "mention_pipelines.retry.asyncio.sleep",
        fake_sleep,
    )

    # Always return the maximum jitter.
    monkeypatch.setattr(
        "mention_pipelines.retry.random.uniform",
        lambda start, end: end,
    )

    handler = RetryHandler(
        max_attempts=3,
        base_delay=10,
        max_delay=30,
    )

    with pytest.raises(RetryableError):
        asyncio.run(
            handler.execute(operation, "test")
        )

    # Attempt 1:
    # base delay = 10
    # jitter = 10 * 0.1 = 1
    # total = 11
    #
    # Attempt 2:
    # base delay = 20
    # jitter = 20 * 0.1 = 2
    # total = 22

    assert sleep_calls == [
        11,
        22,
    ]


# ============================================================
# RateLimitError retry_after
# ============================================================


def test_rate_limit_retry_after_is_respected(monkeypatch):
    sleep_calls = []
    calls = 0

    async def operation(value: str) -> str:
        nonlocal calls

        calls += 1

        if calls == 1:
            raise RateLimitError(retry_after=7)

        return "success"

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)

    monkeypatch.setattr(
        "mention_pipelines.retry.asyncio.sleep",
        fake_sleep,
    )

    handler = RetryHandler(
        max_attempts=3,
        base_delay=1,
        max_delay=30,
    )

    result = asyncio.run(
        handler.execute(operation, "test")
    )

    assert result == "success"
    assert calls == 2
    assert sleep_calls == [7]


# ============================================================
# Non-retryable exceptions
# ============================================================


def test_non_retryable_exception_is_not_retried(monkeypatch):
    calls = 0
    sleep_calls = []

    async def operation(value: str) -> str:
        nonlocal calls

        calls += 1
        raise InvalidRequestError("invalid request")

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)

    monkeypatch.setattr(
        "mention_pipelines.retry.asyncio.sleep",
        fake_sleep,
    )

    handler = RetryHandler(
        max_attempts=3,
        base_delay=1,
    )

    with pytest.raises(
        InvalidRequestError,
        match="invalid request",
    ):
        asyncio.run(
            handler.execute(operation, "test")
        )

    assert calls == 1
    assert sleep_calls == []


# ============================================================
# Input / output propagation
# ============================================================


def test_operation_receives_input():
    received_value = None

    async def operation(value: str) -> str:
        nonlocal received_value
        received_value = value
        return "done"

    handler = RetryHandler()

    result = asyncio.run(
        handler.execute(operation, "hello")
    )

    assert result == "done"
    assert received_value == "hello"


def test_operation_output_is_returned():
    async def operation(value: str) -> dict:
        return {
            "value": value,
            "status": "success",
        }

    handler = RetryHandler()

    result = asyncio.run(
        handler.execute(operation, "test")
    )

    assert result == {
        "value": "test",
        "status": "success",
    }


# ============================================================
# Internal backoff calculation
# ============================================================


def test_calculate_delay_without_jitter(monkeypatch):
    monkeypatch.setattr(
        "mention_pipelines.retry.random.uniform",
        lambda start, end: 0,
    )

    handler = RetryHandler(
        base_delay=2,
        max_delay=30,
    )

    assert handler._calculate_delay(1) == 2
    assert handler._calculate_delay(2) == 4
    assert handler._calculate_delay(3) == 8
    assert handler._calculate_delay(4) == 16
    assert handler._calculate_delay(5) == 30

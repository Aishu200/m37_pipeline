import asyncio
from datetime import datetime, timezone

import pytest

from mention_pipeline.concurrency import ConcurrentBatchProcessor
from mention_pipeline.models import Batch, BatchResult, LLMResponse, Mention
from mention_pipeline.retry import RetryHandler


def create_mention(
    mention_id: str,
    tenant_id: str = "tenant-a",
) -> Mention:
    return Mention(
        id=mention_id,
        tenant_id=tenant_id,
        source="test-source",
        published_at=datetime.now(timezone.utc),
        title="Test mention",
        body="Test mention body",
    )


def create_batch(
    batch_id: str,
    tenant_id: str = "tenant-a",
) -> Batch:
    return Batch(
        tenant_id=tenant_id,
        mentions=[
            create_mention(
                mention_id=batch_id,
                tenant_id=tenant_id,
            )
        ],
        token_count=10,
    )


# ============================================================
# Constructor tests
# ============================================================


def test_max_concurrency_must_be_at_least_one():
    with pytest.raises(ValueError, match="max_concurrency"):
        ConcurrentBatchProcessor(
            client=None,
            retry_handler=None,
            max_concurrency=0,
        )


def test_max_concurrency_negative_value_is_rejected():
    with pytest.raises(ValueError, match="max_concurrency"):
        ConcurrentBatchProcessor(
            client=None,
            retry_handler=None,
            max_concurrency=-1,
        )


# ============================================================
# Empty input
# ============================================================


def test_empty_batches_returns_empty_list():
    processor = ConcurrentBatchProcessor(
        client=None,
        retry_handler=None,
        max_concurrency=2,
    )

    result = asyncio.run(
        processor.process_batches([])
    )

    assert result == []


# ============================================================
# Basic processing
# ============================================================


def test_process_single_batch():
    calls = []

    class FakeClient:
        async def enrich(self, mentions):
            calls.append(mentions)

            return BatchResult(
                results=[],
                prompt_tokens=10,
                completion_tokens=50,
            )

    processor = ConcurrentBatchProcessor(
        client=FakeClient(),
        retry_handler=RetryHandler(
            max_attempts=1,
        ),
        max_concurrency=2,
    )

    batch = create_batch("mention-1")

    result = asyncio.run(
        processor.process_batch(batch)
    )

    assert len(result.results) == 0
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 50

    assert len(calls) == 1
    assert calls[0] == batch.mentions


def test_process_multiple_batches():
    processed_batches = []

    class FakeClient:
        async def enrich(self, mentions):
            processed_batches.append(mentions)

            return BatchResult(
                results=[],
                prompt_tokens=10,
                completion_tokens=50,
            )

    processor = ConcurrentBatchProcessor(
        client=FakeClient(),
        retry_handler=RetryHandler(
            max_attempts=1,
        ),
        max_concurrency=2,
    )

    batches = [
        create_batch("mention-1"),
        create_batch("mention-2"),
        create_batch("mention-3"),
    ]

    results = asyncio.run(
        processor.process_batches(batches)
    )

    assert len(results) == 3
    assert len(processed_batches) == 3


# ============================================================
# Result collection
# ============================================================


def test_results_are_returned_for_each_batch():
    class FakeClient:
        async def enrich(self, mentions):
            return BatchResult(
                results=[
                    LLMResponse(
                        id=mentions[0].id,
                        tenant_id=mentions[0].tenant_id,
                        sentiment="positive",
                        summary="Test summary",
                        topics=["topicA"],
                    )
                ],
                prompt_tokens=10,
                completion_tokens=50,
            )

    processor = ConcurrentBatchProcessor(
        client=FakeClient(),
        retry_handler=RetryHandler(
            max_attempts=1,
        ),
        max_concurrency=2,
    )

    batches = [
        create_batch("mention-1"),
        create_batch("mention-2"),
        create_batch("mention-3"),
    ]

    results = asyncio.run(
        processor.process_batches(batches)
    )

    assert len(results) == 3

    assert results[0].results[0].id == "mention-1"
    assert results[1].results[0].id == "mention-2"
    assert results[2].results[0].id == "mention-3"


# ============================================================
# Concurrency limit
# ============================================================


def test_concurrency_does_not_exceed_limit():
    active_calls = 0
    maximum_active_calls = 0

    async def fake_enrich(mentions):
        nonlocal active_calls
        nonlocal maximum_active_calls

        active_calls += 1

        maximum_active_calls = max(
            maximum_active_calls,
            active_calls,
        )

        await asyncio.sleep(0.01)

        active_calls -= 1

        return BatchResult(
            results=[],
            prompt_tokens=10,
            completion_tokens=50,
        )

    class FakeClient:
        enrich = staticmethod(fake_enrich)

    max_concurrency = 2

    processor = ConcurrentBatchProcessor(
        client=FakeClient(),
        retry_handler=RetryHandler(
            max_attempts=1,
        ),
        max_concurrency=max_concurrency,
    )

    batches = [
        create_batch("mention-1"),
        create_batch("mention-2"),
        create_batch("mention-3"),
        create_batch("mention-4"),
        create_batch("mention-5"),
    ]

    results = asyncio.run(
        processor.process_batches(batches)
    )

    assert len(results) == 5
    assert maximum_active_calls <= max_concurrency


def test_concurrency_one_processes_only_one_batch_at_a_time():
    active_calls = 0
    maximum_active_calls = 0

    async def fake_enrich(mentions):
        nonlocal active_calls
        nonlocal maximum_active_calls

        active_calls += 1

        maximum_active_calls = max(
            maximum_active_calls,
            active_calls,
        )

        await asyncio.sleep(0.01)

        active_calls -= 1

        return BatchResult(
            results=[],
            prompt_tokens=10,
            completion_tokens=50,
        )

    class FakeClient:
        enrich = staticmethod(fake_enrich)

    processor = ConcurrentBatchProcessor(
        client=FakeClient(),
        retry_handler=RetryHandler(
            max_attempts=1,
        ),
        max_concurrency=1,
    )

    batches = [
        create_batch("mention-1"),
        create_batch("mention-2"),
        create_batch("mention-3"),
    ]

    results = asyncio.run(
        processor.process_batches(batches)
    )

    assert len(results) == 3
    assert maximum_active_calls == 1


# ============================================================
# RetryHandler integration
# ============================================================


def test_retry_handler_is_used():
    client_calls = 0

    class FakeClient:
        async def enrich(self, mentions):
            nonlocal client_calls

            client_calls += 1

            return BatchResult(
                results=[],
                prompt_tokens=10,
                completion_tokens=50,
            )

    class FakeRetryHandler:
        def __init__(self):
            self.calls = 0

        async def execute(self, operation, value):
            self.calls += 1
            return await operation(value)

    retry_handler = FakeRetryHandler()

    processor = ConcurrentBatchProcessor(
        client=FakeClient(),
        retry_handler=retry_handler,
        max_concurrency=2,
    )

    batch = create_batch("mention-1")

    result = asyncio.run(
        processor.process_batch(batch)
    )

    assert isinstance(result, BatchResult)
    assert retry_handler.calls == 1
    assert client_calls == 1


# ============================================================
# Retry behavior through processor
# ============================================================


def test_failed_retryable_call_is_retried():
    calls = 0

    from mention_pipeline.exceptions import RetryableError

    class FakeClient:
        async def enrich(self, mentions):
            nonlocal calls

            calls += 1

            if calls < 3:
                raise RetryableError("temporary failure")

            return BatchResult(
                results=[],
                prompt_tokens=10,
                completion_tokens=50,
            )

    processor = ConcurrentBatchProcessor(
        client=FakeClient(),
        retry_handler=RetryHandler(
            max_attempts=3,
            base_delay=0,
        ),
        max_concurrency=1,
    )

    batch = create_batch("mention-1")

    result = asyncio.run(
        processor.process_batch(batch)
    )

    assert isinstance(result, BatchResult)
    assert calls == 3


# ============================================================
# Error propagation
# ============================================================


def test_non_retryable_error_propagates():
    from mention_pipeline.exceptions import InvalidRequestError

    class FakeClient:
        async def enrich(self, mentions):
            raise InvalidRequestError("invalid request")

    processor = ConcurrentBatchProcessor(
        client=FakeClient(),
        retry_handler=RetryHandler(
            max_attempts=3,
            base_delay=0,
        ),
        max_concurrency=1,
    )

    batch = create_batch("mention-1")

    with pytest.raises(
        InvalidRequestError,
        match="invalid request",
    ):
        asyncio.run(
            processor.process_batch(batch)
        )
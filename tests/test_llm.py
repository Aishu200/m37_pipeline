
import asyncio
from datetime import datetime, timezone

import pytest

from mention_pipeline.config import BasicConfig
from mention_pipeline.exceptions import (
    BatchSizeError,
    InvalidRequestError,
    RateLimitError,
    TokenLimitExceeded,
    UpstreamError,
)
from mention_pipeline.llm import (
    MockLLMClient,
)
from mention_pipeline.models import LLMResponse, Mention


def create_mention(
    mention_id: str,
    tenant_id: str = "tenant-a",
    tokens: int = 100,
) -> Mention:
    """
    Create a mention with a predictable token count.

    Mention.tokens = len(title + body) // 4
    """
    return Mention(
        id=mention_id,
        tenant_id=tenant_id,
        source="test-source",
        published_at=datetime.now(timezone.utc),
        title="",
        body="x" * (tokens * 4),
    )


def find_id_for_outcome(start: int, end: int) -> str:
    """
    Find a deterministic mention ID whose MD5 hash produces
    an outcome in the requested range.
    """
    for index in range(10000):
        mention_id = f"test-id-{index}"

        hashed = MockLLMClient.calculate_deterministic_hash(
            mention_id
        )

        outcome = hashed % 100

        if start <= outcome < end:
            return mention_id

    raise AssertionError(
        f"Could not find an ID for outcome range {start}-{end}"
    )


# ============================================================
# Batch validation tests
# ============================================================


def test_empty_batch_raises_invalid_request():
    client = MockLLMClient(latency=0)

    with pytest.raises(InvalidRequestError):
        asyncio.run(client.enrich([]))


def test_batch_size_limit_is_enforced():
    max_items = BasicConfig.MAX_BATCH_ITEM_QUANTITY.value

    mentions = [
        create_mention(f"mention-{index}")
        for index in range(max_items + 1)
    ]

    client = MockLLMClient(latency=0)

    with pytest.raises(BatchSizeError):
        asyncio.run(client.enrich(mentions))


def test_token_limit_is_enforced():
    max_tokens = BasicConfig.BATCH_TOKEN_THRESHOLD.value

    mentions = [
        create_mention(
            "mention-001",
            tokens=max_tokens + 1,
        )
    ]

    client = MockLLMClient(latency=0)

    with pytest.raises(TokenLimitExceeded):
        asyncio.run(client.enrich(mentions))


def test_exact_batch_size_is_allowed():
    max_items = BasicConfig.MAX_BATCH_ITEM_QUANTITY.value

    mentions = [
        create_mention(f"mention-{index}", tokens=1)
        for index in range(max_items)
    ]

    client = MockLLMClient(latency=0)

    result = asyncio.run(client.enrich(mentions))

    assert result.prompt_tokens == max_items


# ============================================================
# Successful enrichment
# ============================================================


def test_successful_enrichment_returns_batch_result():
    mention = create_mention(
        "normal-mention",
        tokens=100,
    )

    client = MockLLMClient(latency=0)

    result = asyncio.run(client.enrich([mention]))

    assert result.prompt_tokens == 100
    assert result.completion_tokens >= 0
    assert isinstance(result.results, list)


def test_enrichment_result_contains_expected_fields():
    mention = create_mention(
        "normal-mention",
        tokens=100,
    )

    client = MockLLMClient(latency=0)

    result = asyncio.run(client.enrich([mention]))

    # The chosen ID should normally produce a successful request.
    if result.results:
        response = result.results[0]

        assert isinstance(response, LLMResponse)
        assert response.id == mention.id
        assert response.tenant_id == mention.tenant_id
        assert response.sentiment in {"positive", "neutral"}
        assert response.summary == f"Mock summary for {mention.id}"
        assert response.enrichment_source == "llm"
        assert response.topics == ["topicA", "topicB"]


def test_prompt_tokens_are_calculated_from_mentions():
    mentions = [
        create_mention("mention-a", tokens=100),
        create_mention("mention-b", tokens=200),
        create_mention("mention-c", tokens=300),
    ]

    client = MockLLMClient(latency=0)

    result = asyncio.run(client.enrich(mentions))

    assert result.prompt_tokens == 600


def test_completion_tokens_are_50_per_returned_result():
    mention = create_mention(
        "normal-mention",
        tokens=100,
    )

    client = MockLLMClient(latency=0)

    result = asyncio.run(client.enrich([mention]))

    assert result.completion_tokens == len(result.results) * 50


# ============================================================
# Deterministic failure tests
# ============================================================


def test_rate_limit_error_is_deterministic():
    mention_id = find_id_for_outcome(0, 15)

    mention = create_mention(
        mention_id,
        tokens=100,
    )

    client = MockLLMClient(latency=0)

    with pytest.raises(RateLimitError) as exc_info:
        asyncio.run(client.enrich([mention]))

    assert exc_info.value.retry_after == 0.1


def test_upstream_error_is_deterministic():
    mention_id = find_id_for_outcome(15, 25)

    mention = create_mention(
        mention_id,
        tokens=100,
    )

    client = MockLLMClient(latency=0)

    with pytest.raises(UpstreamError, match="Internal server error"):
        asyncio.run(client.enrich([mention]))


def test_invalid_request_error_is_deterministic():
    mention_id = find_id_for_outcome(25, 30)

    mention = create_mention(
        mention_id,
        tokens=100,
    )

    client = MockLLMClient(latency=0)

    with pytest.raises(
        InvalidRequestError,
        match="Invalid request payload",
    ):
        asyncio.run(client.enrich([mention]))


# ============================================================
# Dropped-result behavior
# ============================================================


def test_mock_llm_can_drop_mentions():
    """
    The mock intentionally drops mentions when:
        md5(mention.id) % 20 == 0

    Find such an ID instead of depending on a hardcoded ID.
    """
    dropped_id = None

    for index in range(10000):
        mention_id = f"drop-test-{index}"

        hashed = MockLLMClient.calculate_deterministic_hash(
            mention_id
        )

        if hashed % 20 == 0:
            dropped_id = mention_id
            break

    assert dropped_id is not None

    # Make sure the first ID doesn't trigger a request-level failure.
    request_id = find_id_for_outcome(30, 100)

    mentions = [
        create_mention(request_id, tokens=100),
        create_mention(dropped_id, tokens=100),
    ]

    client = MockLLMClient(latency=0)

    result = asyncio.run(client.enrich(mentions))

    returned_ids = {response.id for response in result.results}

    assert dropped_id not in returned_ids


# ============================================================
# Latency test
# ============================================================


def test_injected_latency_is_applied():
    mention_id = find_id_for_outcome(30, 100)

    mention = create_mention(
        mention_id,
        tokens=100,
    )

    latency = 0.05
    client = MockLLMClient(latency=latency)

    async def timed_run():
        start_time = asyncio.get_running_loop().time()
        await client.enrich([mention])
        return asyncio.get_running_loop().time() - start_time

    elapsed = asyncio.run(timed_run())

    assert elapsed >= latency



# ============================================================
# Determinism tests
# ============================================================


def test_same_batch_produces_same_result():
    mention_id = find_id_for_outcome(30, 100)

    mentions = [
        create_mention(mention_id, tokens=100),
    ]

    client = MockLLMClient(latency=0)

    result_1 = asyncio.run(client.enrich(mentions))
    result_2 = asyncio.run(client.enrich(mentions))

    assert result_1.prompt_tokens == result_2.prompt_tokens
    assert result_1.completion_tokens == result_2.completion_tokens
    assert result_1.results == result_2.results


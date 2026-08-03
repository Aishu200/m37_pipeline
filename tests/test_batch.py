from datetime import datetime, timezone

from mention_pipeline.batch import Batching
from mention_pipeline.models import Mention


def create_mention(
    mention_id: str,
    tenant_id: str = "tenant-a",
    title: str = "Test title",
    body: str = "Test body",
) -> Mention:
    return Mention(
        id=mention_id,
        tenant_id=tenant_id,
        source="test-source",
        published_at=datetime.now(timezone.utc),
        title=title,
        body=body,
    )


def test_mentions_are_grouped_into_single_batch():
    mentions = {
        "tenant-a": [
            create_mention("m-001"),
            create_mention("m-002"),
        ]
    }

    failed, batches = Batching(mentions).batch()

    assert failed == []
    assert len(batches) == 1

    assert batches[0].tenant_id == "tenant-a"
    assert batches[0].mentions == mentions["tenant-a"]


def test_mentions_are_split_when_token_limit_exceeded():
    mention_1 = create_mention(
        "m-001",
        body="a" * 50000,
    )

    mention_2 = create_mention(
        "m-002",
        body="short",
    )

    failed, batches = Batching(
        {
            "tenant-a": [
                mention_1,
                mention_2,
            ]
        }
    ).batch()

    assert len(failed) == 1
    assert failed[0].id == "m-001"

    assert len(batches) == 1
    assert batches[0].mentions == [mention_2]


def test_batch_respects_max_item_quantity():
    mentions = {
        "tenant-a": [
            create_mention(f"m-{i}")
            for i in range(25)
        ]
    }

    failed, batches = Batching(mentions).batch()

    assert failed == []

    assert len(batches) == 2

    assert len(batches[0].mentions) == 20
    assert len(batches[1].mentions) == 5


def test_multiple_batches_are_created_for_token_budget():
    mentions = {
        "tenant-a": [
            create_mention(
                f"m-{i}",
                body="x" * 30000,
            )
            for i in range(5)
        ]
    }

    failed, batches = Batching(mentions).batch()

    assert failed == []

    assert len(batches) > 1

    for batch in batches:
        assert batch.token_count <= 8000


def test_batches_are_created_per_tenant():
    tenant_mentions = {
        "tenant-a": [
            create_mention(
                "m-001",
                tenant_id="tenant-a",
            ),
        ],
        "tenant-b": [
            create_mention(
                "m-002",
                tenant_id="tenant-b",
            ),
        ],
    }

    failed, batches = Batching(tenant_mentions).batch()

    assert failed == []

    assert len(batches) == 2

    assert batches[0].tenant_id == "tenant-a"
    assert batches[1].tenant_id == "tenant-b"


def test_failed_mentions_have_reason():
    mention = create_mention(
        "m-001",
        body="x" * 50000,
    )

    failed, batches = Batching(
        {
            "tenant-a": [mention]
        }
    ).batch()

    assert len(failed) == 1

    assert failed[0].id == "m-001"
    assert "exceeds maximum batch token budget" in failed[0].reason

    assert batches == []
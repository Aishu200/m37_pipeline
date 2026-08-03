from datetime import datetime, timezone

from mention_pipeline.models import Mention
from mention_pipeline.deduplication import Deduplicator


def create_mention(
    mention_id: str,
    title: str,
    body: str,
    tenant_id: str = "tenant-a",
) -> Mention:
    return Mention(
        id=mention_id,
        tenant_id=tenant_id,
        source="test-source",
        published_at=datetime.now(timezone.utc),
        title=title,
        body=body,
    )


def test_identical_mentions_are_deduplicated():
    mention_1 = create_mention(
        "m-001",
        "Company opens new factory",
        "The company announced a new factory in Delhi.",
    )

    mention_2 = create_mention(
        "m-002",
        "Company opens new factory",
        "The company announced a new factory in Delhi.",
    )

    result = Deduplicator([mention_1, mention_2]).process()

    assert result.unique_mentions == [mention_1]

    assert result.duplicate_to_canonical == {
        "m-002": "m-001"
    }


def test_multiple_duplicates_point_to_same_canonical():
    mention_1 = create_mention(
        "m-001",
        "Company opens new factory",
        "The company announced a new factory in Delhi.",
    )

    mention_2 = create_mention(
        "m-002",
        "Company opens new factory",
        "The company announced a new factory in Delhi.",
    )

    mention_3 = create_mention(
        "m-003",
        "Company opens new factory",
        "The company announced a new factory in Delhi.",
    )

    result = Deduplicator(
        [mention_1, mention_2, mention_3]
    ).process()

    assert result.unique_mentions == [mention_1]

    assert result.duplicate_to_canonical == {
        "m-002": "m-001",
        "m-003": "m-001",
    }


def test_different_mentions_remain_unique():
    mention_1 = create_mention(
        "m-001",
        "Company opens new factory",
        "The company announced a new factory in Delhi.",
    )

    mention_2 = create_mention(
        "m-002",
        "Weather forecast for Mumbai",
        "Heavy rainfall is expected in Mumbai tomorrow.",
    )

    result = Deduplicator([mention_1, mention_2]).process()

    assert result.unique_mentions == [
        mention_1,
        mention_2,
    ]

    assert result.duplicate_to_canonical == {}


def test_first_occurrence_becomes_canonical():
    mention_1 = create_mention(
        "m-001",
        "Company opens new factory",
        "The company announced a new factory in Delhi.",
    )

    mention_2 = create_mention(
        "m-002",
        "Company opens new factory",
        "The company announced a new factory in Delhi.",
    )

    result = Deduplicator([mention_2, mention_1]).process()

    assert result.unique_mentions == [mention_2]

    assert result.duplicate_to_canonical == {
        "m-001": "m-002"
    }


def test_duplicates_can_exist_across_tenants():
    mention_1 = create_mention(
        "m-001",
        "Company opens new factory",
        "The company announced a new factory in Delhi.",
        tenant_id="tenant-a",
    )

    mention_2 = create_mention(
        "m-002",
        "Company opens new factory",
        "The company announced a new factory in Delhi.",
        tenant_id="tenant-b",
    )

    result = Deduplicator([mention_1, mention_2]).process()

    assert result.unique_mentions == [mention_1]

    assert result.duplicate_to_canonical == {
        "m-002": "m-001"
    }


def test_jaccard_similarity():
    shingles_1 = {
        "company opens new",
        "opens new factory",
        "new factory today",
    }

    shingles_2 = {
        "company opens new",
        "opens new factory",
        "new factory tomorrow",
    }

    similarity = Deduplicator.jaccard_similarity(
        shingles_1,
        shingles_2,
    )

    assert similarity == 0.5


def test_create_shingles():
    text = "one two three four five six"

    shingles = Deduplicator.create_shingles(
        text,
        k=3,
    )

    assert shingles == {
        "one two three",
        "two three four",
        "three four five",
        "four five six",
    }


def test_normalize_text_removes_punctuation_and_lowercases():
    mention = create_mention(
        "m-001",
        "Hello, WORLD!",
        "This is a TEST.",
    )

    normalized = Deduplicator.normalize_text(mention)

    assert normalized == "hello world this is a test"


def test_empty_shingles():
    result = Deduplicator.jaccard_similarity(set(), set())

    assert result == 0.0
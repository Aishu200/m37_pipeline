
from datetime import datetime, timezone

from mention_pipeline.models import FailedMention, LLMResponse, Mention
from mention_pipeline.reconciliation import ResultReconciler


def create_mention(mention_id: str) -> Mention:
    return Mention(
        id=mention_id,
        tenant_id="tenant-1",
        source="test-source",
        published_at=datetime.now(timezone.utc),
        title="Test title",
        body="Test body",
    )


def create_response(response_id: str) -> LLMResponse:
    return LLMResponse(
        id=response_id,
        tenant_id="tenant-1",
        sentiment="positive",
        summary="Test summary",
        topics=["topicA"],
    )


# ============================================================
# Process tests
# ============================================================


def test_all_mentions_are_returned():
    batch = [
        create_mention("m1"),
        create_mention("m2"),
        create_mention("m3"),
    ]

    responses = [
        create_response("m1"),
        create_response("m2"),
        create_response("m3"),
    ]

    reconciler = ResultReconciler(
        batch=batch,
        llm_response=responses,
    )

    failed = reconciler.process()

    assert failed == []


def test_one_mention_is_missing():
    batch = [
        create_mention("m1"),
        create_mention("m2"),
        create_mention("m3"),
    ]

    responses = [
        create_response("m1"),
        create_response("m3"),
    ]

    reconciler = ResultReconciler(
        batch=batch,
        llm_response=responses,
    )

    failed = reconciler.process()

    assert len(failed) == 1
    assert failed[0].id == "m2"
    assert failed[0].reason == (
        "LLM did not return a result for mention"
    )


def test_multiple_mentions_are_missing():
    batch = [
        create_mention("m1"),
        create_mention("m2"),
        create_mention("m3"),
        create_mention("m4"),
    ]

    responses = [
        create_response("m1"),
        create_response("m4"),
    ]

    reconciler = ResultReconciler(
        batch=batch,
        llm_response=responses,
    )

    failed = reconciler.process()

    failed_ids = {
        failure.id
        for failure in failed
    }

    assert failed_ids == {"m2", "m3"}
    assert len(failed) == 2


def test_empty_batch_returns_no_failures():
    reconciler = ResultReconciler(
        batch=[],
        llm_response=[],
    )

    failed = reconciler.process()

    assert failed == []


def test_empty_llm_response_marks_all_mentions_as_failed():
    batch = [
        create_mention("m1"),
        create_mention("m2"),
        create_mention("m3"),
    ]

    reconciler = ResultReconciler(
        batch=batch,
        llm_response=[],
    )

    failed = reconciler.process()

    failed_ids = {
        failure.id
        for failure in failed
    }

    assert failed_ids == {"m1", "m2", "m3"}
    assert len(failed) == 3

    for failure in failed:
        assert isinstance(failure, FailedMention)
        assert failure.reason == (
            "LLM did not return a result for mention"
        )


def test_extra_llm_response_is_ignored():
    batch = [
        create_mention("m1"),
        create_mention("m2"),
    ]

    responses = [
        create_response("m1"),
        create_response("m2"),
        create_response("m999"),
    ]

    reconciler = ResultReconciler(
        batch=batch,
        llm_response=responses,
    )

    failed = reconciler.process()

    assert failed == []


# ============================================================
# get_id_list tests
# ============================================================


def test_get_id_list_returns_set_for_mentions():
    mentions = [
        create_mention("m1"),
        create_mention("m2"),
        create_mention("m3"),
    ]

    result = ResultReconciler.get_id_list(mentions)

    assert isinstance(result, set)
    assert result == {"m1", "m2", "m3"}


def test_get_id_list_returns_set_for_llm_responses():
    responses = [
        create_response("m1"),
        create_response("m2"),
        create_response("m3"),
    ]

    result = ResultReconciler.get_id_list(responses)

    assert isinstance(result, set)
    assert result == {"m1", "m2", "m3"}


def test_get_id_list_removes_duplicate_ids():
    mentions = [
        create_mention("m1"),
        create_mention("m1"),
        create_mention("m2"),
    ]

    result = ResultReconciler.get_id_list(mentions)

    assert result == {"m1", "m2"}


# ============================================================
# find_missing_mentions tests
# ============================================================


def test_find_missing_mentions_returns_difference():
    mention_ids = {
        "m1",
        "m2",
        "m3",
    }

    response_ids = {
        "m1",
        "m3",
    }

    result = ResultReconciler.find_missing_mentions(
        mention_ids,
        response_ids,
    )

    assert result == {"m2"}


def test_find_missing_mentions_returns_empty_when_all_present():
    mention_ids = {
        "m1",
        "m2",
        "m3",
    }

    response_ids = {
        "m1",
        "m2",
        "m3",
    }

    result = ResultReconciler.find_missing_mentions(
        mention_ids,
        response_ids,
    )

    assert result == set()


def test_find_missing_mentions_when_response_is_empty():
    mention_ids = {
        "m1",
        "m2",
        "m3",
    }

    response_ids = set()

    result = ResultReconciler.find_missing_mentions(
        mention_ids,
        response_ids,
    )

    assert result == {
        "m1",
        "m2",
        "m3",
    }


def test_find_missing_mentions_ignores_extra_response_ids():
    mention_ids = {
        "m1",
        "m2",
    }

    response_ids = {
        "m1",
        "m2",
        "m999",
    }

    result = ResultReconciler.find_missing_mentions(
        mention_ids,
        response_ids,
    )

    assert result == set()

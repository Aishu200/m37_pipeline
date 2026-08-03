from datetime import UTC, datetime

from mention_pipeline.config import BasicConfig
from mention_pipeline.models import (
    Batch,
    BatchResult,
    FailedMention,
    LLMResponse,
    Mention,
    Report,
    TenantReport,
)


class ReportGenerator:
    """Generate tenant-level and overall enrichment metrics."""

    def generate(
        self,
        mentions: list[Mention],
        batches: list[Batch],
        batch_results: list[BatchResult],
        failed_mentions: list[FailedMention],
    ) -> Report:
        """Aggregate pipeline results into a report."""
        tenant_mentions = self._group_mentions_by_tenant(mentions)
        tenant_batches = self._group_batches_by_tenant(batches)
        tenant_failures = self._group_failures_by_tenant(
            failed_mentions,
            mentions,
        )

        all_responses = self._get_all_responses(batch_results)

        tenant_reports = {}

        for tenant_id, tenant_input in tenant_mentions.items():
            tenant_batch_list = tenant_batches.get(tenant_id, [])

            tenant_responses = [
                response
                for response in all_responses
                if response.tenant_id == tenant_id
            ]

            tenant_batch_results = [
                result
                for batch, result in zip(batches, batch_results)
                if batch.tenant_id == tenant_id
            ]

            prompt_tokens = sum(
                result.prompt_tokens
                for result in tenant_batch_results
            )

            completion_tokens = sum(
                result.completion_tokens
                for result in tenant_batch_results
            )

            llm_calls = len(tenant_batch_list)

            estimated_cost = self._calculate_cost(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

            tenant_reports[tenant_id] = TenantReport(
                tenant_id=tenant_id,
                mentions_in=len(tenant_input),
                mentions_enriched=len(tenant_responses),
                llm_calls=llm_calls,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                estimated_cost_usd=estimated_cost,
                failed=tenant_failures.get(tenant_id, []),
            )

        return Report(
            generated_at=datetime.now(UTC),
            tenants=tenant_reports,
            mentions=all_responses,
        )

    @staticmethod
    def _group_mentions_by_tenant(mentions: list[Mention]) -> dict[str, list[Mention]]:
        """Group input mentions so tenant metrics remain isolated."""
        grouped: dict[str, list[Mention]] = {}

        for mention in mentions:
            grouped.setdefault(mention.tenant_id, []).append(mention)

        return grouped


    @staticmethod
    def _group_batches_by_tenant(batches: list[Batch]) -> dict[str, list[Batch]]:
        """Group batches so LLM call counts are tenant-specific."""
        grouped: dict[str, list[Batch]] = {}

        for batch in batches:
            grouped.setdefault(batch.tenant_id, []).append(batch)

        return grouped


    @staticmethod
    def _group_failures_by_tenant( failed_mentions: list[FailedMention], mentions: list[Mention]) -> dict[str, list[FailedMention]]:
        """Associate failed mentions with their owning tenant."""
        mention_tenants = {
            mention.id: mention.tenant_id
            for mention in mentions
        }

        grouped: dict[str, list[FailedMention]] = {}

        for failure in failed_mentions:
            tenant_id = mention_tenants.get(failure.id)

            if tenant_id is None:
                continue

            grouped.setdefault(tenant_id, []).append(failure)

        return grouped

    @staticmethod
    def _get_all_responses(batch_results: list[BatchResult]) -> list[LLMResponse]:
        """Flatten successful LLM responses from all batch results."""
        responses: list[LLMResponse] = []

        for result in batch_results:
            responses.extend(result.results)

        return responses


    @staticmethod
    def _calculate_cost(prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate LLM cost from configured token pricing."""
        input_cost = (
            prompt_tokens / 1000
        ) * BasicConfig.LLM_INPUT_COST_PER_1K.value

        output_cost = (
            completion_tokens / 1000
        ) * BasicConfig.LLM_OUTPUT_COST_PER_1K.value

        return round(input_cost + output_cost, 6)

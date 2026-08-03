from collections import defaultdict

from mention_pipeline.models import FailedMention, LLMResponse, Mention, Report



# ========================================================== Group Mentions By Tenant ==========================================================
def group_mentions_by_tenant(mention_list: list[Mention]) -> dict[str, list[Mention]] :
    grouped_data = defaultdict(list)
    
    for mention in mention_list:
        grouped_data[mention.tenant_id].append(mention)
    
    return {
        tenant_id: sorted(
            mentions,
            key=lambda mention: (mention.published_at, mention.id),
        )
        for tenant_id, mentions in grouped_data.items()
    }
    
    
# ========================================================== Group Mentions By Tenant ==========================================================


# ============================== Orchestration Layer =======================================

class MentionPipeline:
    def __init__(self, deduplicator, batcher, batch_processor, reconciler, report_generator) -> None :
        self.deduplicator = deduplicator
        self.batcher = batcher
        self.batch_processor = batch_processor
        self.reconciler = reconciler
        self.report_generator = report_generator


    async def run(self, mentions: list[Mention]) -> Report :
        # 1. Group mentions by tenant
        tenant_mentions = group_mentions_by_tenant(mentions)

        # 2. Deduplicate
        deduplication_results = {
            tenant_id: self.deduplicator(
                mention_list=tenant_mentions
            ).process()
            for tenant_id, tenant_mentions in tenant_mentions.items()
        }

        # 3. Prepare unique mentions for batching
        unique_mentions = {
            tenant_id: result.unique_mentions
            for tenant_id, result in deduplication_results.items()
        }

        # 4. Create batches
        failed_mentions, batches = self.batcher(
            tenant_based_mentions=unique_mentions
        ).batch()

        # 5. Process batches concurrently
        batch_results = await self.batch_processor.process_batches(
            batches
        )

        # 6. Reconcile LLM responses
        for batch, batch_result in zip(batches, batch_results):
            failed_mentions.extend(
                self.reconciler(
                    batch=batch.mentions,
                    llm_response=batch_result.results,
                ).process()
            )


        # =========================================================
        # 7. Collect canonical LLM responses
        # =========================================================
        canonical_responses: dict[str, LLMResponse] = {}

        for batch_result in batch_results:
            for response in batch_result.results:
                canonical_responses[response.id] = response

        # =========================================================
        # 8. Propagate canonical responses to duplicates
        # =========================================================
        duplicate_responses: list[LLMResponse] = []

        for deduplication_result in deduplication_results.values():
            for duplicate_id, canonical_id in (
                deduplication_result.duplicate_to_canonical.items()
            ):
                canonical_response = canonical_responses.get(canonical_id)

                # Canonical mention did not receive a response.
                # Therefore the duplicate cannot be enriched either.
                if canonical_response is None:
                    failed_mentions.append(
                        FailedMention(
                            id=duplicate_id,
                            reason=(
                                "Canonical mention did not receive "
                                "an LLM result"
                            ),
                        )
                    )
                    continue

                duplicate_responses.append(
                    LLMResponse(
                        id=duplicate_id,
                        tenant_id=canonical_response.tenant_id,
                        sentiment=canonical_response.sentiment,
                        summary=canonical_response.summary,
                        topics=list(canonical_response.topics),
                        enrichment_source=f"duplicate_of:{canonical_id}",
                    )
                )

        # =========================================================
        # 9. Combine canonical + duplicate responses
        # =========================================================
        all_responses = [
            response
            for batch_result in batch_results
            for response in batch_result.results
        ]

        all_responses.extend(duplicate_responses)


        report = self.report_generator.generate(
            mentions=mentions,
            batches=batches,
            batch_results=batch_results,
            failed_mentions=failed_mentions,
            responses=all_responses,
        )

        return report

    

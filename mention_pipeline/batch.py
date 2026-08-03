
from mention_pipeline.config import BasicConfig
from mention_pipeline.models import Batch, FailedMention, Mention


class Batching:
    def __init__(self, tenant_based_mentions: dict[str, list[Mention]]) -> None :
        self.tenant_based_mentions = tenant_based_mentions
        
    
    def batch(self) -> tuple[list[FailedMention], list[Batch]]:
        
        total_batches: list[Batch] = []
        failed_mentions: list[FailedMention] = []
        
        
        for tenant, mentions in self.tenant_based_mentions.items():
            inner_batch: list[Mention] = []
            tokens_used = 0

            for mention in mentions:
                if mention.tokens > BasicConfig.BATCH_TOKEN_THRESHOLD.value:
                    failed_mentions.append(
                        FailedMention(
                            id = mention.id,
                            reason= f'mention exceeds maximum batch token budget ({BasicConfig.BATCH_TOKEN_THRESHOLD.value})'
                        )
                    )
                    continue
                
                if len(inner_batch) < BasicConfig.MAX_BATCH_ITEM_QUANTITY.value and tokens_used + mention.tokens <= BasicConfig.BATCH_TOKEN_THRESHOLD.value:
                    inner_batch.append(mention)
                    tokens_used += mention.tokens
                    
                else:
                    total_batches.append(self.create_batch(
                        tenant, inner_batch, tokens_used
                    ))
                    inner_batch, tokens_used = [], 0
                    
                    inner_batch.append(mention)
                    tokens_used += mention.tokens
        
            if inner_batch:
                total_batches.append(self.create_batch(
                    tenant, inner_batch, tokens_used
                ))
        
        
        return failed_mentions, total_batches
        
    
    @staticmethod
    def create_batch(tenant_id: str, mentions: list[Mention], token_count: int) -> Batch :
        return Batch(
            tenant_id= tenant_id,
            mentions = mentions,
            token_count= token_count
        )
        
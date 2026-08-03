""" A Mock LLM Client """

import asyncio
import hashlib
from abc import ABC, abstractmethod

from mention_pipeline.config import BasicConfig
from mention_pipeline.exceptions import (
    BatchSizeError,
    InvalidRequestError,
    RateLimitError,
    TokenLimitExceeded,
    UpstreamError,
)
from mention_pipeline.models import BatchResult, LLMResponse, Mention


class LLMClient(ABC):
    @abstractmethod
    async def enrich(self, batch: list[Mention]) -> BatchResult: ...


class BatchValidations:
    def __init__(self, batch: list[Mention]) -> None:
        self.batch = batch

    def validate(self) -> None :
        self.validate_empty_batch()
        self.validate_batch_size()
        self.validate_prompt_token()

    def validate_batch_size(self) -> None :
        if len(self.batch) > BasicConfig.MAX_BATCH_ITEM_QUANTITY.value:
            raise BatchSizeError(f"Batch size {len(self.batch)} exceeds limit of {BasicConfig.MAX_BATCH_ITEM_QUANTITY.value}")    

    def validate_empty_batch(self) -> None :
        if len(self.batch) == 0:
            raise InvalidRequestError("Empty batch can not be processed.")    

    def validate_prompt_token(self) -> None :
        total_token_count = sum(m.tokens for m in self.batch)
        if total_token_count > BasicConfig.BATCH_TOKEN_THRESHOLD.value:
            raise TokenLimitExceeded(f"Tokens {total_token_count} exceed limit of {BasicConfig.BATCH_TOKEN_THRESHOLD.value}")



class MockLLMClient(LLMClient):

    def __init__(self, latency: float = 0.05) -> None:
        self.latency = latency


    async def enrich(self, batch: list[Mention]) -> BatchResult:

        # Validate Batch
        BatchValidations(
            batch= batch
        ).validate()

        # Check Latency
        if self.latency > 0:
            await asyncio.sleep(self.latency)

        h = self.calculate_deterministic_hash(
            first_id= batch[0].id
        )
        outcome = h % 100
        if outcome < 15:
            raise RateLimitError(retry_after=0.1)
        elif outcome < 25:
            raise UpstreamError("Internal server error from mock LLM")
        elif outcome < 30:
            raise InvalidRequestError("Invalid request payload")

        results: list[LLMResponse] = []
        for mention in batch:
            # Model sometimes drops items. Let's say if the hash of mention id % 20 == 0
            drop_hash = int(hashlib.md5(mention.id.encode('utf-8')).hexdigest(), 16)
            if drop_hash % 20 == 0:
                continue  # Drop this mention

            results.append(LLMResponse(
                id= mention.id,
                tenant_id= mention.tenant_id,
                sentiment= "positive" if (drop_hash % 2) == 0 else "neutral",
                summary= f"Mock summary for {mention.id}",
                enrichment_source= "llm",
                topics= ["topicA", "topicB"],
            ))

        completion_tokens = len(results) * 50
        prompt_tokens = sum(m.tokens for m in batch)
        return BatchResult(
            results= results,
            prompt_tokens= prompt_tokens,
            completion_tokens= completion_tokens
        ) 
             

    @staticmethod
    def calculate_deterministic_hash(first_id: str) -> int:
        return int(hashlib.md5(first_id.encode('utf-8')).hexdigest(), 16)



    
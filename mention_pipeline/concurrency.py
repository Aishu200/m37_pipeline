import asyncio

from mention_pipeline.config import BasicConfig
from mention_pipeline.llm import LLMClient
from mention_pipeline.models import Batch, BatchResult
from mention_pipeline.retry import RetryHandler


class ConcurrentBatchProcessor:
    def __init__(self, client: LLMClient, retry_handler: RetryHandler, max_concurrency: int = BasicConfig.SEMAPHORE_VALUE.value) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")

        self.client = client
        self.retry_handler = retry_handler
        self.semaphore = asyncio.Semaphore(max_concurrency)


    async def process_batch(self, batch: Batch) -> BatchResult:
        async with self.semaphore:
            return await self.retry_handler.execute(
                self.client.enrich,
                batch.mentions,
            )


    async def process_batches(self, batches: list[Batch],) -> list[BatchResult]:
        if not batches:
            return []

        tasks = [
            self.process_batch(batch)
            for batch in batches
        ]

        return await asyncio.gather(*tasks)


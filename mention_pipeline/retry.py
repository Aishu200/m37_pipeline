import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from mention_pipeline.exceptions import RetryableError

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class RetryHandler:
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 30.0) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        if base_delay < 0:
            raise ValueError("base_delay cannot be negative")

        if max_delay < base_delay:
            raise ValueError("max_delay must be >= base_delay")

        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay


    async def execute(self, operation: Callable[[InputT], Awaitable[OutputT]], value: InputT) -> OutputT:
        attempt = 1

        while attempt <= self.max_attempts:
            try:
                return await operation(value)
            
            except RetryableError as re :
                if attempt == self.max_attempts:
                    raise
                retry_after = getattr(re, 'retry_after', None)
                delay = (
                    retry_after
                    if retry_after is not None
                    else self._calculate_delay(attempt)
                )
                await asyncio.sleep(delay)

                attempt += 1

        raise RuntimeError("Retry execution failed unexpectedly")


    def _calculate_delay(self, attempt: int) -> float:
        exponential_delay = self.base_delay * (2 ** (attempt - 1))
        delay:float = min(exponential_delay, self.max_delay)

        jitter:float = random.uniform(0, delay * 0.1)

        return delay + jitter

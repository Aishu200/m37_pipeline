
# BASE EXCEPTION FOR THIS PROJECT
class MentionPipelineError(Exception):
    pass

# -----------------------------------------------------------------
# SECOND HIERARCHY EXCEPTION FOR THIS PROJECT
class RetryableError(MentionPipelineError):
    pass

class NonRetryableError(MentionPipelineError):
    pass

# -----------------------------------------------------------------
# THIRD HIERARCHY EXCEPTION FOR THIS PROJECT


class RateLimitError(RetryableError):
    def __init__(self, retry_after: float = 0.1) -> None:
        self.retry_after = retry_after

class UpstreamError(RetryableError):
    pass


class InvalidRequestError(NonRetryableError):
    pass

class TokenLimitExceeded(NonRetryableError):
    pass

class BatchSizeError(NonRetryableError):
    pass

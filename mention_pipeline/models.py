from dataclasses import dataclass, field
from datetime import datetime

# ================================================================ DATACLASS MODELS ================================================================

# ============  Mention ============
@dataclass
class Mention:
    """Represent a Mention"""
    id: str
    tenant_id: str
    source: str
    published_at: datetime
    title: str
    body: str
    
    @property
    def tokens(self) -> int:
        return len(self.title + self.body) // 4
    



# ============ Deduplication Record ============
@dataclass
class DeduplicationRecord:
    """Represent a Duplication Record"""
    unique_mentions: list[Mention]
    duplicate_to_canonical: dict[str, str]
    
    
    
    
# # ============ Batches ============
@dataclass
class Batch:
    """Represent a Batch"""
    tenant_id: str
    mentions: list[Mention] = field(default_factory=list)
    token_count: int = 0    



# ============  LLM Response per Mention ============
@dataclass
class LLMResponse:
    """Represent a LLM Response per Mention"""
    id: str
    tenant_id: str
    sentiment: str
    summary: str
    topics: list[str] = field(default_factory= list)
    enrichment_source: str = "llm"
    
    
    
    
# ============ Failed Mentions ============
@dataclass
class FailedMention:
    """Represent a Failed Mention"""
    id: str
    reason: str
    
    
    
    
# ============ Tenant Report ============
@dataclass
class TenantReport:
    """Represent a Tenant Report"""
    tenant_id: str
    mentions_in: int
    mentions_enriched: int
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    failed: list[FailedMention] = field(default_factory= list)




# ============ Report ============
@dataclass
class Report:
    """Represent the Report"""
    generated_at: datetime
    tenants: dict[str, TenantReport] = field(default_factory= dict)
    mentions: list[LLMResponse] = field(default_factory= list)
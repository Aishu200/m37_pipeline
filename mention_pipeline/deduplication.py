import string

from mention_pipeline.config import BasicConfig
from mention_pipeline.models import DeduplicationRecord, Mention


class Deduplicator:
    def __init__(self, mention_list: list[Mention]) -> None :
        self.mention_list = mention_list
    
    
    def process(self) -> DeduplicationRecord :
        unique_mentions: list[Mention] = []
        duplicate_to_canonical: dict[str, str] = {}
        canonical_shingles: dict[str, set[str]] = {}
        
        for mention in self.mention_list:
            normalized_message = self.normalize_text(mention= mention)
            shingles = self.create_shingles(normalized_message)
            
            if not canonical_shingles:
                unique_mentions.append(mention)
                canonical_shingles[mention.id] = shingles
                continue
            
            duplicate_found = False

            for canonical_id, canonical_shingle in canonical_shingles.items():
                similarity = self.jaccard_similarity(
                    shingles,
                    canonical_shingle
                )
                
                if similarity >= BasicConfig.JACCARD_THRESHOLD.value:
                    duplicate_to_canonical[mention.id] = canonical_id
                    duplicate_found = True
                    break

            if not duplicate_found:
                unique_mentions.append(mention)
                canonical_shingles[mention.id] = shingles

        return DeduplicationRecord(
            unique_mentions=unique_mentions,
            duplicate_to_canonical=duplicate_to_canonical
        )
        
    
      
    @staticmethod
    def jaccard_similarity(shingle1: set[str], shingle2: set[str]) -> float :
        
        union = shingle1 | shingle2
        intersection = shingle1 & shingle2
        
        return len(intersection) / len(union) if union else 0.00
    
    
    @staticmethod
    def create_shingles(message: str, k: int = BasicConfig.SHINGLE_VAlUE.value) -> set[str]:
        words = message.split()

        if len(words) < k:
            return {" ".join(words)} if words else set()

        return {
            " ".join(words[i : i + k])
            for i in range(len(words) - k + 1)
        }
      
        
    @staticmethod
    def normalize_text(mention: Mention) -> str :
        message = mention.title + " " + mention.body
        return Deduplicator.remove_punctuations(message= message.lower())
    
    
    @staticmethod
    def remove_punctuations(message: str) -> str:
        return message.translate(str.maketrans("", "", string.punctuation))
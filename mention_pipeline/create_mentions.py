import json
from datetime import datetime

from mention_pipeline.models import Mention


class CreateMentions:
    def __init__(self, file_location: str) -> None:
        self.file_location = file_location
        
    def process(self) -> list[Mention]:
        with open(self.file_location, "r", encoding="utf-8") as file:
            mention_data = json.load(file)
            
        return [
            Mention(
                id=item["id"],
                tenant_id=item["tenant_id"],
                source=item["source"],
                published_at=self.parse_datetime(item["published_at"]),
                title=item["title"],
                body=item["body"],
            )
            for item in mention_data
        ]

    @staticmethod
    def parse_datetime(datetime_str: str) -> datetime:
        try:
            return datetime.fromisoformat(datetime_str)
        except ValueError as e:
            raise ValueError(f"Invalid datetime: {datetime_str}") from e
 
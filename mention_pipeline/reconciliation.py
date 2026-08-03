from mention_pipeline.models import FailedMention, LLMResponse, Mention


class ResultReconciler:
    def __init__(self, batch: list[Mention], llm_response: list[LLMResponse]) -> None :
        self.batch = batch
        self.llm_response = llm_response


    def process(self) -> list[FailedMention] :
        mention_ids = self.get_id_list(data_list= self.batch)
        response_ids = self.get_id_list(data_list= self.llm_response)
        missing_mentions = self.find_missing_mentions(
            mention_ids= mention_ids,
            response_ids= response_ids
        )
        return [
            FailedMention(
                id= mention_id,
                reason= "LLM did not return a result for mention"
            ) for mention_id in missing_mentions
        ]


    @staticmethod
    def get_id_list(data_list: list[Mention] | list[LLMResponse]) -> set[str] :
        return {
            data.id for data in data_list
        }

    @staticmethod
    def find_missing_mentions(mention_ids: set[str], response_ids: set[str]) -> set[str] :
        return mention_ids - response_ids
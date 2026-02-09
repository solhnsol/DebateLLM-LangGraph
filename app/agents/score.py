from app.agents.base import BaseAgent
from app.models.schemas import ScoreOutput, MessageList

SCORE_PROMPT = """당신은 토론 심사위원입니다.
주어진 토론 주제, {topic}에 대해 {position} 측의 토론 내용을 바탕으로 다음 세 가지 기준에 따라 각각 0에서 100점 사이의 점수를 매겨야 합니다.
1. 논리 (Reasoning): 주장의 일관성과 타당성
2. 근거 (Substantiality): 주장에 대한 구체적이고 설득력 있는 근거 제시
3. 전달력 및 매너 (Delivery and Manner): 표현의 명확성, 어조, 태도  
"""

class ScoreAgent(BaseAgent):
    def __init__(self):
        super().__init__(output_schema=ScoreOutput, temperature=0)

    async def score_debate(self, topic: str, messages: MessageList, position: str) -> ScoreOutput:
        kr_position = "찬성" if position == "positive" else "반대"

        prompt = SCORE_PROMPT.format(topic=topic, position=kr_position)
        response: ScoreOutput = await self.get_response(prompt, messages)
        return response
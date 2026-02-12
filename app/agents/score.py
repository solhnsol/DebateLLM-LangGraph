from langchain_core.messages import AIMessage

from app.agents.base import BaseAgent
from app.models.schemas import ScoreOutput, MessageList
from app.core.prompts import SCORE_PROMPT

class ScoreAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(output_schema=ScoreOutput, temperature=0, *args, **kwargs)

    async def score_debate(self, topic: str, messages: MessageList, position: str) -> ScoreOutput:
        kr_position = "찬성" if position == "pro" else "반대"

        prompt = SCORE_PROMPT.format(topic=topic, position=kr_position)
        response: AIMessage
        parsed: ScoreOutput
        response, parsed = await self.get_response(prompt, messages)
        return response, parsed
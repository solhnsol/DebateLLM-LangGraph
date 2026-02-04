from app.agents.base import BaseAgent
from app.models.schemas import DebaterOutput, MessageList

DEBATER_PROMPT = """당신은 열정적인 토론자입니다.
주어진 토론 주제인 '{topic}', 지금까지의 대화 맥락에 맞게 {position} 입장에서 논리적이고 설득력 있는 발언을 하세요.
주장은 명확하고 간결하게 200자 내외로 표현해야 하며, 상대방의 주장을 반박하는 내용을 포함할 수 있습니다."""

class DebaterAgent(BaseAgent):
    def __init__(self):
        super().__init__(output_schema=DebaterOutput)

    async def debate_chat(self, topic: str, messages: MessageList, position: str) -> DebaterOutput:
        ai_position = "반대" if position == "positive" else "찬성"

        prompt = DEBATER_PROMPT.format(topic=topic, position=ai_position)
        response: DebaterOutput = await self.get_response(prompt, messages)
        return response
from app.agents.base import BaseAgent
from app.models.schemas import MessageList
from app.tools.tool_manager import ToolManager

DEBATER_PROMPT = """당신은 열정적인 토론자입니다.
주어진 토론 주제인 '{topic}', 지금까지의 대화 맥락에 맞게 {position} 입장에서 논리적이고 설득력 있는 발언을 하세요.
주장은 반드시 주어진 검색 도구를 활용해 뒷받침해야 합니다."""

class DebaterAgent(BaseAgent):
    def __init__(self, tools: list = None):
        super().__init__(tools=tools)

    async def debate_chat(self, topic: str, messages: MessageList, position: str):
        ai_position = "반대" if position == "positive" else "찬성"

        prompt = DEBATER_PROMPT.format(topic=topic, position=ai_position)
        response = await self.get_response(prompt, messages)
        return response
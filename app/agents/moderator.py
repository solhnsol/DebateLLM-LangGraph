from app.agents.base import BaseAgent
from app.models.schemas import ModeratorOutput, MessageList

MODERATOR_PROMPT = """당신은 최고 수준의 토론 사회자입니다.
주어진 토론 주제, {topic}에 대해 공정하고 균형 잡힌 진행을 해주세요.
멘트는 간결하고 명확하게 200자 내외로 작성하며, 다음 발언자를 지정해야 합니다.
찬성 측 토론자부터 토론을 시작하세요.
"""


class ModeratorAgent(BaseAgent):
    def __init__(self):
        super().__init__(output_schema=ModeratorOutput)
        
    async def moderate_chat(self, topic: str, messages: MessageList) -> ModeratorOutput:
        prompt = MODERATOR_PROMPT.format(topic=topic)
        response: ModeratorOutput = await self.get_response(prompt, messages)
        return response
from app.agents.base import BaseAgent
from app.models.schemas import JudgeOutput, MessageList

JUDGE_PROMPT = """당신은 공정한 판사입니다.
주어진 토론 주제인 '{topic}'에 대해 지금까지의 대화 맥락을 종합하여 최종 판결을 내리세요.
해당 주제에 대한 당신의 기존 생각은 배제하고, 오직 토론자들의 발언에 근거하여 판결을 내려야 합니다.
또한 판결문은 간결하고 명확해야 합니다."""

class JudgeAgent(BaseAgent):
    def __init__(self):
        super().__init__(output_schema=JudgeOutput)
        
    async def judge_chat(self, topic: str, messages: MessageList) -> JudgeOutput:
        prompt = JUDGE_PROMPT.format(topic=topic)
        response: JudgeOutput = await self.get_response(prompt, messages)
        return response

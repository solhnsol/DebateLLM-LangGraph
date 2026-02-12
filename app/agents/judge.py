from langchain_core.messages import AIMessage

from app.agents.base import BaseAgent
from app.models.schemas import JudgeOutput, MessageList
from app.core.prompts import JUDGE_PROMPT


class JudgeAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(output_schema=JudgeOutput, *args, **kwargs)
        
    async def judge_chat(self, topic: str, messages: MessageList) -> AIMessage:
        prompt = JUDGE_PROMPT.format(topic=topic)
        response: AIMessage
        parsed: JudgeOutput
        response, parsed = await self.get_response(prompt, messages)
        return response, parsed
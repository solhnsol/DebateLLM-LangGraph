from langchain_core.messages import AIMessage

from app.agents.base import BaseAgent
from app.models.schemas import MessageList
from app.core.prompts import DEBATER_PROMPT


class DebaterAgent(BaseAgent):
    async def debate_chat(self, topic: str, messages: MessageList, position: str):
        if position not in ["pro", "con"]:
            raise ValueError("Position must be either 'pro' or 'con'.")
        ai_position = "반대" if position == "pro" else "찬성"

        prompt = DEBATER_PROMPT.format(topic=topic, position=ai_position)
        response: AIMessage
        response, _ = await self.get_response(prompt, messages)
        return response
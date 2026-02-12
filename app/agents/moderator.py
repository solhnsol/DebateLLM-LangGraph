from langchain_core.messages import AIMessage

from app.agents.base import BaseAgent
from app.models.schemas import ModeratorOutput, MessageList
from app.core.prompts import MODERATOR_PROMPT



class ModeratorAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(output_schema=ModeratorOutput, *args, **kwargs)
        
    async def moderate_chat(self, topic: str, messages: MessageList) -> AIMessage:
        prompt = MODERATOR_PROMPT.format(topic=topic)
        response: AIMessage
        parsed: ModeratorOutput
        response, parsed = await self.get_response(prompt, messages)
        return response, parsed
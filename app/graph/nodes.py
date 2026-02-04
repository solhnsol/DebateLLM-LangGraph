from langchain_core.messages import AIMessage
from app.models.schemas import DebateState

from app.agents.debater import DebaterAgent
from app.agents.moderator import ModeratorAgent
from app.agents.judge import JudgeAgent

class DebateNodes:
    def __init__(self):
        self.moderator_agent = ModeratorAgent()
        self.debater_agent = DebaterAgent()
        self.judge_agent = JudgeAgent()
    
    async def moderator_node(self, state: DebateState):
        response = await self.moderator_agent.moderate_chat(state.topic, state.messages)
        return {
            "messages": [AIMessage(content=response.script, name="moderator")],
            "next_speaker": response.next_speaker
        }

    async def debater_node(self, state: DebateState):
        response = await self.debater_agent.debate_chat(state.topic, state.messages, state.user_side)
        return {
            "messages": [AIMessage(content=response.script, name=state.next_speaker)],
            "next_speaker": "moderator"
        }

    async def human_node(self, state: DebateState):
        return {
            "messages": [],
            "next_speaker": "moderator"
        }
    
    async def judge_node(self, state: DebateState):
        response = await self.judge_agent.judge_chat(state.topic, state.messages)
        return {
            "messages": [AIMessage(content=response.script, name="judge")],
        }

    def router(self, state: DebateState) -> str:
        if state.next_speaker == "judge":
            return "judge"
        
        if state.next_speaker == state.user_side:
            return "human"
        else:
            return "debater"
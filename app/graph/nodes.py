from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import StreamWriter 
from langchain_core.callbacks import adispatch_custom_event
from app.models.schemas import DebateState

from app.agents.debater import DebaterAgent
from app.agents.moderator import ModeratorAgent
from app.agents.judge import JudgeAgent
from app.agents.score import ScoreAgent
from app.agents.base import LLM_USED

class DebateNodes:
    def __init__(self, tools: list = None):
        self.moderator_agent = ModeratorAgent()
        self.debater_agent = DebaterAgent(tools=tools)
        self.judge_agent = JudgeAgent()
        self.score_agent = ScoreAgent()

        self.stream_writer = StreamWriter
    
    async def moderator_node(self, state: DebateState):
        if LLM_USED == "google" and not isinstance(state.messages[-1], HumanMessage):
            state.messages.append(HumanMessage(content="주어진 역할과 상황에 맞게 행동하세요."))
        response, parsed = await self.moderator_agent.moderate_chat(state.topic, state.messages)
        # response 메타데이터 유지하면서 content만 script로 교체
        response = response.model_copy(update={"content": parsed.script, "name": "moderator"})
        return {
            "messages": [response],
            "next_speaker": parsed.next_speaker
        }

    async def debater_node(self, state: DebateState):
        if LLM_USED == "google" and not isinstance(state.messages[-1], (HumanMessage, ToolMessage)):
            state.messages.append(HumanMessage(content="주어진 역할과 상황에 맞게 행동하세요."))
        response = await self.debater_agent.debate_chat(state.topic, state.messages, state.user_side)
        response.name = "debater"
        return {
            "messages": [response],
            "next_speaker": "moderator"
        }

    async def human_node(self, state: DebateState):
        return {
            "messages": [],
            "next_speaker": "moderator"
        }
    
    async def judge_node(self, state: DebateState):
        if LLM_USED == "google" and not isinstance(state.messages[-1], HumanMessage):
            state.messages.append(HumanMessage(content="주어진 역할과 상황에 맞게 행동하세요."))
        response, parsed = await self.judge_agent.judge_chat(state.topic, state.messages)
        # response 메타데이터 유지하면서 content만 script로 교체
        response = response.model_copy(update={"content": parsed.script, "name": "judge"})
        return {
            "messages": [response],
        }

    async def score_node(self, state: DebateState, writer: StreamWriter):
        if LLM_USED == "google" and not isinstance(state.messages[-1], HumanMessage):
            state.messages.append(HumanMessage(content="주어진 역할과 상황에 맞게 행동하세요."))
        response, parsed = await self.score_agent.score_debate(state.topic, state.messages, state.user_side)
        
        await adispatch_custom_event(
                name= "score_update",
                data= response.model_dump()
            )

    def router(self, state: DebateState) -> str:
        if state.next_speaker == "end":
            return "judge"
        if state.next_speaker == state.user_side:
            return "human"
        elif state.next_speaker in ["pro", "con"]:
            return "debater"
        else:
            return "judge"

nodes = DebateNodes()

def set_nodes(tools: list = None):
    global nodes
    nodes = DebateNodes(tools=tools)
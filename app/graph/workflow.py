from typing import Optional
from langchain_core.messages import HumanMessage
from langchain_core.utils.json import parse_partial_json
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.models.schemas import DebateState
from app.graph.nodes import DebateNodes

class DebateWorkflow:
    def __init__(self):
        self.nodes = DebateNodes()
        self.workflow = StateGraph(DebateState)

        self._build_graph()
        
        self.app = None

    def _build_graph(self):
        self.workflow.add_node("moderator", self.nodes.moderator_node)
        self.workflow.add_node("debater", self.nodes.debater_node)
        self.workflow.add_node("human", self.nodes.human_node)
        self.workflow.add_node("judge", self.nodes.judge_node)

        self.workflow.add_edge(START, "moderator")
        self.workflow.add_conditional_edges(
            "moderator",
            self.nodes.router,
            {
                "debater": "debater",
                "human": "human",
                "judge": "judge"
            }
        )
        self.workflow.add_edge("debater", "moderator")
        self.workflow.add_edge("human", "moderator")
        self.workflow.add_edge("judge", END)

    async def compile(self, db_connection):
        checkpointer = AsyncSqliteSaver(db_connection)
        self.app = self.workflow.compile(checkpointer=checkpointer, interrupt_before=["human"])

    async def is_session_valid(self, session_id: str) -> bool:
        config = {"configurable": {"thread_id": session_id}}
        state_snapshot = await self.app.aget_state(config)
        return bool(state_snapshot.values and "topic" in state_snapshot.values)

    async def generate_debate(self, session_id: Optional[str], topic: str, user_side: str):
        import uuid
        if not session_id:
            session_id = str(uuid.uuid4())
            
        config = {"configurable": {"thread_id": session_id}}
        initial_state = {
            "topic": topic,
            "user_side": user_side,
            "next_speaker": "moderator",
            "messages": []
        }
        await self.app.aupdate_state(config, values=initial_state)
        return session_id

    async def user_input(self, session_id: str, user_message: str):
        config = {"configurable": {"thread_id": session_id}}
        state = await self.app.aget_state(config)
        speaker = state.values.get("user_side", "unknown")
        
        await self.app.aupdate_state(
            config,
            values={
                "messages": [HumanMessage(content=user_message, name=speaker)],
                "next_speaker": "moderator"
            },
            as_node="human"
        )

    async def run_debate(self, session_id: Optional[str]):
        chat_scripts = {}
        config = {"configurable": {"thread_id": session_id}}

        async for msg, metadata in self.app.astream(
            None, 
            config, 
            stream_mode="messages"
        ):
            yield {"type": "node", "node": metadata["langgraph_node"]}

            if metadata["langgraph_node"] == "human":
                continue

            step = metadata["langgraph_step"]
            incoming_chunk = None
            
            if hasattr(msg, 'tool_call_chunks') and msg.tool_call_chunks:
                incoming_chunk = msg.tool_call_chunks[0]["args"]
            elif msg.content:
                incoming_chunk = msg.content
            
            if incoming_chunk:
                if step not in chat_scripts:
                    chat_scripts[step] = ""
                chat_scripts[step] += incoming_chunk

                try:
                    parsed_content = parse_partial_json(chat_scripts[step])
                    if isinstance(parsed_content, dict) and "script" in parsed_content:
                        yield {
                            "type": "message",
                            "node": metadata["langgraph_node"],
                            "content": parsed_content["script"]
                        }
                except Exception:
                    pass
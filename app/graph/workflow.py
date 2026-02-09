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
        self.workflow.add_node("score", self.nodes.score_node)

        self.workflow.add_edge(START, "moderator")
        self.workflow.add_conditional_edges(
            "moderator",
            self.nodes.router,
            {
                "debater": "debater",
                "human": "human",
                "end": "judge"
            }
        )
        self.workflow.add_edge("debater", "moderator")
        self.workflow.add_edge("human", "moderator")
        self.workflow.add_edge("human", "score")
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

        async for event in self.app.astream_events(
            None,
            config,
            version="v2"
        ):
            event_type = event.get("event", "Unkown")

            metadata = event.get("metadata", {})
            node = metadata.get("langgraph_node", None)

            if not node or node == "human":
                continue
            
            # 노드 정보 전송
            if event_type in ("on_chat_model_stream", "on_chat_event"):
                yield {"type": "node", "node": node}

            # 커스텀 이벤트 처리
            if event_type == "on_custom_event":
                if event["name"] == "score_update":
                    data = event["data"]

                    yield {
                        "type": "score_update",
                        "content": data["scores"]
                    }
                    continue
            
            if node == "score":
                continue

            if event_type == "on_chat_model_stream":
                chunk = event["data"]["chunk"]

                step = metadata.get("langgraph_step", event.get("run_id"))

                incoming_chunk = None
                message_type = "unknown"
                tool_name = None

                # 툴 호출 청크
                if chunk.tool_call_chunks:
                    tool_info = chunk.tool_call_chunks[0]
                    tool_name = tool_info.get("name", "unknown_tool")
                    incoming_chunk = tool_info.get("args")
                    message_type = "tool_call"
                # 일반 메시지 청크
                elif chunk.content:
                    incoming_chunk = chunk.content
                    message_type = "output"

                if incoming_chunk:
                    if step not in chat_scripts:
                        chat_scripts[step] = ""
                    
                    chat_scripts[step] += incoming_chunk

                    try:
                        parsed_content = parse_partial_json(chat_scripts[step])
                        
                        if isinstance(parsed_content, dict):
                            yield {
                                "type": "message",
                                "node": node,
                                "message_type": message_type,
                                "script": parsed_content["script"],
                                "full_content": parsed_content,
                                "tool_name": tool_name
                            }
                    except Exception:
                        pass
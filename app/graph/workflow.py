from typing import Optional, Literal
from langchain_core.messages import HumanMessage
from langchain_core.utils.json import parse_partial_json
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.prebuilt import ToolNode, tools_condition
import json

from app.models.schemas import DebateState
from app.graph.nodes import set_nodes, nodes
from app.agents.base import LLM_USED
from app.tools.tool_manager import tool_manager
import logging

logger = logging.getLogger(__name__)

class DebateWorkflow:
    def __init__(self):
        self.workflow = StateGraph(DebateState)
        self.tools = tool_manager.get_tools()
        if len(self.tools) > 0:
            set_nodes(tools=self.tools)
        self.nodes = nodes
        
        self.tool_map = {'tavily_search': 'search'}
        self.pass_events = ("on_prompt_start", "on_prompt_end", "on_chain_stream", "on_chat_model_start", "on_parser_start", "on_parser_end")

        self._build_graph()
        
        self.app = None
        self.current_step = dict()  # Track current step for each session

    def _build_graph(self):
        self.workflow.add_node("moderator", self.nodes.moderator_node)
        self.workflow.add_node("debater", self.nodes.debater_node)
        self.workflow.add_node("human", self.nodes.human_node)
        self.workflow.add_node("judge", self.nodes.judge_node)
        self.workflow.add_node("score", self.nodes.score_node)
        self.workflow.add_node("tools", ToolNode(self.tools))

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
        
        self.workflow.add_conditional_edges(
            "debater",
            tools_condition, 
            {
                "tools": "tools",  # 툴 호출 시 -> tools 노드로
                END: "moderator"   # 툴 호출 없으면(발언 끝) -> moderator로
            }
        )
        self.workflow.add_edge("tools", "debater")
        self.workflow.add_edge("human", "moderator")
        self.workflow.add_edge("human", "score")
        self.workflow.add_edge("judge", END)

    async def compile(self, db_connection):
        checkpointer = AsyncSqliteSaver(db_connection)
        await checkpointer.setup()

        self.app = self.workflow.compile(checkpointer=checkpointer, interrupt_before=["human"])

    async def is_session_valid(self, session_id: str) -> bool:
        if self.app is None:
            raise RuntimeError("ERROR: Workflow not compiled.")
        config = {"configurable": {"thread_id": session_id}}
        state_snapshot = await self.app.aget_state(config)
        return bool(state_snapshot.values and "topic" in state_snapshot.values)

    async def generate_debate(self, session_id: Optional[str], topic: str, user_side: Literal["pro", "con"]):
        if self.app is None:
            raise RuntimeError("ERROR: Workflow not compiled.")
        import uuid
        if not session_id:
            session_id = str(uuid.uuid4())
            
        config = {"configurable": {"thread_id": session_id}}
        initial_state = {
            "topic": topic,
            "user_side": user_side,
            "next_speaker": "moderator",
            "messages": [HumanMessage(content="토론 시작")] if LLM_USED == "google" else [],
        }
        await self.app.aupdate_state(config, values=initial_state)
        return session_id

    async def user_input(self, session_id: str, user_message: str):
        if self.app is None:
            raise RuntimeError("ERROR: Workflow not compiled.")
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
        if self.app is None:
            raise RuntimeError("ERROR: Workflow not compiled.")
        chat_scripts = {}
        config = {"configurable": {"thread_id": session_id}}

        async for event in self.app.astream_events(
            None,
            config,
            version="v2"
        ):
            event_type = event.get("event", "Unknown")
            event_name = event.get("name", "Unknown")
            metadata = event.get("metadata", {})
            node = metadata.get("langgraph_node", None)
            step = metadata.get("langgraph_step", None)
            data = event.get("data", {})
            
            # Update current step
            if step is not None:
                self.current_step[session_id] = step

            if node is None:
                continue
            if event_type in self.pass_events:
                continue
            elif event_type == "on_chain_start":
                yield {
                    "type": "node_start",
                    "node": node,
                    "step": step,
                    "content": {
                        "name": event_name
                    }
                }
            elif event_type == "on_chain_end":
                yield {
                    "type": "node_end",
                    "node": node,
                    "step": step,
                    "content": {
                        "name": event_name
                    }
                }        
            elif event_type == "on_chat_model_stream":
                chunk = data.get("chunk", "").content
                if step not in chat_scripts:
                    chat_scripts[step] = ""
                if isinstance(chunk, list):
                    if len(chunk) == 0:
                        continue
                    chunk = chunk[0]["text"]
                chat_scripts[step] += chunk

                if node in ["moderator", "judge"]:
                    try:
                        parsed = parse_partial_json(chat_scripts[step])
                    except:
                        parsed = None
                else:
                    parsed = {"script": chat_scripts[step]}
                
                yield {
                    "type": "message",
                    "node": node,
                    "step": step,
                    "content": {
                        "status": "streaming",
                        "json_message": parsed,
                        "raw_message": chat_scripts[step],
                        "chunk": chunk
                    }
                }
            elif event_type == "on_chat_model_end":
                output = data.get("output")
                if output is None:
                    logger.warning(f"No output found in on_chat_model_end event for node: {node}, step: {step}")
                    continue
                else:
                    content = getattr(output, "content")
                if content is None:
                    logger.warning(f"No content found in output for on_chat_model_end event for node: {node}, step: {step}")
                    continue
                if node in ["moderator", "judge"]:
                    try:
                        parsed = parse_partial_json(content)
                    except:
                        parsed = None
                else:
                    parsed = {"script": content}
                
                if step in chat_scripts:
                    yield {
                        "type": "message_complete",
                        "node": node,
                        "step": step,
                        "content": {
                            "status": "complete",
                            "json_message": parsed,
                            "raw_message": content,
                        }
                    }
                    del chat_scripts[step]
            elif event_type == "on_tool_start":
                tool_name = self.tool_map.get(event_name, event_name)
                if tool_name == "search":
                    yield {
                        "type": "tool_start",
                        "node": node,
                        "step": step,
                        "content": {
                            "tool_name": tool_name,
                            "query": data['input']['query'],
                            "topic": data['input'].get('topic', None)
                        }
                    }
            elif event_type == "on_tool_end":
                tool_name = self.tool_map.get(event_name, event_name)
                if tool_name == "search":
                    content = json.loads(data.get("output").content)
                    results = content.get("results", [])
                    response_time = content.get("response_time", None)

                    results_dict = {}
                    for idx, res in enumerate(results, start=1):
                        results_dict[f"result{idx}"] = {
                            "url": res.get("url") if isinstance(res, dict) else getattr(res, "url", None),
                            "title": res.get("title") if isinstance(res, dict) else getattr(res, "title", None),
                            "date": res.get("published_date") if isinstance(res, dict) else getattr(res, "published_date", None)
                        }

                    yield {
                        "type": "tool_end",
                        "node": node,
                        "step": step,
                        "content": {
                            "tool_name": tool_name,
                            "results": results_dict,
                            "response_time": response_time,
                        }
                    }
            elif event_type == "on_custom_event" and event_name == "score_update":
                yield {
                    "type": "score_update",
                    "node": node,
                    "step": step,
                    "content": {
                        "scores": {
                            "reasoning": data.get("reasoning"),
                            "substantiality": data.get("substantiality"),
                            "manner": data.get("manner")
                        }
                    }
                }
            else:
                logger.warning(f"Unhandled event type: {event_type} in node: {node} with data: {data}")

workflow = DebateWorkflow()
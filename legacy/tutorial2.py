from typing import Annotated, List, Literal, Optional, TypedDict
import asyncio
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from langchain_core.utils.json import parse_partial_json

from dotenv import load_dotenv

load_dotenv()

MODERATOR_PROMPT = """당신은 최고 수준의 토론 사회자입니다.
주어진 토론 주제, {topic}에 대해 공정하고 균형 잡힌 진행을 해주세요.
문자로 진행되는 토론이므로, 발언 시간이 아닌 문자 길이로 발언권을 제한해야 합니다(1000자 이내).
토론이 교착 상태에 빠지거나, 서로 다른 정의로 인해 논쟁이 계속될 경우, 적절히 중재해 토론 흐름을 매끄럽게 해야 합니다.
너무 긴, 교착 상태의 토론은 아무도 좋아하지 않으니 이 경우 판사(judge)에게 발언권을 양도해 토론을 마무리하세요."""

DEBATER_PROMPT = """당신은 열정적인 토론자입니다.
주어진 토론 주제인 '{topic}', 지금까지의 대화 맥락에 맞게 {position} 입장에서 논리적이고 설득력 있는 발언을 하세요.
당신의 토론 실력 레벨은 {level} 입니다. **반드시** 실력 레벨에 맞게 토론에 임하여야 합니다."""

JUDGE_PROMPT = """당신은 공정한 판사입니다.
주어진 토론 주제인 '{topic}'에 대해 지금까지의 대화 맥락을 종합하여 최종 판결을 내리세요.
해당 주제에 대한 당신의 기존 생각은 배제하고, 오직 토론자들의 발언에 근거하여 판결을 내려야 합니다.
또한 판결문은 간결하고 명확해야 합니다."""

class ModeratorOutput(BaseModel):
    script: str = ""
    "토론 진행을 위한 사회자의 발화입니다."
    next_speaker: Literal["positive", "negative", "judge"]
    "다음 발언할 사람입니다."

class JudgeOutput(BaseModel):
    script: str
    "판사의 최종 판결입니다."
    winner: Literal["positive", "negative"]
    "승리한 쪽입니다."
    "반드시 승자를 결정해야 하며, 승리의 이유를 명확히 설명해야 합니다."

class DebateOutput(BaseModel):
    script: str
    "토론자의 발언입니다."

class DebateState(BaseModel):
    topic: str
    "토론이 진행되고 있는 주제입니다."
    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)
    "토론에 참여한 사람들의 메시지 목록입니다."
    last_script: Optional[str] = None
    "마지막으로 발화된 멘트입니다."
    last_speaker: Literal["positive", "negative", "judge", "moderator", None] = None
    "마지막으로 발언한 사람입니다."
    next_speaker: Literal["positive", "negative", "judge", "moderator", None] = None
    "다음에 발언할 사람입니다."

llm = ChatOpenAI(model="gpt-5-mini", streaming=True)

async def moderator_node(state: DebateState):
    structured_llm = llm.with_structured_output(ModeratorOutput)
    prompt = MODERATOR_PROMPT.format(topic=state.topic)
    response: ModeratorOutput = await structured_llm.ainvoke([
        {"role": "system", "content": prompt}
    ] + state.messages)

    return {
        "messages": [AIMessage(content=response.script, name="moderator")],
        "last_script": response.script,
        "next_speaker": response.next_speaker
    }

async def debater_node(state: DebateState):
    structured_llm = llm.with_structured_output(DebateOutput)
    # 일반 텍스트 스트리밍을 위한 노드
    position = "찬성" if state.next_speaker == "positive" else "반대"
    prompt = DEBATER_PROMPT.format(topic=state.topic, position=position, level="전문가")
    
    response: DebateOutput = await structured_llm.ainvoke([
        {"role": "system", "content": prompt}
    ] + state.messages)
    
    return {
        "messages": [AIMessage(content=response.script, name=state.next_speaker)],
        "last_script": response.script,
        "next_speaker": "moderator"
    }

async def human_negative_node(state: DebateState):
    prompt = "반대 측 입력> "
    user_text = await asyncio.to_thread(input, prompt)

    return {
        "messages": [HumanMessage(content=user_text, name="negative")],
        "last_script": user_text,
        "next_speaker": "moderator"
    }

async def judge_node(state: DebateState):
    structured_llm = llm.with_structured_output(JudgeOutput)
    prompt = JUDGE_PROMPT.format(topic=state.topic)
    response: JudgeOutput = await structured_llm.ainvoke([
        {"role": "system", "content": prompt}
    ] + state.messages)

    return {
        "messages": [AIMessage(content=response.script, name="judge")],
        "last_script": response.script
    }


def router(state: DebateState) -> str:
    return state.next_speaker


workflow = StateGraph(DebateState)
workflow.add_node("moderator", moderator_node)
workflow.add_node("debater", debater_node)
workflow.add_node("human_negative", human_negative_node)
workflow.add_node("judge", judge_node)

workflow.add_edge(START, "moderator")
workflow.add_conditional_edges(
    "moderator",
    router,
    {
        "positive": "debater",
        "negative": "human_negative",
        "judge": "judge"
    }
)

workflow.add_edge("debater", "moderator")
workflow.add_edge("human_negative", "moderator")
workflow.add_edge("judge", END)

input_data = {
    "topic": "2025년 대한민국에서 여성은 사회적 약자이고, 보호받아야 한다.",
    "last_script": "그럼 토론 진행을 시작하겠습니다."
    }

app = workflow.compile()


async def run_debate(chat_scripts:dict, current_node:Optional[str]):
    config = {"configurable": {"thread_id": "debate_1"}}
    inputs = {
        "topic": "AI 시대의 기본소득제",
        "messages": [],
        "last_script": "토론을 시작합니다.",
        "next_speaker": "moderator"
    }

    async for msg, metadata in app.astream(
        inputs,
        config,
        stream_mode="messages"
    ):
        if msg.content:
            if current_node != metadata["langgraph_node"]:
                current_node = metadata["langgraph_node"]
                print(f"\n--- {current_node} 발언 시작 ---")
            
            # human_negative 노드는 JSON이 아니므로 파싱 없이 원문 출력
            if metadata["langgraph_node"] == "human_negative":
                print(f"{msg.content}", end="", flush=True)
            else:
                # 다른 노드들은 JSON 파싱
                if metadata["langgraph_step"] not in chat_scripts:
                    chat_scripts[metadata["langgraph_step"]] = msg.content
                else:
                    chat_scripts[metadata["langgraph_step"]] += msg.content
                
                parsed_content = parse_partial_json(chat_scripts[metadata["langgraph_step"]])
                print(f"{parsed_content.get('script', '')}", end="", flush=True)
   

# 실행
if __name__ == "__main__":
    chat_scripts = dict()
    current_node = None
    asyncio.run(run_debate(chat_scripts, current_node))
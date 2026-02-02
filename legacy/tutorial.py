from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from typing import Annotated, List, Literal
import operator

class DebateState(BaseModel):
    topic: str
    "토론이 진행되고 있는 주제입니다."
    messages: Annotated[List[str], operator.add] = Field(default_factory=list)
    "토론에 참여한 사람들의 메시지 목록입니다."
    turn_count: int = 0
    "현재까지 진행된 토론 턴 수입니다."

def moderator_node(state: DebateState):
    print(f"\n--- [사회자] {state.turn_count}번째 턴 정리 중... ---")
    # 사회자가 턴을 하나 올립니다.
    return {"turn_count": state.turn_count + 1}

def debater_node(state: DebateState):
    print(f"--- [토론자] {state.turn_count}번째 발언 중 ---")
    return {"messages": [f"토론자: {state.turn_count}번째 반론입니다!"]}

def user_node(state: DebateState):
    return {}

def judge_node(state: DebateState):
    print("--- [판사] 최종 판결 ---")
    return {"messages": ["판사: 양측의 의견을 종합하여 찬성 측 승리를 선언합니다!"]}

# [3. 루프 결정 함수 (Router)]
def should_continue(state: DebateState) -> Literal["debater", "judge"]:
    # 턴이 3번 넘어가면 판사에게, 아니면 다시 토론자에게!
    if state.turn_count >= 5:
        return "judge"
    elif state.turn_count >= 3:
        return "user"
    return "debater"

workflow = StateGraph(DebateState)

workflow.add_node("moderator", moderator_node)
workflow.add_node("debater", debater_node)
workflow.add_node("user", user_node)
workflow.add_node("judge", judge_node)

workflow.add_edge(START, "moderator")
workflow.add_conditional_edges(
    "moderator",
    should_continue,
    {
        "debater": "debater",
        "judge": "judge",
        "user": "user"
    }
)
workflow.add_edge("debater", "moderator")
workflow.add_edge("user", "moderator")
workflow.add_edge("judge", END)

memory = MemorySaver()
app = workflow.compile(checkpointer=memory, interrupt_before=["user"])

thread_config = {"configurable": {"thread_id": "debate_1"}}
input_data = {"topic": "AI의 권리", "messages": []}
while True:
    events = app.stream(input_data if input_data else None, thread_config)

    for event in events:
        print(event)

    state = app.get_state(thread_config)

    if "user" in state.next:
        user_input = input("\n[사용자 입력 칸]: ")
        app.update_state(thread_config, {"messages": [f"사용자: {user_input}"]}, as_node="user")
        input_data = None
    else:
        break
state = app.get_state(thread_config)
for msg in state.values.get("messages", []):
    print(msg)
print("\n=== 모든 토론 절차가 완료되었습니다 ===")
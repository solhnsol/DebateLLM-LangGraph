from typing import Annotated, List, Literal, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

type MessageList = list[BaseMessage]

class DebateState(BaseModel):
    topic: str
    "토론이 진행되고 있는 주제입니다."

    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)
    "토론에 참여한 사람들의 메시지 목록입니다."

    next_speaker: Literal["positive", "negative", "judge", "moderator", None] = None
    '''
    다음에 발언할 사람입니다.
    Positive: 찬성측 토론자
    Negative: 반대측 토론자
    Judge: 심사위원(발언 후 토론이 무조건 종료됩니다.)
    Moderator: 사회자
    '''

    user_side: Literal["positive", "negative"]
    "사용자가 맡은 토론자 역할입니다."

class ModeratorOutput(BaseModel):
    script: str
    "사회자의 멘트"
    next_speaker: Literal["positive", "negative", "judge"]
    "다음 발언자 지정"

class DebaterOutput(BaseModel):
    script: str
    "토론자의 발언"

class JudgeOutput(BaseModel):
    script: str
    "심사위원의 평가 멘트"
    winner: Literal["positive", "negative"]
    "승리한 쪽"
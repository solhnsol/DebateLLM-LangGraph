from typing import Annotated, List, Literal, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

type MessageList = list[BaseMessage]

# API 입출력 관련 스키마
class DebateInitiateRequest(BaseModel):
    topic: str
    "해당 세션에서 토론할 주제입니다."
    user_side: Literal["pro", "con"]
    "사용자가 맡을 토론자 역할입니다."
    session_id: Optional[str] = None
    "생성한 세션의 id입니다. 지정하지 않으면 새로 생성됩니다."

# 에이전트 출력 관련 스키마
class ModeratorOutput(BaseModel):
    script: str
    "사회자의 멘트"
    next_speaker: Literal["pro", "con", "end"]
    "다음 발언자 지정 혹은 토론 종료"

class JudgeOutput(BaseModel):
    script: str
    "심사위원의 평가 멘트"
    winner: Literal["pro", "con"]
    "승리한 쪽"

class ScoreOutput(BaseModel):
    reasoning: int = Field(..., ge=0, le=100)
    "논리 점수 (0-100)"
    substantiality: int = Field(..., ge=0, le=100)
    "근거 점수 (0-100)"
    manner: int = Field(..., ge=0, le=100)
    "전달력 및 매너 점수 (0-100)"
    script: str
    "점수 부여 이유에 대한 매우 짧은 설명 멘트"

# 그래프 상태 관련 스키마
class DebateState(BaseModel):
    topic: str
    "토론이 진행되고 있는 주제입니다."

    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)
    "토론에 참여한 사람들의 메시지 목록입니다."

    next_speaker: Literal["pro", "con", "end", "moderator", None] = None
    '''
    다음에 발언할 사람입니다.
    Pro: 찬성측 토론자
    Con: 반대측 토론자
    End: 토론 종료
    Moderator: 사회자
    '''

    user_side: Literal["pro", "con"]
    "사용자가 맡은 토론자 역할입니다."
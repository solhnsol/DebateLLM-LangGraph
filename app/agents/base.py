from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage
from pydantic import BaseModel
from typing import Type, Any

from dotenv import load_dotenv
import os

load_dotenv()

LLM_USED = os.environ.get("LLM_USED")
REASONING = os.environ.get("REASONING")

llms_available = ["google", "openai"]

if not LLM_USED:
    raise RuntimeError("ERROR: LLM_USED Not Set.")
if LLM_USED not in llms_available:
    raise RuntimeError(f"ERROR: Invalid LLM_USED value. Available options: {llms_available}")

openai_reasoning_effort = {
    "low": "low",
    "medium": "medium",
    "high": "high"
}

class BaseAgent:
    _instances = {}

    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[cls] = instance
        return cls._instances[cls]
    
    def __init__(self, model_name: str = None, temperature: float = None, output_schema: Type[BaseModel] = None, tools: list = None):
        """
        Args:
            model_name: 사용할 LLM 모델명
            output_schema: 구조화된 출력을 위한 Pydantic 클래스 (None이면 일반 텍스트)
        """
        self.output_schema = output_schema

        if LLM_USED == "google":
            if temperature is None:
                temperature = 0.4 if output_schema else 0.7
            if not model_name:
                model_name = os.environ.get("MODEL_GOOGLE")
            self.llm = ChatGoogleGenerativeAI(
                model=model_name,
                temperature=temperature,
                streaming=True
            )
        
        elif LLM_USED == "openai":
            if temperature is None:
                temperature = 0.4 if output_schema else 0.7
            if not model_name:
                model_name = os.environ.get("MODEL_OPENAI")
            reasoning_effort = openai_reasoning_effort.get(REASONING)
            if not reasoning_effort:
                raise RuntimeError("ERROR: Invalid REASONING value for OpenAI LLM.")
            self.llm = ChatOpenAI(model_name=model_name, temperature=temperature, reasoning_effort=reasoning_effort)
        
        if output_schema:
            self.llm = self.llm.with_structured_output(output_schema, include_raw=True)
        elif tools:
            self.llm = self.llm.bind_tools(tools)
        
        
    
    def _create_prompt(self, system_instruction: str) -> ChatPromptTemplate:
        """
        공통 프롬프트 템플릿 생성 (System Message + 대화 기록)
        """
        return ChatPromptTemplate.from_messages([
            ("system", system_instruction),
            MessagesPlaceholder(variable_name="messages")
        ])

    async def get_response(self, system_prompt: str, messages: list) -> AIMessage:
        """
        실제 LLM 호출 메서드
        Args:
            system_prompt: 포맷팅이 완료된 시스템 프롬프트 문자열
            messages: 대화 기록 리스트
        """

        # 프롬프트 템플릿 생성
        prompt_template = self._create_prompt(system_prompt)
        
        # 체인 생성 (Prompt -> LLM)
        chain = prompt_template | self.llm
        
        # 비동기 실행
        response = await chain.ainvoke({
            "messages": messages
        })
        if self.output_schema:
            return response["raw"], response["parsed"]
        return response, None
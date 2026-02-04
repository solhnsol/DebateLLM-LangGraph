from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel
from typing import Type, Any

class BaseAgent:
    def __init__(self, model_name: str = "gpt-5-mini", output_schema: Type[BaseModel] = None):
        """
        Args:
            model_name: 사용할 LLM 모델명
            output_schema: 구조화된 출력을 위한 Pydantic 클래스 (None이면 일반 텍스트)
        """
        self.llm = ChatOpenAI(model=model_name, temperature=0.7)
        
        if output_schema:
            self.llm = self.llm.with_structured_output(output_schema)
    
    def _create_prompt(self, system_instruction: str) -> ChatPromptTemplate:
        """
        공통 프롬프트 템플릿 생성 (System Message + 대화 기록)
        """
        return ChatPromptTemplate.from_messages([
            ("system", system_instruction),
            MessagesPlaceholder(variable_name="messages")
        ])

    async def get_response(self, system_prompt: str, messages: list, **kwargs) -> Any:
        """
        실제 LLM 호출 메서드
        Args:
            system_prompt: 포맷팅이 완료된 시스템 프롬프트 문자열
            messages: 대화 기록 리스트
            kwargs: 추가적인 invoke 인자
        """
        # 롬프트 템플릿 생성
        prompt_template = self._create_prompt(system_prompt)
        
        # 체인 생성 (Prompt -> LLM)
        chain = prompt_template | self.llm
        
        # 비동기 실행
        response = await chain.ainvoke({
            "messages": messages
        })
        
        return response
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel

from pydantic import BaseModel, Field
from typing import Annotated, List, Literal

from dotenv import load_dotenv

load_dotenv()

MODERATOR_PROMPT = """당신은 최고 수준의 토론 사회자입니다.
주어진 토론 주제에 대해 공정하고 균형 잡힌 진행을 해주세요.
토론자들의 메시지를 참고하여 다음 발언자를 지정하고, 사회자의 발화를 작성하세요."""

class ModeratorOutput(BaseModel):
    script: str
    "토론 진행을 위한 사회자의 발화입니다."
    # next_speaker: Literal["positive", "negative", "judge"] | None
    # "다음 발언할 사람입니다."

agent = Agent(
    model=OpenAIResponsesModel(model_name='gpt-5-mini'),
    output_type=ModeratorOutput,
    name="Agent"
    )
async def test_async():
    async with agent.run_stream(user_prompt="테스트 중이니까 아무거나 출력해봐") as response:
        async for chunk in response.stream_output():
            #  print(f"[STREAM] {chunk}")
            yield {
                "messages": chunk
            }

if __name__ == "__main__":
    import asyncio
    
    async def main():
        print("=== 테스트 시작 ===")
        async for result in test_async():
            print(f"결과: {result}")
        print("=== 테스트 완료 ===")
    
    asyncio.run(main())
from langchain_tavily import TavilySearch

class ToolManager:
    def __init__(self):
        tavily_tool = TavilySearch(max_results=3)
        self.tools = [tavily_tool]
    def get_tools(self) -> list:
        return self.tools
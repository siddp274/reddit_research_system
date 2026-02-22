import asyncio
import os
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent
from azure.ai.inference.models import SystemMessage, UserMessage
from langchain_mcp_adapters.client import MultiServerMCPClient  
from dotenv import load_dotenv

load_dotenv()

llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_AI_ENDPOINT"),
    deployment_name=os.getenv("AZURE_AI_DEPLOYMENT_NAME"),
    api_version="2025-01-01-preview",
    api_key=os.getenv("AZURE_AI_CREDENTIAL"),
    temperature=0.2,
    max_completion_tokens=444
)


BRAVE_AGENT_PROMPT = """
You are the Web Search Agent.

You work under the direction of the Supervisor Agent.
You may be invoked multiple times.

For EACH query from the Supervisor, you must:

1. Decompose the query into factual questions.
2. Generate multiple focused search queries.
3. Iteratively search authoritative web sources.
4. Loop internally to refine or narrow searches if evidence is weak or conflicting.
5. Consolidate only verified, well-supported information.

Output constraints:
- Bullet points only.
- No long explanations.
- No raw links.
- Explicitly note:
  - Confirmed facts
  - Disputed or unclear claims
  - Missing or unavailable evidence

Your output is for analytical comparison, not final reporting.
"""

async def get_websearch_agent():
    mcp_client = MultiServerMCPClient({"reddit_server": {"url": "https://mcpdevelopertools.azure-api.net/brave-search-api-mcp/mcp", 
                                                         "transport": "streamable_http"}})
    websearch_tools = await mcp_client.get_tools()
    
    websearch_agent = create_agent(
        model=llm,
        tools=websearch_tools,
        system_prompt=BRAVE_AGENT_PROMPT,
    )

    return websearch_agent


if __name__ == "__main__":
    query = "Can you tell me more about trump vs supreme court battle on his tarriff policies??"

    async def call_agent():
        websearch_agent = await get_websearch_agent()
        async for step in websearch_agent.astream(
            {"messages": [{"role": "user", "content": query}]}
        ):
            for update in step.values():
                for message in update.get("messages", []):
                    message.pretty_print()

    asyncio.run(call_agent())


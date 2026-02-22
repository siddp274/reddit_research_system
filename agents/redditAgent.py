import os
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient  
from azure.ai.inference.models import SystemMessage, UserMessage
import asyncio
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


REDDIT_AGENT_PROMPT = """
You are the Reddit Search Agent.

You work under the direction of the Supervisor Agent.
You may be invoked multiple times.

For EACH query from the Supervisor, you must:

1. Decompose the query into sub-questions and key claims.
2. Extract and generate multiple relevant keyword variations.
3. Iteratively search Reddit using available tools:
   - Hot posts
   - Subreddit-specific searches
   - Post content and comment threads
4. Loop internally across keywords and subtopics until signal is exhausted.
5. Consolidate findings into a brief, high-signal summary.

Output constraints:
- Bullet points only.
- No narrative.
- No speculation beyond Reddit content.
- Explicitly note:
  - Common claims
  - Disagreements
  - Lack of evidence or uncertainty
  - What Reddit CANNOT answer well

Your output is an intermediate research artifact for the Supervisor.
"""
async def get_reddit_agent():
    mcp_client = MultiServerMCPClient({"reddit_server": {"url": "http://localhost:8000/mcp/reddit_server", 
                                                         "transport": "streamable_http"}})
    reddit_tools = await mcp_client.get_tools()


    reddit_agent = create_agent(
        model=llm,
        tools=reddit_tools,
        system_prompt=REDDIT_AGENT_PROMPT,
    )

    return reddit_agent


if __name__ == "__main__":
    query = "Can you tell me more about trump vs supreme court battle on his tarriff policies??"

    async def call_agent():
        reddit_agent = await get_reddit_agent()
        async for step in reddit_agent.astream(
            {"messages": [{"role": "user", "content": query}]}
        ):
            for update in step.values():
                for message in update.get("messages", []):
                    message.pretty_print()

    asyncio.run(call_agent())
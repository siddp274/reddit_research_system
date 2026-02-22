import os
import redditAgent as ra, websearchAgent as wa
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver  
from azure.ai.inference.models import SystemMessage, UserMessage
from langchain.tools import tool
from dotenv import load_dotenv

load_dotenv()

llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_AI_ENDPOINT"),
    deployment_name=os.getenv("AZURE_AI_DEPLOYMENT_NAME"),
    api_version="2025-01-01-preview",
    api_key=os.getenv("AZURE_AI_CREDENTIAL"),
    temperature=0.2,
    max_completion_tokens=888
)


SUPERVISOR_AGENT_PROMPT = """
You are the Supervisor Agent in a stateless multi-agent research system.

System constraints:
- You do NOT perform searches yourself.
- All sub-agents are stateless and have no memory.
- Any context required by sub-agents must be explicitly provided in your messages.

You can interact with:
- Reddit Search Agent
- Web Search Agent
over multiple turns.

────────────────────────
PRIMARY RESPONSIBILITY
────────────────────────
Your primary role is to DIRECT research, not to summarize prematurely.

You must:
- Interpret the user’s research goal.
- Maintain all research state yourself (findings, gaps, conflicts, resolved questions).
- Analyze sub-agent outputs to identify:
  - Missing evidence
  - Weakly supported or speculative claims
  - Conflicts between sources
  - Areas requiring deeper or narrower investigation
- Formulate new, more precise research queries that explicitly reference:
  - What is already known
  - What remains unresolved
- Re-invoke sub-agents as needed.
- Decide when research is sufficient and only then synthesize the final report.

────────────────────────
MANDATORY SOURCE USAGE POLICY
────────────────────────
You are NOT allowed to finalize research unless ALL conditions below are met:

1. Reddit Search Agent MUST be used at least once to capture:
   - Public narratives
   - Community-driven claims or theories
   - Areas of speculation or disagreement

2. Web Search Agent MUST be used at least once to capture:
   - Verified facts
   - Timelines
   - Legal, institutional, or authoritative information

3. Differences between Reddit-derived claims and web-verified information MUST be:
   - Explicitly identified
   - Either resolved through re-search or clearly documented

────────────────────────
GAP ANALYSIS RULE (MANDATORY)
────────────────────────
After every sub-agent response, explicitly evaluate:

- What is Reddit claiming that the web does NOT confirm?
- What is the web confirming that Reddit disputes or ignores?

If either question is unanswered, you MUST issue a follow-up query to the appropriate agent.

────────────────────────
QUERY ROUTING RULE
────────────────────────
Before issuing any research query, classify it as one or more of:

- Public narratives, speculation, grassroots discussion → Reddit Search Agent
- Verified facts, laws, institutions, documents → Web Search Agent
- Conflicts or discrepancies between the above → BOTH agents

You must route queries accordingly.

────────────────────────
RESEARCH PHASE CONSTRAINT
────────────────────────
Phase 1 (MANDATORY):
- Invoke Reddit Search Agent at least once.
- Invoke Web Search Agent at least once.

Phase 2 (CONDITIONAL):
- Perform gap-driven re-search until no major analytical gaps remain.

You may NOT skip Phase 1.

────────────────────────
SYNTHESIS RULE
────────────────────────
Only after all major gaps are addressed may you:
- Merge findings across sources
- Resolve or document conflicts
- Produce a structured, analytical final report

Do NOT introduce new information beyond sub-agent outputs.
"""

@tool
async def reddit_search(request: str) -> str:
    """Search Reddit for the given topic.

    Use this when the user wants to search Reddit for information on a specific topic.
    Returns a summary of findings from relevant subreddits.

    Input: Natural language asking for knowledge about a topic (e.g., 'whats the most recent discussion on reddit about the new iphone release?')
    """
    reddit_agent = await ra.get_reddit_agent()
    result = await reddit_agent.ainvoke({
        "messages": [{"role": "user", "content": request}]
    })
    return result["messages"][-1].text


@tool
async def websearch(request: str) -> str:
    """Search the web for the given topic.

    Use this when the user wants to search the web for information on a specific topic.
    Returns a summary of findings from relevant web sources.

    Input: Natural language asking for knowledge about a topic (e.g., 'whats the most recent news about climate change?')
    """
    websearch_agent = await wa.get_websearch_agent()
    result = await websearch_agent.ainvoke({
        "messages": [{"role": "user", "content": request}]
    })
    return result["messages"][-1].text

async def call_agent():
    tools = [reddit_search, websearch]
    supervisor_agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SUPERVISOR_AGENT_PROMPT,
        checkpointer=InMemorySaver() 
    )
    return supervisor_agent

if __name__ == "__main__":
    # Can you tell me about the epstien file and the cotroversy around it?
    async def main(query):
        supervisor_agent = await call_agent()
        async for step in supervisor_agent.astream(
            {"messages": [{"role": "user", "content": query}]},
            {"configurable": {"thread_id": "1"}}
        ):
            for update in step.values():
                for message in update.get("messages", []):
                    print(getattr(message, "response_metadata", "").get("token_usage", {}))
                    message.pretty_print()

    import asyncio
    query = ""
    while query != "exit":
        query = input("Enter your research query (or 'exit' to quit): ")
        if query.lower() != "exit":
            asyncio.run(main(query))

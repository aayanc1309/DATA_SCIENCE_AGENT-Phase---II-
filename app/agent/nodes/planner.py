"""
Planner node logic: Determines the steps needed to fulfill the user's query.
"""

import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.config import settings
from app.agent.state import AgentState
from app.agent.prompts import PLANNER_PROMPT


class AnalysisPlan(BaseModel):
    """Pydantic model to enforce structured output for the plan."""
    steps: list[str] = Field(description="A sequential list of 2 to 4 concrete analysis steps")


async def planner_node(state: AgentState) -> dict:
    """
    Given the data schema and user query, create a step-by-step plan.
    """
    print(f"🧠 [Planner] Planning analysis for: '{state.get('user_query', 'General Analysis')}'")
    
    # Initialize the LLM (Gemini)
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        api_key=settings.GOOGLE_API_KEY,
        temperature=0.2
    )
    
    # Enforce structured output via function calling
    structured_llm = llm.with_structured_output(AnalysisPlan)
    
    # Prepare the prompt
    sys_prompt = PLANNER_PROMPT.format(
        schema_summary=state.get("schema_summary", ""),
        user_query=state.get("user_query", "Provide a general summary and basic visualizations for this data.")
    )
    
    # Execute
    try:
        result: AnalysisPlan = await structured_llm.ainvoke([
            SystemMessage(content=sys_prompt),
            HumanMessage(content=f"Create an analysis plan for: {state.get('user_query', 'Provide a general summary and basic visualizations for this data.')}"),
        ])
        plan_steps = result.steps
        print(f"🧠 [Planner] Plan generated with {len(plan_steps)} steps.")
    except Exception as e:
        print(f"🚨 [Planner] Error: {str(e)}")
        # Fallback to a basic plan if structured output fails
        plan_steps = [
            "Load the dataset and provide a high-level statistical summary.",
            "Identify the top categories or distributions and create a bar chart.",
            "Check for any obvious correlations or trends and plot them."
        ]
    
    # Return updates to the state
    return {
        "analysis_plan": plan_steps,
        "current_step_index": 0,
        "iteration_count": 0,
        "error": None
    }

"""
Analyst node logic: Generates Python code for the current step in the plan.
"""

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.config import settings
from app.agent.state import AgentState
from app.agent.prompts import ANALYST_PROMPT


class GeneratedCode(BaseModel):
    """Pydantic model to enforce code generation structure."""
    title: str = Field(description="A short title for this code snippet")
    code: str = Field(description="The executable Python code using pandas and plotly")


async def analyst_node(state: AgentState) -> dict:
    """
    Generate Python code for the current analysis step.
    """
    plan = state.get("analysis_plan", [])
    step_idx = state.get("current_step_index", 0)
    
    # Guard check — all steps done
    if step_idx >= len(plan):
        print(f"✅ [Analyst] All {len(plan)} steps completed.")
        return {}

    # Prevent infinite retry loops
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3)
    if iteration_count >= max_iterations:
        print(f"🚨 [Analyst] Max iterations ({max_iterations}) reached for step {step_idx + 1}. Skipping.")
        return {
            "current_step_index": step_idx + 1,
            "iteration_count": 0,
            "error": None,
        }

    current_step = plan[step_idx]
    print(f"📊 [Analyst] Generating code for step {step_idx + 1}/{len(plan)}: '{current_step}'")
    
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        api_key=settings.GOOGLE_API_KEY,
        temperature=0.0
    )
    
    structured_llm = llm.with_structured_output(GeneratedCode)
    
    sys_prompt = ANALYST_PROMPT.format(
        step_index=step_idx + 1,
        total_steps=len(plan),
        current_step=current_step,
        schema_summary=state.get("schema_summary", "")
    )
    
    # Build the human message content for the current step
    human_content = f"Please generate the Python code for this step: \"{current_step}\""

    # Optional context from previous errors if we are retrying
    if state.get("error") and iteration_count > 0:
        human_content += f"\n\nPREVIOUS ERROR THAT YOU MUST FIX:\n{state['error']}"

    try:
        result: GeneratedCode = await structured_llm.ainvoke([
            SystemMessage(content=sys_prompt),
            HumanMessage(content=human_content),
        ])
        
        # We append the new code snippet to our state. We don't execute it yet.
        new_snippet = {
            "title": result.title,
            "code": result.code,
            "step_index": step_idx,
            "status": "pending_execution"
        }
        
        return {
            "code_snippets": [new_snippet], # State reducer will append this
            "error": None
        }
    except Exception as e:
        print(f"🚨 [Analyst] Error generating code: {str(e)}")
        # Increment iteration_count so we eventually hit max_iterations and skip this step
        return {
            "error": f"Failed to generate code for step {step_idx + 1}: {str(e)}",
            "iteration_count": iteration_count + 1,
        }

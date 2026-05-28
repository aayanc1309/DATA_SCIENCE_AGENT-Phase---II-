"""
Evaluator node logic: Evaluates code execution results.
"""

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.config import settings
from app.agent.state import AgentState
from app.agent.prompts import EVALUATOR_PROMPT


class EvaluationResult(BaseModel):
    """Pydantic model to enforce evaluation structure."""
    is_successful: bool = Field(description="True if the code ran correctly and produced meaningful output.")
    retry_needed: bool = Field(description="True if the code failed but can be fixed by the Analyst.")
    error_feedback: str = Field(description="Feedback to the Analyst on how to fix the error, if retry_needed is True.")
    key_insights: list[str] = Field(description="List of interesting insights if the code was successful. Empty array otherwise.")


async def evaluator_node(state: AgentState) -> dict:
    """
    Evaluates the execution result. Determines if we loop back to Analyst or move to next step.
    """
    plan = state.get("analysis_plan", [])
    step_idx = state.get("current_step_index", 0)
    current_step = plan[step_idx] if step_idx < len(plan) else ""
    
    snippets = state.get("code_snippets", [])
    if not snippets:
        return {"error": "No snippet to evaluate"}
        
    latest_code = snippets[-1].get("code", "")
    
    # We retrieve the transient execution result passed from Executor
    exec_res = state.get("last_execution_result", {})
    
    print(f"✅ [Evaluator] Checking results for step {step_idx + 1}")
    
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        api_key=settings.GOOGLE_API_KEY,
        temperature=0.0
    )
    
    structured_llm = llm.with_structured_output(EvaluationResult)
    
    sys_prompt = EVALUATOR_PROMPT.format(
        current_step=current_step,
        code=latest_code,
        status="Success" if exec_res.get("success") else "Failed",
        stdout=exec_res.get("stdout", ""),
        stderr=exec_res.get("stderr", ""),
        error=exec_res.get("error", ""),
        visualizations_captured=bool(exec_res.get("visualizations"))
    )
    
    try:
        eval_res: EvaluationResult = await structured_llm.ainvoke([
            SystemMessage(content=sys_prompt),
            HumanMessage(content=f"Evaluate the execution results for step: '{current_step}'"),
        ])
    except Exception as e:
        print(f"🚨 [Evaluator] Error parsing evaluation: {e}")
        # Default fallback
        eval_res = EvaluationResult(
            is_successful=exec_res.get("success", False),
            retry_needed=False,
            error_feedback="",
            key_insights=["Execution completed but evaluation failed to parse."] if exec_res.get("success") else []
        )
    
    updates = {}
    
    # Logic for routing
    max_iters = state.get("max_iterations", 5)
    current_iter = state.get("iteration_count", 0)
    
    if not eval_res.is_successful and eval_res.retry_needed and current_iter < max_iters:
        print(f"🔁 [Evaluator] Code failed. Requesting retry. Feedback: {eval_res.error_feedback}")
        updates["error"] = eval_res.error_feedback
        updates["iteration_count"] = current_iter + 1
        # We don't increment step_index, so it routes back to Analyst for the SAME step
    else:
        # Success or ran out of retries. Move to next step.
        print(f"➡️ [Evaluator] Proceeding to next step. Insights found: {len(eval_res.key_insights)}")
        updates["current_step_index"] = step_idx + 1
        updates["error"] = None # Clear error
        updates["iteration_count"] = 0 # reset counter for next step
        
        if eval_res.key_insights:
           updates["key_findings"] = eval_res.key_insights # appended by reducer
           
    return updates

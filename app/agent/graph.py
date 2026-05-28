"""
Compiled LangGraph for the AI Agent.
"""

from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes.planner import planner_node
from app.agent.nodes.analyst import analyst_node
from app.agent.nodes.executor import executor_node
from app.agent.nodes.evaluator import evaluator_node
from app.agent.nodes.summarizer import summarizer_node

# ── Routing Logic ────────────────────────────────────────────────────────────

def analyst_router(state: AgentState) -> str:
    """
    Decides the next node after the Analyst.
    If the Analyst produced no code (skipped step or all steps done),
    check whether we should move to Summarizer or try the next step.
    If code was produced, proceed to Executor.
    """
    plan = state.get("analysis_plan", [])
    step_idx = state.get("current_step_index", 0)
    snippets = state.get("code_snippets", [])

    # If step_index is past the end of the plan, we're done → Summarizer
    if step_idx >= len(plan):
        return "Summarizer"

    # If the Analyst just set an error (failed to generate code) but didn't
    # produce a snippet, skip Executor/Evaluator and loop back to Analyst
    # (the iteration_count guard in the Analyst will eventually break the loop)
    if state.get("error") and (not snippets or snippets[-1].get("status") != "pending_execution"):
        return "Analyst"

    # If there are no snippets at all (shouldn't normally happen), go to Summarizer
    if not snippets:
        return "Summarizer"

    # Normal case: code was generated, send it to the Executor
    return "Executor"


def evaluator_router(state: AgentState) -> str:
    """
    Decides the next node after evaluation.
    If error is set (meaning retry requested), go back to Analyst.
    If current_step_index < len(plan), go to next Analyst step.
    Otherwise, go to Summarizer.
    """
    # If the evaluator set an error, it means we need to retry the current step
    if state.get("error"):
        return "Analyst"
        
    plan = state.get("analysis_plan", [])
    step_idx = state.get("current_step_index", 0)
    
    if step_idx < len(plan):
        return "Analyst"
    
    return "Summarizer"

# ── Graph Construction ───────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Build and compile the LangGraph workflow."""
    
    workflow = StateGraph(AgentState)
    
    # 1. Add Nodes
    workflow.add_node("Planner", planner_node)
    workflow.add_node("Analyst", analyst_node)
    workflow.add_node("Executor", executor_node)
    workflow.add_node("Evaluator", evaluator_node)
    workflow.add_node("Summarizer", summarizer_node)
    
    # 2. Add Edges
    workflow.set_entry_point("Planner")
    
    # Planner -> Analyst
    workflow.add_edge("Planner", "Analyst")
    
    # Analyst -> [Conditional: Executor if code produced, Summarizer if done, self-loop if error]
    workflow.add_conditional_edges(
        "Analyst",
        analyst_router,
        {
            "Executor": "Executor",
            "Summarizer": "Summarizer",
            "Analyst": "Analyst",
        }
    )
    
    # Executor -> Evaluator
    workflow.add_edge("Executor", "Evaluator")
    
    # Evaluator -> [Conditional]
    workflow.add_conditional_edges(
        "Evaluator",
        evaluator_router,
        {
            "Analyst": "Analyst",
            "Summarizer": "Summarizer"
        }
    )
    
    # Summarizer -> End
    workflow.add_edge("Summarizer", END)
    
    # 3. Compile
    return workflow.compile()

# Provide a pre-compiled graph for the service to use
agent_graph = build_graph()

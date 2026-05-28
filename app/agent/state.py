"""
LangGraph State definitions for the AI Agent.
"""

import operator
from typing import Annotated, Any, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

# Using LangGraph's add_messages to append to the message list properly
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    The shared state dictionary for the LangGraph agent across all nodes.
    """
    # System and user conversation messages
    messages: Annotated[list, add_messages]
    
    # Metadata and summary of the uploaded dataset
    file_id: str
    file_metadata: dict[str, Any]
    schema_summary: str
    user_query: Optional[str]
    
    # Track the steps the Agent plans to execute
    analysis_plan: list[str]
    current_step_index: int
    
    # Aggregated outputs as the agent runs code
    code_snippets: Annotated[list[dict], operator.add]
    visualizations: Annotated[list[dict], operator.add]
    key_findings: Annotated[list[str], operator.add]
    
    # Loop counters to prevent infinite loops (Agent retrying bad code)
    iteration_count: int
    max_iterations: int
    
    # The final plain-language response provided by the Summarizer
    final_summary: str
    
    # Transient: execution result from the Executor for the Evaluator to inspect
    last_execution_result: dict[str, Any]

    # Global flag to track failures
    error: Optional[str]


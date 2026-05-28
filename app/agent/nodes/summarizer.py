"""
Summarizer node logic: Compiles all findings into a final plain-language response.
"""

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.config import settings
from app.agent.state import AgentState
from app.agent.prompts import SUMMARIZER_PROMPT


class SummaryOutput(BaseModel):
    """Pydantic model for final summary."""
    plain_language_summary: str = Field(description="A highly readable, non-technical summary of the analysis.")


async def summarizer_node(state: AgentState) -> dict:
    """
    Creates the final summary using the collected key findings.
    """
    print("📝 [Summarizer] Compiling final report...")
    
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        api_key=settings.GOOGLE_API_KEY,
        temperature=0.3
    )
    
    structured_llm = llm.with_structured_output(SummaryOutput)
    
    findings_list = "\n".join([f"- {f}" for f in state.get("key_findings", [])])
    if not findings_list:
        findings_list = "No significant insights were successfully extracted."
        
    sys_prompt = SUMMARIZER_PROMPT.format(
        user_query=state.get("user_query", "General data overview"),
        key_findings=findings_list
    )
    
    try:
        final_summary: SummaryOutput = await structured_llm.ainvoke([
            SystemMessage(content=sys_prompt),
            HumanMessage(content=f"Summarize the analysis findings for: {state.get('user_query', 'General data overview')}"),
        ])
        
        return {
            "final_summary": final_summary.plain_language_summary,
            "error": None
        }
    except Exception as e:
        print(f"🚨 [Summarizer] Error generating summary: {str(e)}")
        return {
            "final_summary": f"Analysis complete. Raw findings:\n{findings_list}",
        }

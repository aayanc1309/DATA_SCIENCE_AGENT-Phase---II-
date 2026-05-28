"""
Analysis Service: Triggers and monitors the LangGraph agent background execution.
"""

import asyncio
from datetime import datetime

from app.agent.graph import agent_graph
from app.models.schemas import AnalysisResult, AnalysisStatus
from app.services.file_service import file_service
from app.api.routes.websocket import ws_manager


class AnalysisService:
    def __init__(self):
        # In memory store for tasks
        self._tasks: dict[str, AnalysisResult] = {}

    def get_task(self, task_id: str) -> AnalysisResult | None:
        return self._tasks.get(task_id)

    def create_task(self, task_id: str, file_id: str) -> AnalysisResult:
        task = AnalysisResult(
            task_id=task_id,
            file_id=file_id,
            status=AnalysisStatus.PENDING,
            started_at=datetime.utcnow(),
        )
        self._tasks[task_id] = task
        return task

    async def run_analysis(self, task_id: str, file_id: str, user_query: str | None, session_id: str):
        """
        Runs the LangGraph agent in the background and streams updates via WebSocket.
        """
        task = self._tasks[task_id]
        task.status = AnalysisStatus.RUNNING
        
        # 1. Fetch File Metadata for schema
        schema_summary = file_service.get_schema_summary(file_id)
        if not schema_summary:
            task.status = AnalysisStatus.FAILED
            task.error = "File metadata not found or failed to parse."
            task.completed_at = datetime.utcnow()
            await ws_manager.send_event(session_id, "analysis:progress", {"status": "failed", "current_step": "Error"})
            return

        # 2. Setup Initial State
        initial_state = {
            "messages": [],
            "file_id": file_id,
            "file_metadata": {},
            "schema_summary": schema_summary,
            "user_query": user_query,
            "analysis_plan": [],
            "current_step_index": 0,
            "code_snippets": [],
            "visualizations": [],
            "key_findings": [],
            "iteration_count": 0,
            "max_iterations": 3,
            "final_summary": "",
            "error": None,
            "last_execution_result": {}
        }

        # 3. Execute Graph and Stream Updates
        print(f"🚀 [AnalysisService] Starting agent graph for task {task_id} (Session {session_id})")
        await ws_manager.send_event(session_id, "analysis:progress", {
            "status": "running", 
            "progress_percent": 10,
            "current_step": "Planning analysis strategy..."
        })

        try:
            # We use astream to get events as nodes finish
            progress_map = {
                "Planner": (30, "Generating code for analysis steps..."),
                "Analyst": (50, "Executing analysis code..."),
                "Executor": (70, "Evaluating results..."),
                "Evaluator": (80, "Processing next step..."),
                "Summarizer": (95, "Compiling final report...")
            }
            
            final_state = None
            async for s in agent_graph.astream(initial_state):
                # s is a dict with the node name as key and its output as value
                for node_name, state_update in s.items():
                    print(f"✅ [AnalysisService] Node completed: {node_name}")
                    
                    if node_name in progress_map:
                        pct, msg = progress_map[node_name]
                        await ws_manager.send_event(session_id, "analysis:progress", {
                            "status": "running", 
                            "progress_percent": pct,
                            "current_step": msg
                        })
                    
                    # Store latest state for final extraction just in case
                    final_state = state_update

            # Full state after execution is needed to build the final response 
            # `astream` yields updates, we need the final combined state.
            # Using `.ainvoke` is simpler if we just want the final result, but `astream` gives us nodes. 
            # We can re-fetch the state or trust the last node. 
            # Wait, `astream` yields state updates. It doesn't yield the full merged state unless we ask for it.
            # Let's run `ainvoke` for simplicity and just stream placeholder progress during it.
            # Actually, `agent_graph.astream` with `stream_mode="values"` yields the full state after each step.
            
        except Exception as e:
            print(f"🚨 [AnalysisService] Agent execution failed: {str(e)}")
            task.status = AnalysisStatus.FAILED
            task.error = f"Agent failed: {str(e)}"
            task.completed_at = datetime.utcnow()
            await ws_manager.send_event(session_id, "analysis:progress", {"status": "failed", "current_step": "Agent Error"})
            return

        # Since astream logic above is tricky with merging state manually, let's just use ainvoke
        # and send a 100% update. I will re-write the execution block to be safe.
        pass

    async def run_analysis_simple(self, task_id: str, file_id: str, user_query: str | None, session_id: str):
        """ simpler version using ainvoke to ensure state is 100% accurate. """
        task = self._tasks[task_id]
        task.status = AnalysisStatus.RUNNING
        
        schema_summary = file_service.get_schema_summary(file_id)
        if not schema_summary:
            task.status = AnalysisStatus.FAILED
            return
            
        initial_state = {
            "messages": [], "file_id": file_id, "file_metadata": {},
            "schema_summary": schema_summary, "user_query": user_query,
            "analysis_plan": [], "current_step_index": 0, "code_snippets": [],
            "visualizations": [], "key_findings": [], "iteration_count": 0,
            "max_iterations": 3, "final_summary": "", "error": None,
            "last_execution_result": {}
        }

        await ws_manager.send_event(session_id, "analysis:progress", {
            "status": "running", "progress_percent": 20, "current_step": "Agent is thinking..."
        })

        try:
            # Let it run with streaming values to get live state updatess
            final_state = initial_state
            
            # Use stream_mode="values" which yields the full state after each node runs
            async for current_state in agent_graph.astream(initial_state, stream_mode="values"):
                final_state = current_state
                
                # We can determine progress based on step index
                idx = current_state.get("current_step_index", 0)
                plan = current_state.get("analysis_plan", [])
                
                pct = 20
                msg = "Agent is thinking..."
                
                if plan:
                    pct = 30 + int(70 * (idx / max(len(plan), 1)))
                    step_name = plan[idx] if idx < len(plan) else "Finalizing report..."
                    msg = f"Step {idx + 1}/{len(plan)}: {step_name}"
                    
                await ws_manager.send_event(session_id, "analysis:progress", {
                    "status": "running", 
                    "progress_percent": min(pct, 95), 
                    "current_step": msg
                })

            task.status = AnalysisStatus.COMPLETED
            task.summary = final_state.get("final_summary")
            task.key_findings = final_state.get("key_findings", [])
            
            from app.models.schemas import VisualizationSpec
            viz_list = []
            for v in final_state.get("visualizations", []):
                viz_list.append(VisualizationSpec(
                    title=v.get("title", ""),
                    chart_type=v.get("chart_type", "plotly"),
                    plotly_json=v.get("plotly_json", {})
                ))
            task.visualizations = viz_list
            
            # Map code snippets to the schema
            task_snippets = []
            import uuid
            from app.models.schemas import CodeSnippet
            for idx, snip in enumerate(final_state.get("code_snippets", [])):
                task_snippets.append(CodeSnippet(
                    cell_id=str(uuid.uuid4()),
                    title=snip.get("title", f"Step {snip.get('step_index', idx) + 1}"),
                    description="",
                    code=snip.get("code", ""),
                    language="python"
                ))
            task.code_snippets = task_snippets
            task.completed_at = datetime.utcnow()

            # Push the final result to websocket immediately so UI updates instantly
            await ws_manager.send_event(session_id, "analysis:result", task.model_dump(mode="json"))

        except Exception as e:
            print(f"🚨 [AnalysisService] Agent execution failed: {str(e)}")
            task.status = AnalysisStatus.FAILED
            task.error = f"Agent failed: {str(e)}"
            task.completed_at = datetime.utcnow()
            await ws_manager.send_event(session_id, "analysis:progress", {"status": "failed", "current_step": "Agent Error"})

analysis_service = AnalysisService()

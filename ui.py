"""
DataLens AI — Streamlit Frontend
Showcases: file upload, data profiling, LangGraph agent analysis,
interactive code execution, Plotly visualizations, and agent internals.
Run: streamlit run ui.py
"""

import sys, os, asyncio, uuid, time, io

# ── Fix Windows cp1252 emoji crash ───────────────────────
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import streamlit as st
import pandas as pd

# ── Ensure backend is importable ─────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from app.services.file_service import file_service
from app.agent.graph import agent_graph
from app.agent.tools.code_runner import run_python_code

# ── Page config ──────────────────────────────────────────
st.set_page_config(page_title="DataLens AI Agent", page_icon="🔬", layout="wide")

# ── Custom CSS ───────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }
    .stApp { background: linear-gradient(135deg, #0f0c29 0%, #1a1a2e 50%, #16213e 100%); }
    h1, h2, h3 { color: #e0e0ff !important; }
    .node-badge {
        display: inline-block; padding: 4px 14px; border-radius: 20px;
        font-size: 13px; font-weight: 600; margin: 2px 4px;
    }
    .node-planner  { background: #6c5ce7; color: white; }
    .node-analyst  { background: #00b894; color: white; }
    .node-executor { background: #fdcb6e; color: #2d3436; }
    .node-evaluator{ background: #e17055; color: white; }
    .node-summarizer{ background: #0984e3; color: white; }
    .metric-card {
        background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px; padding: 20px; text-align: center;
    }
    .metric-card h2 { margin: 0; font-size: 28px; color: #a29bfe !important; }
    .metric-card p { margin: 4px 0 0 0; color: #b2bec3; font-size: 13px; }
    .pipeline-flow {
        background: rgba(255,255,255,0.04); border-radius: 12px;
        padding: 16px; text-align: center; margin: 12px 0;
    }
    .finding-card {
        background: rgba(108,92,231,0.1); border-left: 3px solid #6c5ce7;
        padding: 10px 16px; border-radius: 0 8px 8px 0; margin: 6px 0;
    }
    div[data-testid="stExpander"] { background: rgba(255,255,255,0.03); border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 20px 0 10px 0;">
    <h1 style="font-size:42px; margin:0;">🔬 DataLens AI Agent</h1>
    <p style="color:#b2bec3; font-size:16px; margin-top:4px;">
        Autonomous Data Science • Powered by LangGraph + Gemini
    </p>
</div>
""", unsafe_allow_html=True)

# Pipeline diagram
st.markdown("""
<div class="pipeline-flow">
    <span class="node-badge node-planner">🧠 Planner</span> →
    <span class="node-badge node-analyst">📊 Analyst</span> →
    <span class="node-badge node-executor">⚙️ Executor</span> →
    <span class="node-badge node-evaluator">✅ Evaluator</span> →
    <span class="node-badge node-summarizer">📝 Summarizer</span>
</div>
""", unsafe_allow_html=True)

# ── Session state defaults ───────────────────────────────
for k, v in {"file_id": None, "df": None, "metadata": None, "result": None}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════════════════════════
# SECTION 1 — FILE UPLOAD
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("📁 Upload Dataset")
col_up, col_info = st.columns([2, 3])

with col_up:
    uploaded = st.file_uploader(
        "Drop a CSV or Excel file", type=["csv", "xlsx", "xls"],
        help="Max 100 MB • Supported: .csv, .xlsx, .xls"
    )
    if uploaded and (st.session_state.file_id is None or uploaded.name != getattr(st.session_state.metadata, "filename", "")):
        with st.spinner("Parsing file…"):
            content = uploaded.read()
            fid, meta, df = asyncio.run(file_service.process_upload(uploaded.name, content))
            st.session_state.file_id = fid
            st.session_state.metadata = meta
            st.session_state.df = df
            st.session_state.result = None
        st.success(f"✅ **{meta.filename}** loaded — {meta.row_count:,} rows × {meta.column_count} cols")

with col_info:
    if st.session_state.metadata:
        m = st.session_state.metadata
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rows", f"{m.row_count:,}")
        c2.metric("Columns", m.column_count)
        c3.metric("File Type", m.file_type.value.upper())
        c4.metric("Size", f"{m.file_size_bytes / 1024:.1f} KB")

# ══════════════════════════════════════════════════════════
# SECTION 2 — DATA PREVIEW & SCHEMA
# ══════════════════════════════════════════════════════════
if st.session_state.df is not None:
    st.markdown("---")
    tab_preview, tab_schema, tab_stats = st.tabs(["📋 Data Preview", "🧬 Column Schema", "📊 Statistics"])

    with tab_preview:
        page = st.number_input("Page", 1, max(1, len(st.session_state.df) // 50 + 1), 1, key="preview_page")
        s, e = (page - 1) * 50, page * 50
        st.dataframe(st.session_state.df.iloc[s:e], use_container_width=True, height=350)

    with tab_schema:
        schema_rows = [{
            "Column": c.name, "Type": c.dtype,
            "Non-Null": f"{c.non_null_count:,}", "Null": f"{c.null_count:,}",
            "Unique": f"{c.unique_count:,}", "Samples": str(c.sample_values[:3])
        } for c in st.session_state.metadata.columns]
        st.dataframe(pd.DataFrame(schema_rows), use_container_width=True, hide_index=True)

    with tab_stats:
        num_df = st.session_state.df.select_dtypes(include=["number"])
        if num_df.empty:
            st.info("No numeric columns found.")
        else:
            st.dataframe(num_df.describe().T, use_container_width=True)

    # ══════════════════════════════════════════════════════
    # SECTION 3 — AI ANALYSIS
    # ══════════════════════════════════════════════════════
    st.markdown("---")
    st.subheader("🤖 AI Agent Analysis")

    query = st.text_input(
        "Ask a question about your data",
        placeholder="e.g. Show me the distribution of sales by category",
        help="Leave blank for automatic general analysis"
    )

    if st.button("🚀 Run Agent", type="primary", use_container_width=True):
        fid = st.session_state.file_id
        schema_summary = file_service.get_schema_summary(fid)
        user_query = query or "Provide a general summary and basic visualizations for this data."

        initial_state = {
            "messages": [], "file_id": fid, "file_metadata": {},
            "schema_summary": schema_summary, "user_query": user_query,
            "analysis_plan": [], "current_step_index": 0,
            "code_snippets": [], "visualizations": [], "key_findings": [],
            "iteration_count": 0, "max_iterations": 3,
            "final_summary": "", "error": None, "last_execution_result": {}
        }

        status = st.empty()
        progress = st.progress(0)
        holder = [initial_state]  # mutable container for async capture

        async def stream_agent():
            async for state in agent_graph.astream(initial_state, stream_mode="values"):
                holder[0] = state
                plan = state.get("analysis_plan", [])
                idx = state.get("current_step_index", 0)
                if plan:
                    pct = min(int(30 + 65 * idx / max(len(plan), 1)), 95)
                    step = plan[idx] if idx < len(plan) else "Finalizing…"
                    status.info(f"⏳ Step {idx+1}/{len(plan)}: {step}")
                    progress.progress(pct)
                else:
                    status.info("⏳ Planning analysis strategy…")
                    progress.progress(20)

        with st.spinner("Agent is running…"):
            asyncio.run(stream_agent())

        progress.progress(100)
        status.success("✅ Analysis complete!")
        st.session_state.result = holder[0]

    # ══════════════════════════════════════════════════════
    # SECTION 4 — RESULTS DISPLAY
    # ══════════════════════════════════════════════════════
    if st.session_state.result:
        res = st.session_state.result
        st.markdown("---")

        # 4a — Summary
        if res.get("final_summary"):
            st.subheader("AI Summary")
            st.markdown(f"""<div style="background:rgba(9,132,227,0.1); border-left:3px solid #0984e3;
                padding:16px 20px; border-radius:0 10px 10px 0; color:#dfe6e9; line-height:1.7;">
                {res['final_summary']}</div>""", unsafe_allow_html=True)

        # 4b — Key Findings
        findings = res.get("key_findings", [])
        if findings:
            st.subheader("Key Findings")
            for f in findings:
                st.markdown(f'<div class="finding-card">{f}</div>', unsafe_allow_html=True)

        # 4c — Visualizations (Plotly)
        vizs = res.get("visualizations", [])
        if vizs:
            st.subheader("Visualizations")
            import plotly.io as pio
            for v in vizs:
                pj = v.get("plotly_json")
                if pj:
                    import json as _json
                    fig = pio.from_json(_json.dumps(pj))
                    st.plotly_chart(fig, use_container_width=True)

        # 4d — Analysis Plan
        plan = res.get("analysis_plan", [])
        if plan:
            with st.expander("Agent Analysis Plan", expanded=False):
                for i, step in enumerate(plan):
                    done = i < res.get("current_step_index", 0)
                    st.markdown(f"{'[x]' if done else '[ ]'} **Step {i+1}:** {step}")

    # ══════════════════════════════════════════════════════
    # SECTION 5 — NOTEBOOK CELLS (agent-generated + custom)
    # ══════════════════════════════════════════════════════
    st.markdown("---")
    st.subheader("Notebook")
    st.caption("`df` and `px` (plotly.express) are pre-loaded. Edit any cell and hit Run.")

    # Initialize custom cells list
    if "custom_cells" not in st.session_state:
        st.session_state.custom_cells = []

    # Helper to render a runnable cell
    def render_cell(cell_key, title, default_code, readonly=False):
        st.markdown(f"**{title}**")
        code = st.text_area("Code", value=default_code, height=120, key=f"code_{cell_key}", label_visibility="collapsed")
        if st.button("Run", key=f"run_{cell_key}", type="secondary"):
            with st.spinner("Executing..."):
                t0 = time.time()
                result = run_python_code(st.session_state.file_id, code)
                elapsed = int((time.time() - t0) * 1000)
            st.caption(f"{elapsed}ms | {'Success' if result['success'] else 'Failed'}")
            if result["stdout"]:
                st.code(result["stdout"], language="text")
            if result["stderr"]:
                st.error(result["stderr"])
            if result.get("error"):
                st.error(result["error"][:500])
            for v in result.get("visualizations", []):
                pj = v.get("plotly_json")
                if pj:
                    import json as _json, plotly.io as pio
                    st.plotly_chart(pio.from_json(_json.dumps(pj)), use_container_width=True)
        st.markdown("---")

    # Render agent-generated cells
    if st.session_state.result:
        for i, sn in enumerate(st.session_state.result.get("code_snippets", [])):
            render_cell(f"agent_{i}", f"Cell {i+1} — {sn.get('title', 'Untitled')}", sn.get("code", ""))

    # Render custom user cells
    for i in range(len(st.session_state.custom_cells)):
        render_cell(f"custom_{i}", f"Cell {len(st.session_state.result.get('code_snippets', [])) + i + 1 if st.session_state.result else i + 1} — Custom", st.session_state.custom_cells[i])

    # Add new cell button
    if st.button("+ Add Cell", use_container_width=True):
        st.session_state.custom_cells.append("import pandas as pd\nprint(df.head())")
        st.rerun()

# ── Empty state ──────────────────────────────────────────
else:
    st.markdown("""
    <div style="text-align:center; padding:60px 0; color:#636e72;">
        <p style="font-size:48px; margin:0;">📂</p>
        <p style="font-size:18px;">Upload a CSV or Excel file to get started</p>
        <p style="font-size:13px;">The AI agent will plan, write code, execute it, evaluate results, and summarize findings — all autonomously.</p>
    </div>
    """, unsafe_allow_html=True)

# ── Sidebar — Agent Architecture Info ────────────────────
with st.sidebar:
    st.markdown("### 🏗️ Agent Architecture")
    st.markdown("""
    **5-Node LangGraph Pipeline:**

    1. **🧠 Planner** — Parses user intent, creates 2-4 step analysis plan via structured output
    2. **📊 Analyst** — Generates Python code (pandas + plotly) for each step
    3. **⚙️ Executor** — Runs code in sandboxed env with `df` pre-loaded
    4. **✅ Evaluator** — LLM-judges output quality, triggers retries on failure (max 3)
    5. **📝 Summarizer** — Translates findings into plain-language narrative
    """)
    st.markdown("---")
    st.markdown("### ⚡ Key Features")
    st.markdown("""
    - 🔄 **Self-healing loops** — Evaluator retries failed code up to 3×
    - 📊 **Auto viz extraction** — Plotly figures captured from exec locals
    - 🧬 **Schema-aware prompts** — Column types, stats, samples sent to LLM
    - 🎯 **Structured outputs** — Pydantic models enforce valid LLM responses
    - 🔒 **Sandboxed execution** — `df.copy()` prevents data mutation
    - 📡 **WebSocket streaming** — Real-time progress updates to frontend
    """)
    st.markdown("---")
    st.markdown("### 🛠️ Stack")
    st.markdown("Gemini 2.5 Flash Lite • LangGraph • FastAPI • Pandas • Plotly")
    st.markdown("---")
    from app.config import settings
    st.caption(f"v{settings.APP_VERSION} • Model: `{settings.GEMINI_MODEL}`")
    st.caption(f"Max file: {settings.MAX_FILE_SIZE_MB} MB • Extensions: {', '.join(settings.ALLOWED_EXTENSIONS)}")

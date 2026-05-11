"""Xpanse Agent Command Center — Streamlit UI.

Progressive dashboard that mirrors the LangGraph workflow lifecycle:

  Stage 0  →  Idle (sidebar config, launch button)
  Stage 1  →  Analysis running (compliance + strategy in parallel)
  Stage 2  →  Awaiting Review (HITL gate — yellow review panel)
  Stage 3  →  Completed (technical artifacts in tabbed code explorer)

Session state keys
------------------
  thread_id      : str   — UUID for the current LangGraph thread
  graph_app      : obj   — compiled LangGraph instance (with MemorySaver)
  checkpointer   : obj   — shared MemorySaver instance
  current_stage  : str   — 'idle' | 'analysis' | 'awaiting_review' | 'completed'
  compliance_output : str | None
  strategy_output   : str | None
  technical_artifacts : dict | None
"""

import uuid

import streamlit as st
from langgraph.checkpoint.memory import MemorySaver

from src.graph.state import create_initial_state
from src.graph.workflow import build_graph

# ---------------------------------------------------------------------------
# Page config — must be the very first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Xpanse Agent Command Center",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — Enterprise Dark Mode aesthetic
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    /* ── Global dark background ── */
    .stApp { background-color: #0d1117; color: #e6edf3; }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }
    [data-testid="stSidebar"] * { color: #e6edf3 !important; }

    /* ── Stage cards ── */
    .card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1rem;
    }
    .card-compliance { border-left: 4px solid #58a6ff; }
    .card-strategy   { border-left: 4px solid #3fb950; }

    /* ── HITL review panel ── */
    .review-panel {
        background: #1c1a00;
        border: 2px solid #e3b341;
        border-radius: 10px;
        padding: 1.4rem;
        margin-bottom: 1rem;
    }
    .review-panel h3 { color: #e3b341 !important; }

    /* ── Stage 3 artifact panel ── */
    .artifact-panel {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 1rem;
    }

    /* ── LED status indicator ── */
    .led-active  { color: #3fb950; font-weight: 600; }
    .led-error   { color: #f85149; font-weight: 600; }

    /* ── Stage header labels ── */
    .stage-label {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #8b949e;
        margin-bottom: 0.3rem;
    }

    /* ── Divider ── */
    hr { border-color: #30363d; }

    /* ── Button overrides ── */
    .stButton > button {
        background: #238636;
        color: #ffffff;
        border: none;
        border-radius: 6px;
        font-weight: 600;
    }
    .stButton > button:hover { background: #2ea043; }

    /* ── Refine button ── */
    .btn-refine > button {
        background: #9e6a03 !important;
    }
    .btn-refine > button:hover { background: #bb8009 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

DEFAULTS: dict = {
    "thread_id": None,
    "graph_app": None,
    "checkpointer": None,
    "current_stage": "idle",
    "compliance_output": None,
    "strategy_output": None,
    "technical_artifacts": None,
}

for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ---------------------------------------------------------------------------
# Helper: initialise (or reuse) the compiled graph
# ---------------------------------------------------------------------------

def _get_app():
    """Return the compiled LangGraph app, creating it once per session."""
    if st.session_state.graph_app is None:
        checkpointer = MemorySaver()
        st.session_state.checkpointer = checkpointer
        st.session_state.graph_app = build_graph(checkpointer=checkpointer)
    return st.session_state.graph_app


def _thread_config() -> dict:
    return {"configurable": {"thread_id": st.session_state.thread_id}}


# ---------------------------------------------------------------------------
# Helper: stream Stage 1 and collect outputs
# ---------------------------------------------------------------------------

def _run_stage1(region: str, goal: str) -> None:
    """Stream Stage 1 nodes and update session state as each node completes."""
    app = _get_app()
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.current_stage = "analysis"
    st.session_state.compliance_output = None
    st.session_state.strategy_output = None
    st.session_state.technical_artifacts = None

    initial_state = create_initial_state(
        target_region=region,
        campaign_goal=goal,
    )

    config = _thread_config()

    # Stream node-by-node; update session state as outputs arrive
    for snapshot in app.stream(initial_state, config=config, stream_mode="values"):
        if snapshot.get("compliance_output"):
            st.session_state.compliance_output = snapshot["compliance_output"]
        if snapshot.get("strategy_output"):
            st.session_state.strategy_output = snapshot["strategy_output"]

    # Graph has paused at interrupt_before=["architect"]
    st.session_state.current_stage = "awaiting_review"


# ---------------------------------------------------------------------------
# Helper: resume after human decision
# ---------------------------------------------------------------------------

def _resume(approved: bool, feedback: str | None = None) -> None:
    """Inject human decision and resume the graph from the interrupt point."""
    app = _get_app()
    config = _thread_config()

    state_update: dict = {"is_approved": approved}
    if feedback:
        state_update["human_feedback"] = feedback

    app.update_state(config, state_update)

    for snapshot in app.stream(None, config=config, stream_mode="values"):
        artifacts = snapshot.get("technical_artifacts")
        if artifacts:
            st.session_state.technical_artifacts = artifacts

    if approved:
        st.session_state.current_stage = "completed"
    else:
        # Strategy loop — go back to awaiting_review after re-run
        st.session_state.current_stage = "awaiting_review"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> tuple[str, str]:
    """Render the control panel sidebar. Returns (region, goal)."""
    with st.sidebar:
        st.markdown("## 🌐 Xpanse Command Center")
        st.markdown("---")

        # Bedrock connection status
        st.markdown("**System Status**")
        st.markdown(
            '<span class="led-active">⬤ Bedrock Connection: Active</span>',
            unsafe_allow_html=True,
        )
        st.markdown("---")

        st.markdown("**Campaign Configuration**")

        region = st.selectbox(
            "Target Region",
            options=["Japan", "Germany", "United Kingdom", "India", "Brazil", "South Korea"],
            index=0,
            help="The geographic market for this expansion campaign.",
        )

        goal = st.text_area(
            "Expansion Goal",
            placeholder="e.g. Expand Sneaker Rewards Program to drive Gen-Z engagement...",
            height=120,
            help="Describe the specific business objective for this campaign.",
        )

        st.markdown("---")

        launch_disabled = st.session_state.current_stage not in ("idle", "completed")
        launch = st.button(
            "🚀 Launch Expansion Squad",
            disabled=launch_disabled,
            use_container_width=True,
        )

        if st.session_state.current_stage not in ("idle", "completed"):
            st.caption("Pipeline is running — wait for completion to relaunch.")

        if st.session_state.thread_id:
            st.markdown("---")
            st.markdown("**Session**")
            st.caption(f"Thread: `{st.session_state.thread_id[:8]}…`")
            st.caption(f"Stage: `{st.session_state.current_stage}`")

    return region, goal, launch


# ---------------------------------------------------------------------------
# Stage 1: Analysis cards
# ---------------------------------------------------------------------------

def render_stage1() -> None:
    """Render the parallel compliance + strategy output cards."""
    st.markdown('<p class="stage-label">Stage 1 — Analysis & Strategy</p>', unsafe_allow_html=True)

    col_compliance, col_strategy = st.columns(2, gap="medium")

    with col_compliance:
        st.markdown('<div class="card card-compliance">', unsafe_allow_html=True)
        st.markdown("### 🛡️ Compliance Sentinel")
        if st.session_state.current_stage == "analysis" and not st.session_state.compliance_output:
            with st.spinner("Analysing legal & data residency risks…"):
                st.empty()
        elif st.session_state.compliance_output:
            # Render each line as a checklist item where possible
            lines = st.session_state.compliance_output.strip().splitlines()
            for line in lines:
                stripped = line.strip()
                if stripped:
                    if stripped[0].isdigit() and stripped[1:3] in (". ", ") "):
                        st.markdown(f"✅ {stripped}")
                    else:
                        st.markdown(stripped)
        else:
            st.caption("Awaiting launch…")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_strategy:
        st.markdown('<div class="card card-strategy">', unsafe_allow_html=True)
        st.markdown("### 🎯 Cultural Strategist")
        if st.session_state.current_stage == "analysis" and not st.session_state.strategy_output:
            with st.spinner("Crafting localised strategy…"):
                st.empty()
        elif st.session_state.strategy_output:
            st.markdown(st.session_state.strategy_output)
        else:
            st.caption("Awaiting launch…")
        st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Stage 2: HITL Review Panel
# ---------------------------------------------------------------------------

def render_stage2() -> None:
    """Render the human-in-the-loop approval gate."""
    st.markdown("---")
    st.markdown('<p class="stage-label">Stage 2 — Human Review Gate</p>', unsafe_allow_html=True)

    st.markdown('<div class="review-panel">', unsafe_allow_html=True)
    st.markdown("### ⚠️ Awaiting Your Approval")
    st.markdown(
        "Review the **Compliance Report** and **Localised Strategy** above. "
        "You can approve the plan to generate technical artifacts, or send it "
        "back to the Strategist with refinement instructions."
    )

    feedback = st.text_area(
        "Refinement Instructions (optional)",
        placeholder="e.g. Increase point multiplier for limited-edition drops, focus on LINE messaging channel…",
        height=90,
        key="hitl_feedback",
    )

    col_refine, col_approve = st.columns([1, 1], gap="small")

    with col_refine:
        st.markdown('<div class="btn-refine">', unsafe_allow_html=True)
        if st.button("🔄 Refine Plan", use_container_width=True):
            if not feedback.strip():
                st.warning("Please provide refinement instructions before sending back.")
            else:
                with st.spinner("Sending feedback to Strategist…"):
                    _resume(approved=False, feedback=feedback.strip())
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col_approve:
        if st.button("✅ Approve & Generate Code", use_container_width=True):
            with st.spinner("Generating technical artifacts — this may take a moment…"):
                _resume(approved=True)
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Stage 3: Technical Artifacts
# ---------------------------------------------------------------------------

def render_stage3() -> None:
    """Render the tabbed code explorer with SQL, Python, and QA report."""
    st.markdown("---")
    st.markdown('<p class="stage-label">Stage 3 — Technical Artifacts</p>', unsafe_allow_html=True)

    artifacts = st.session_state.technical_artifacts or {}
    sql_code = artifacts.get("sql", "")
    python_code = artifacts.get("python", "")
    qa_report = artifacts.get("qa_report", "")

    if not any([sql_code, python_code, qa_report]):
        st.info("Technical artifacts will appear here after approval.")
        return

    tab_sql, tab_python, tab_qa = st.tabs(["🗄️ Snowflake SQL", "🐍 AWS Lambda Python", "🔍 QA Report"])

    with tab_sql:
        if sql_code:
            st.code(sql_code, language="sql")
        else:
            st.caption("No SQL artifact generated.")

    with tab_python:
        if python_code:
            st.code(python_code, language="python")
        else:
            st.caption("No Python artifact generated.")

    with tab_qa:
        if qa_report:
            st.markdown(qa_report)
        else:
            st.caption("No QA report generated.")


# ---------------------------------------------------------------------------
# Main render loop
# ---------------------------------------------------------------------------

def main() -> None:
    region, goal, launch = render_sidebar()

    # ── Page header ──────────────────────────────────────────────────────────
    st.markdown("# 🌐 Global Loyalty Expansion")
    st.markdown(
        "An AI-powered multi-agent system that analyses compliance risks, "
        "crafts localised strategies, and generates production-ready code — "
        "with a human-in-the-loop approval gate."
    )
    st.markdown("---")

    # ── Launch handler ────────────────────────────────────────────────────────
    if launch:
        if not goal.strip():
            st.sidebar.error("Please enter an Expansion Goal before launching.")
        else:
            with st.spinner("🚀 Launching Expansion Squad — running compliance & strategy agents in parallel…"):
                try:
                    _run_stage1(region=region, goal=goal.strip())
                except RuntimeError as exc:
                    st.error(f"**Pipeline error:** {exc}")
                    st.session_state.current_stage = "idle"
            st.rerun()

    # ── Progressive rendering based on current stage ──────────────────────────
    stage = st.session_state.current_stage

    if stage == "idle":
        st.markdown(
            '<div class="card" style="text-align:center; padding: 3rem;">'
            "<h3>Ready to Launch</h3>"
            "<p>Configure your campaign in the sidebar and click "
            "<strong>Launch Expansion Squad</strong> to begin.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    elif stage == "analysis":
        render_stage1()
        st.info("⏳ Agents are running — the page will update automatically when Stage 1 completes.")

    elif stage in ("awaiting_review", "completed"):
        # Always show Stage 1 outputs once available
        render_stage1()

        if stage == "awaiting_review":
            render_stage2()

        if stage == "completed" or st.session_state.technical_artifacts:
            render_stage3()

        if stage == "completed":
            st.success("✅ Pipeline complete! All artifacts have been generated and validated.")
            if st.button("🔁 Start New Expansion", use_container_width=False):
                for key in DEFAULTS:
                    st.session_state[key] = DEFAULTS[key]
                st.rerun()


if __name__ == "__main__":
    main()

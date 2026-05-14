"""Xpanse.ai — Dual-Mode Agent Command Center.

Modes:
  1. Campaign Strategy — 3-agent pipeline with feedback router
  2. Content Transcreation — Cultural research + draft + critic reflection loop
"""

import difflib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver

from src.graph.state import create_initial_state, create_transcreator_state
from src.graph.workflow import build_graph
from src.graph.transcreator import build_transcreator_graph

load_dotenv()

# ---------------------------------------------------------------------------
# Visitor Tracking
# ---------------------------------------------------------------------------
_VISITORS_FILE = Path(__file__).resolve().parent.parent / "data" / "visitors.json"


def _track_visitor():
    """Track unique visitors by session. Stores visit log in data/visitors.json."""
    if "visitor_tracked" in st.session_state:
        return

    st.session_state.visitor_tracked = True
    _VISITORS_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data
    if _VISITORS_FILE.exists():
        data = json.loads(_VISITORS_FILE.read_text())
    else:
        data = {"total_visits": 0, "visits": []}

    # Record visit
    data["total_visits"] += 1
    data["visits"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": str(uuid.uuid4())[:8],
    })

    # Keep only last 500 entries to avoid file bloat
    data["visits"] = data["visits"][-500:]
    _VISITORS_FILE.write_text(json.dumps(data, indent=2))


_track_visitor()

st.set_page_config(page_title="Xpanse.ai Command Center", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
.stApp { background-color: #0f1419; color: #c9d1d9; font-size: 13px; }
[data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #21262d; min-width: 340px !important; width: 340px !important; }
[data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span:not(.led-on):not(.led-off) { color: #c9d1d9; font-size: 12px; }
section[data-testid="stSidebar"] > div { width: 340px; }
h1 { font-size: 1.15rem !important; font-weight: 600 !important; color: #f0f6fc !important; }
h2 { font-size: 0.95rem !important; font-weight: 600 !important; color: #e6edf3 !important; }
h3 { font-size: 0.82rem !important; font-weight: 600 !important; }
p, li, span { font-size: 12px; }
.led { display: inline-flex; align-items: center; gap: 4px; font-size: 0.7rem !important; margin-bottom: 2px; }
.led-on, .led-on * { color: #3fb950 !important; }
.led-off, .led-off * { color: #f85149 !important; }
.flow-graph { display:flex; align-items:center; justify-content:center; gap:0; padding:14px 10px; background:#161b22; border:1px solid #21262d; border-radius:8px; margin-bottom:1rem; }
.flow-node { width:42px; height:42px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:15px; border:2px solid #30363d; background:#0f1419; }
.flow-node-done { border-color:#3fb950; background:#0d3320; }
.flow-node-active { border-color:#58a6ff; background:#0c2d6b; animation:pulse 1.5s infinite; }
.flow-node-pending { border-color:#30363d; opacity:0.4; }
.flow-node-loopback { border-color:#d29922; background:#1c1a00; }
.flow-edge { width:28px; height:2px; background:#30363d; }
.flow-edge-done { background:#3fb950; }
.flow-label { font-size:0.58rem; color:#8b949e; text-align:center; margin-top:3px; font-weight:500; }
.flow-label-done { color:#3fb950; }
@keyframes pulse { 0%,100%{box-shadow:0 0 0 0 rgba(88,166,255,0.4)} 50%{box-shadow:0 0 0 7px rgba(88,166,255,0)} }
.agent-card { background:#161b22; border:1px solid #21262d; border-radius:6px; padding:0.7rem 0.9rem; margin-bottom:0.5rem; font-size:12px; }
.card-done { border-left:3px solid #3fb950; }
.card-pending { border-left:3px solid #30363d; opacity:0.5; }
.impact-card { background:#1a1814; border:1px solid #d29922; border-radius:6px; padding:0.6rem 0.8rem; margin:0.4rem 0; font-size:12px; }
.diff-add { background:#0d3320; color:#7ee787; padding:1px 4px; font-family:monospace; font-size:11px; }
.diff-del { background:#3d1117; color:#ffa198; padding:1px 4px; font-family:monospace; font-size:11px; text-decoration:line-through; }
.score-bar { height:6px; border-radius:3px; background:#21262d; overflow:hidden; margin:4px 0; }
.score-fill { height:100%; border-radius:3px; transition:width 0.3s; }
.stButton > button { font-size:0.75rem !important; font-weight:500; border-radius:5px; padding:0.4rem 0.8rem; background:#1f6feb !important; color:#fff !important; border:none !important; }
.stButton > button:hover { background:#388bfd !important; }
[data-testid="stSidebar"] .stButton > button { background:#238636 !important; }
[data-testid="stSidebar"] .stButton > button:hover { background:#2ea043 !important; }
.tl-entry { display:flex; align-items:flex-start; gap:6px; margin-bottom:3px; font-size:0.65rem; font-family:monospace; }
.tl-dot { width:7px; height:7px; border-radius:50%; margin-top:3px; flex-shrink:0; }
.tl-green { background:#3fb950; } .tl-blue { background:#58a6ff; } .tl-amber { background:#d29922; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
DEFAULTS = {"thread_id": None, "campaign_app": None, "transcreator_app": None, "checkpointer": None, "stage": "idle", "pipeline_state": None, "app_mode": "Campaign Strategy"}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------
def _get_campaign_app():
    if st.session_state.campaign_app is None:
        cp = MemorySaver()
        st.session_state.checkpointer = cp
        st.session_state.campaign_app = build_graph(checkpointer=cp)
    return st.session_state.campaign_app

def _get_transcreator_app():
    if st.session_state.transcreator_app is None:
        cp = MemorySaver()
        st.session_state.transcreator_app = build_transcreator_graph(checkpointer=cp)
    return st.session_state.transcreator_app

def _cfg():
    return {"configurable": {"thread_id": st.session_state.thread_id}}

# Campaign mode helpers
def _run_campaign(brief):
    app = _get_campaign_app()
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.stage = "running"
    st.session_state.pipeline_state = None
    config = _cfg()
    for _ in app.stream(create_initial_state(**brief), config=config, stream_mode="values"):
        pass
    snap = app.get_state(config)
    if snap and snap.values:
        st.session_state.pipeline_state = snap.values
    st.session_state.stage = "review"

def _resume_campaign_feedback(feedback):
    app = _get_campaign_app()
    config = _cfg()
    app.update_state(config, {"human_feedback": feedback, "is_approved": False}, as_node="campaign_architect")
    for _ in app.stream(None, config=config, stream_mode="values"):
        pass
    snap = app.get_state(config)
    if snap and snap.values:
        st.session_state.pipeline_state = snap.values
    st.session_state.stage = "review"

def _approve_campaign():
    app = _get_campaign_app()
    config = _cfg()
    app.update_state(config, {"human_feedback": "approve", "is_approved": True, "target_node": "end"}, as_node="campaign_architect")
    for _ in app.stream(None, config=config, stream_mode="values"):
        pass
    snap = app.get_state(config)
    if snap and snap.values:
        st.session_state.pipeline_state = snap.values
    st.session_state.stage = "approved"

# Transcreator mode helpers
def _run_transcreator(source_content, target_market, brand_tone=""):
    app = _get_transcreator_app()
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.stage = "running"
    st.session_state.pipeline_state = None
    config = _cfg()
    initial = create_transcreator_state(source_content=source_content, target_market=target_market, brand_tone=brand_tone)
    for _ in app.stream(initial, config=config, stream_mode="values"):
        pass
    snap = app.get_state(config)
    if snap and snap.values:
        st.session_state.pipeline_state = snap.values
    st.session_state.stage = "review"

def _approve_transcreator():
    app = _get_transcreator_app()
    config = _cfg()
    app.update_state(config, {"is_approved": True}, as_node="cultural_critic")
    for _ in app.stream(None, config=config, stream_mode="values"):
        pass
    snap = app.get_state(config)
    if snap and snap.values:
        st.session_state.pipeline_state = snap.values
    st.session_state.stage = "approved"

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def render_sidebar():
    with st.sidebar:
        st.markdown("## ⚡ Xpanse.ai Command Center")

        # Mode selector
        mode = st.radio("Mode", ["Campaign Strategy", "Content Transcreation"], key="mode_radio", horizontal=True)
        if mode != st.session_state.app_mode:
            st.session_state.app_mode = mode
            st.session_state.stage = "idle"
            st.session_state.pipeline_state = None
            st.session_state.thread_id = None
            st.rerun()

        # Mode description
        if mode == "Campaign Strategy":
            st.caption(
                "🏗️ **3-Agent Pipeline** — Analyzes past campaign archives, "
                "researches live market trends, then synthesizes a full campaign "
                "strategy. You review and refine with feedback until approved."
            )
        else:
            st.caption(
                "🌐 **Content Transcreation** — Researches local culture for your "
                "target market, adapts your English copy to resonate locally, then "
                "a critic scores it. Auto-loops until quality passes, then you approve."
            )

        st.markdown("---")

        # System Health
        st.markdown("**System**")
        c1, c2 = st.columns(2)
        with c1:
            _led("Archive KnowledgeBase", bool(os.getenv("ARCHIVE_KB_ID")))
            _led("Brand KnowledgeBase", bool(os.getenv("BRAND_KB_ID")))
        with c2:
            _led("Web Search Tool", bool(os.getenv("TAVILY_API_KEY")))
            _led("Bedrock Model", bool(os.getenv("AWS_REGION") or True))

        st.markdown("---")

        # Mode-specific inputs
        brief = None
        if st.session_state.app_mode == "Campaign Strategy":
            brief = _campaign_inputs()
        else:
            brief = _transcreator_inputs()

        # Execution log
        st.markdown("---")
        st.markdown("**Execution Log**")
        _render_timeline()

        # Visitor stats
        st.markdown("---")
        if _VISITORS_FILE.exists():
            vdata = json.loads(_VISITORS_FILE.read_text())
            st.markdown(f"**Visitors:** {vdata['total_visits']} total sessions")

    return brief

def _campaign_inputs():
    st.markdown("**Campaign Brief**")
    aim = st.text_area("Objective", placeholder="Campaign goal, audience, budget...", height=100, key="in_aim")
    cons = st.text_input("Constraints", placeholder="Guardrails", key="in_cons")
    exp = st.checkbox("Geographic Expansion", key="in_exp")
    reg = st.text_input("Region", placeholder="e.g., Japan", key="in_reg") if exp else None
    st.markdown("---")
    can = st.session_state.stage in ("idle", "approved")
    if st.button("▶ Launch Strategy Engine", disabled=not can, use_container_width=True, type="primary", key="btn_campaign"):
        if aim.strip():
            return ("campaign", {"campaign_aim": aim.strip(), "target_audience": "", "budget": 0.0, "duration": "", "constraints": cons.strip(), "is_expansion": exp, "target_region": reg.strip() if reg else None})
        st.error("Enter objective.")
    return None

def _transcreator_inputs():
    st.markdown("**Content Transcreation**")
    content = st.text_area("Source Content (English)", placeholder="Paste your marketing copy here...", height=120, key="in_content")
    market = st.selectbox("Target Market", ["Japan", "Germany", "France", "Brazil", "India", "South Korea", "Italy", "Mexico", "UAE"], key="in_market")
    tone = st.text_input("Brand Tone (optional)", placeholder="e.g., playful, premium, minimalist", key="in_tone")
    st.markdown("---")
    can = st.session_state.stage in ("idle", "approved")
    if st.button("▶ Launch Transcreator", disabled=not can, use_container_width=True, type="primary", key="btn_trans"):
        if content.strip():
            return ("transcreator", {"source_content": content.strip(), "target_market": market, "brand_tone": tone.strip()})
        st.error("Paste source content.")
    return None

def _led(label, ok):
    cls = "led-on" if ok else "led-off"
    st.markdown(f'<span class="led {cls}">{"●" if ok else "○"} {label}</span>', unsafe_allow_html=True)

def _render_timeline():
    state = st.session_state.pipeline_state or {}
    log = state.get("execution_log", [])
    if not log:
        st.caption("No activity yet.")
        return
    names = {"sentinel": "Historian", "seer": "Market Intel", "architect": "Architect", "router": "Router", "researcher": "Researcher", "drafter": "Drafter", "critic": "Critic"}
    html = ""
    for e in log[-12:]:
        agent = names.get(e.get("agent", ""), e.get("agent", ""))
        ts = e.get("timestamp", "")
        status = e.get("status", "")
        dot = "tl-green" if "complete" in status else "tl-blue"
        html += f'<div class="tl-entry"><span class="tl-dot {dot}"></span><span>{ts} {agent} [{status}]</span></div>'
    st.markdown(html, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Campaign Mode UI (existing)
# ---------------------------------------------------------------------------
def render_campaign_flow(state):
    active = state.get("active_node", "")
    has_s = bool(state.get("historical_dna"))
    has_r = bool(state.get("market_pulse"))
    has_a = bool(state.get("strategy_document"))
    target = state.get("target_node", "")
    def ncls(n, d):
        if active == n: return "flow-node-active"
        return "flow-node-done" if d else "flow-node-pending"
    def ecls(l, r): return "flow-edge-done" if l and r else ""
    def lcls(d): return "flow-label-done" if d else ""
    html = f'''<div class="flow-graph">
    <div style="text-align:center"><div class="flow-node {ncls("sentinel",has_s)}">📚</div><div class="flow-label {lcls(has_s)}">Historian</div></div>
    <div class="flow-edge {ecls(has_s,has_r)}"></div>
    <div style="text-align:center"><div class="flow-node {ncls("seer",has_r)}">🌐</div><div class="flow-label {lcls(has_r)}">Market Intel</div></div>
    <div class="flow-edge {ecls(has_r,has_a)}"></div>
    <div style="text-align:center"><div class="flow-node {ncls("architect",has_a)}">🏗️</div><div class="flow-label {lcls(has_a)}">Architect</div></div>
    <div class="flow-edge {ecls(has_a,bool(target))}"></div>
    <div style="text-align:center"><div class="flow-node {"flow-node-done" if target=="end" else ("flow-node-loopback" if target else "flow-node-pending")}">↻</div><div class="flow-label">Router</div></div>
    </div>'''
    st.markdown(html, unsafe_allow_html=True)

def render_campaign_review(state):
    render_campaign_flow(state)
    reasoning = state.get("router_reasoning", "")
    if reasoning and state.get("loop_count", 0) > 1:
        st.markdown(f'<div class="impact-card">🧠 {reasoning}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        done = bool(state.get("historical_dna"))
        st.markdown(f'<div class="agent-card {"card-done" if done else "card-pending"}"><b>📚 Campaign Historian</b></div>', unsafe_allow_html=True)
        if done:
            with st.expander("Past Campaign Analysis"):
                st.markdown(state.get("historical_dna", ""))
            recs = state.get("sentinel_recommendations", "")
            if recs:
                with st.expander("→ Recommendations to Market Intel & Architect"):
                    st.markdown(recs)
    with c2:
        done = bool(state.get("market_pulse"))
        queries = state.get("tavily_queries", [])
        st.markdown(f'<div class="agent-card {"card-done" if done else "card-pending"}"><b>🌐 Market Intelligence</b></div>', unsafe_allow_html=True)
        if queries:
            with st.expander("🔍 Web Search Activity"):
                for q in queries:
                    st.markdown(f"✓ `{q}`")
        if done:
            with st.expander("Search Intelligence Report"):
                st.markdown(state.get("market_pulse", ""))
            recs = state.get("seer_recommendations", "")
            if recs:
                with st.expander("→ Recommendations to Architect"):
                    st.markdown(recs)
    strategy = state.get("strategy_document", "")
    if strategy:
        st.markdown('<div class="agent-card card-done"><b>🏗️ Campaign Architect</b></div>', unsafe_allow_html=True)
        prev = state.get("previous_strategy", "")
        if prev and prev != strategy:
            t1, t2 = st.tabs(["Strategy", "Changes"])
            with t1: st.markdown(strategy)
            with t2: _render_diff(prev, strategy)
        else:
            with st.expander("View Strategy", expanded=True):
                st.markdown(strategy)
    # Approval gate
    with st.container(border=True):
        st.markdown("**⚠ Approval Gate**")
        st.caption("past/history → Historian · market/trends → Market Intel · strategy/tone → Architect")
        fb = st.text_area("Feedback", placeholder="What should change?", height=60, key="fb_camp", label_visibility="collapsed")
        ca, cf = st.columns(2)
        with ca:
            if st.button("✓ Approve", use_container_width=True, key="btn_camp_ok"):
                with st.spinner("Finalizing..."): _approve_campaign()
                st.rerun()
        with cf:
            if st.button("↻ Refine", use_container_width=True, key="btn_camp_fb"):
                if not fb.strip(): st.warning("Provide feedback.")
                else:
                    with st.spinner("Re-processing..."): _resume_campaign_feedback(fb.strip())
                    st.rerun()
        history = state.get("feedback_history", [])
        if history:
            with st.expander(f"Log ({len(history)})"):
                for i, f in enumerate(history, 1): st.markdown(f"`[{i}]` {f}")

# ---------------------------------------------------------------------------
# Transcreator Mode UI (new)
# ---------------------------------------------------------------------------
def render_transcreator_flow(state):
    has_r = bool(state.get("cultural_research"))
    has_d = bool(state.get("draft_content"))
    has_c = state.get("critic_score", 0) > 0
    loops = state.get("reflection_loops", 0)
    active = state.get("active_node", "")
    def ncls(n, d):
        if active == n: return "flow-node-active"
        return "flow-node-done" if d else "flow-node-pending"
    def ecls(l, r): return "flow-edge-done" if l and r else ""
    def lcls(d): return "flow-label-done" if d else ""
    html = f'''<div class="flow-graph">
    <div style="text-align:center"><div class="flow-node {ncls("researcher",has_r)}">🔬</div><div class="flow-label {lcls(has_r)}">Researcher</div></div>
    <div class="flow-edge {ecls(has_r,has_d)}"></div>
    <div style="text-align:center"><div class="flow-node {ncls("drafter",has_d)}">✍️</div><div class="flow-label {lcls(has_d)}">Drafter</div></div>
    <div class="flow-edge {ecls(has_d,has_c)}"></div>
    <div style="text-align:center"><div class="flow-node {ncls("critic",has_c)}">🎭</div><div class="flow-label {lcls(has_c)}">Critic</div></div>
    </div>'''
    if loops > 1:
        html += f'<div style="text-align:center;font-size:0.62rem;color:#d29922;">⤺ {loops} reflection loops completed</div>'
    st.markdown(html, unsafe_allow_html=True)

def render_transcreator_review(state):
    render_transcreator_flow(state)

    # Critic score bar
    score = state.get("critic_score", 0)
    loops = state.get("reflection_loops", 0)
    color = "#3fb950" if score >= 7 else ("#d29922" if score >= 5 else "#f85149")
    st.markdown(f'<div style="font-size:11px;margin-bottom:2px;">Critic Score: <b>{score}/10</b> · Loops: {loops}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="score-bar"><div class="score-fill" style="width:{score*10}%;background:{color};"></div></div>', unsafe_allow_html=True)

    # Cultural Research
    c1, c2 = st.columns(2)
    with c1:
        done = bool(state.get("cultural_research"))
        st.markdown(f'<div class="agent-card {"card-done" if done else "card-pending"}"><b>🔬 Cultural Researcher</b></div>', unsafe_allow_html=True)
        if done:
            with st.expander("Cultural Intelligence Brief"):
                st.markdown(state.get("cultural_research", ""))
            queries = state.get("research_queries", [])
            if queries:
                with st.expander("🔍 Research Queries"):
                    for q in queries: st.markdown(f"✓ `{q}`")

    with c2:
        done = bool(state.get("draft_content"))
        st.markdown(f'<div class="agent-card {"card-done" if done else "card-pending"}"><b>✍️ Content Drafter</b></div>', unsafe_allow_html=True)
        if done:
            with st.expander("Localized Content (Latest Draft)"):
                st.markdown(state.get("draft_content", ""))

    # Critic feedback (if any)
    critic_fb = state.get("critic_feedback", "")
    if critic_fb:
        with st.expander("🎭 Critic Feedback (addressed in latest draft)"):
            st.markdown(critic_fb)

    # Draft versions
    versions = state.get("draft_versions", [])
    if len(versions) > 1:
        with st.expander(f"📜 Draft History ({len(versions)} versions)"):
            for v in versions:
                st.markdown(f"**v{v.get('version')}** — critic: _{v.get('critic_feedback', 'initial')[:80]}…_")

    # Approval gate
    with st.container(border=True):
        st.markdown("**✓ Human Review**")
        st.caption(f"The critic scored this {score}/10. Review the localized content and approve or request changes.")
        ca, _ = st.columns([1, 1])
        with ca:
            if st.button("✓ Approve Content", use_container_width=True, key="btn_trans_ok"):
                with st.spinner("Finalizing..."): _approve_transcreator()
                st.rerun()

def render_approved(state):
    if st.session_state.app_mode == "Campaign Strategy":
        render_campaign_flow(state)
        st.success("Strategy approved.")
        with st.expander("Final Strategy", expanded=True):
            st.markdown(state.get("strategy_document", ""))
    else:
        render_transcreator_flow(state)
        st.success("Transcreated content approved.")
        with st.expander("Final Localized Content", expanded=True):
            st.markdown(state.get("draft_content", ""))
    if st.button("↻ Start New", key="btn_rst"):
        st.session_state.stage = "idle"
        st.session_state.pipeline_state = None
        st.session_state.thread_id = None
        st.rerun()

# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------
def _render_diff(old, new):
    if not old or not new or old == new: return
    diff = list(difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=1))
    if not diff: return
    html = '<div style="font-family:monospace;font-size:11px;max-height:180px;overflow-y:auto;background:#0d1117;border:1px solid #21262d;border-radius:4px;padding:6px;">'
    for line in diff[2:]:
        if line.startswith("+"): html += f'<div class="diff-add">{line}</div>'
        elif line.startswith("-"): html += f'<div class="diff-del">{line}</div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

def render_idle():
    mode = st.session_state.app_mode
    if mode == "Campaign Strategy":
        st.markdown("""<div class="agent-card" style="padding:1.5rem;">
<p style="color:#e6edf3;font-size:13px;font-weight:600;margin-bottom:8px;">How it works</p>
<p style="color:#8b949e;margin-bottom:6px;">1. <b>📚 Campaign Historian</b> — Queries your past campaign archive & brand KB to find what worked and what failed</p>
<p style="color:#8b949e;margin-bottom:6px;">2. <b>🌐 Market Intelligence</b> — Searches live web data to validate historical patterns against current trends</p>
<p style="color:#8b949e;margin-bottom:6px;">3. <b>🏗️ Campaign Architect</b> — Synthesizes both inputs into a complete strategy with budget, flow, and messaging</p>
<p style="color:#8b949e;margin-bottom:6px;">4. <b>↻ Feedback Router</b> — You review and provide feedback; an LLM routes it to the right agent for revision</p>
<p style="color:#58a6ff;margin-top:12px;font-size:12px;">Enter your campaign brief in the sidebar → Launch Strategy Engine</p>
</div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="agent-card" style="padding:1.5rem;">
<p style="color:#e6edf3;font-size:13px;font-weight:600;margin-bottom:8px;">How it works</p>
<p style="color:#8b949e;margin-bottom:6px;">1. <b>🔬 Cultural Researcher</b> — Searches the web for local slang, taboos, purchasing psychology, and marketing norms</p>
<p style="color:#8b949e;margin-bottom:6px;">2. <b>✍️ Content Drafter</b> — Transcreates (not translates) your copy to resonate with the local audience</p>
<p style="color:#8b949e;margin-bottom:6px;">3. <b>🎭 Cultural Critic</b> — A strict native reviewer scores the draft on authenticity, resonance, and idiom usage</p>
<p style="color:#8b949e;margin-bottom:6px;">4. <b>⤺ Auto-Loop</b> — If score &lt; 7/10, the drafter revises automatically (up to 3 loops)</p>
<p style="color:#58a6ff;margin-top:12px;font-size:12px;">Paste your English marketing copy in the sidebar → Launch Transcreator</p>
</div>""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    brief = render_sidebar()

    mode = st.session_state.app_mode
    title = "Campaign Strategy Engine" if mode == "Campaign Strategy" else "Content Transcreator"
    st.markdown(f"# Xpanse.ai — {title}")

    stage = st.session_state.stage
    state = st.session_state.pipeline_state or {}

    if stage in ("idle", "running"):
        render_idle()

    if brief:
        mode_key, params = brief
        with st.spinner("Running agent pipeline..."):
            try:
                if mode_key == "campaign":
                    _run_campaign(params)
                else:
                    _run_transcreator(**params)
            except Exception as e:
                st.error(f"Pipeline error: {e}")
                st.session_state.stage = "idle"
        st.rerun()

    if stage == "review":
        if mode == "Campaign Strategy":
            render_campaign_review(state)
        else:
            render_transcreator_review(state)
    elif stage == "approved":
        render_approved(state)

if __name__ == "__main__":
    main()

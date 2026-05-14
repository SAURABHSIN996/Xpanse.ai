"""Xpanse V2.0 — Graph State Definition.

Intent-aware state with processing phases, feedback routing,
version history, execution log, and diff support.
"""

from typing import Annotated, TypedDict, List, Dict, Optional
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # Core
    thread_id: str
    messages: Annotated[list, add_messages]

    # --- Strategic Brief Inputs ---
    campaign_aim: str
    target_audience: str
    budget: float
    duration: str
    constraints: str
    is_expansion: bool
    target_region: Optional[str]

    # --- Intent Stream ---
    active_node: str                # Currently executing node name
    processing_phase: str           # 'analysis' | 'scouting' | 'synthesis' | 'routing' | 'complete'

    # --- Agent 1: Performance Sentinel ---
    archive_report: str
    historical_dna: str
    archive_metrics: Dict[str, str]
    citations: List[str]
    analysis_data: str

    # --- Agent 2: Strategic Seer ---
    market_pulse: str
    seer_report: str
    research_data: str
    tavily_queries: List[str]

    # --- Agent 3: Campaign Architect ---
    strategy_document: str
    strategy_flow: str
    budget_table: str
    previous_strategy: str          # Stored before re-run for diff

    # --- Agent 4: Feedback Router ---
    target_node: str                # 'sentinel' | 'seer' | 'architect' | 'end'
    router_reasoning: str           # One-line explanation of routing decision

    # --- Human-in-the-Loop ---
    human_feedback: str
    feedback_history: List[str]
    is_approved: bool

    # --- Version History ---
    strategy_versions: List[Dict[str, str]]  # [{version, document, feedback, target}]

    # --- Execution Log ---
    execution_log: List[Dict[str, str]]  # [{agent, timestamp, trigger, status}]

    # --- Agent Recommendations (passed between agents) ---
    sentinel_recommendations: str   # Extracted recs from Historian → Seer/Architect
    seer_recommendations: str       # Extracted recs from Market Intel → Architect

    # --- Feedback Impact ---
    feedback_impact: str            # Summary of what changed after feedback

    # --- Iteration tracking ---
    loop_count: int


# ===========================================================================
# Transcreator State (Market Mirror mode)
# ===========================================================================


class TranscreatorState(TypedDict):
    # Core
    thread_id: str
    messages: Annotated[list, add_messages]

    # --- Inputs ---
    source_content: str          # Original English marketing copy
    target_market: str           # e.g., "Japan", "Germany"
    brand_tone: str              # Optional brand tone override

    # --- Agent 1: Cultural Researcher ---
    cultural_research: str       # Local insights from Tavily
    research_queries: List[str]  # Tavily queries executed

    # --- Agent 2: Content Drafter ---
    draft_content: str           # Current localized draft
    previous_draft: str          # For diff view
    draft_versions: List[Dict[str, str]]  # All iterations

    # --- Agent 3: Cultural Critic ---
    critic_score: int            # 1-10 quality score
    critic_feedback: str         # Specific issues to fix

    # --- Loop control ---
    reflection_loops: int        # Current loop count
    max_loops: int               # Cap (default 3)

    # --- HITL ---
    human_feedback: str
    is_approved: bool

    # --- Execution ---
    active_node: str
    execution_log: List[Dict[str, str]]


def create_transcreator_state(
    source_content: str = "",
    target_market: str = "",
    brand_tone: str = "",
    max_loops: int = 3,
) -> "TranscreatorState":
    """Create initial state for a transcreation pipeline run."""
    return {
        "thread_id": "",
        "messages": [],
        "source_content": source_content,
        "target_market": target_market,
        "brand_tone": brand_tone,
        "cultural_research": "",
        "research_queries": [],
        "draft_content": "",
        "previous_draft": "",
        "draft_versions": [],
        "critic_score": 0,
        "critic_feedback": "",
        "reflection_loops": 0,
        "max_loops": max_loops,
        "human_feedback": "",
        "is_approved": False,
        "active_node": "",
        "execution_log": [],
    }


def create_initial_state(
    campaign_aim: str = "",
    target_audience: str = "",
    budget: float = 0.0,
    duration: str = "",
    constraints: str = "",
    is_expansion: bool = False,
    target_region: Optional[str] = None,
) -> "AgentState":
    """Create the initial state for a new pipeline run."""
    return {
        "thread_id": "",
        "messages": [],
        "campaign_aim": campaign_aim,
        "target_audience": target_audience,
        "budget": budget,
        "duration": duration,
        "constraints": constraints,
        "is_expansion": is_expansion,
        "target_region": target_region if is_expansion else None,
        "active_node": "",
        "processing_phase": "",
        "archive_report": "",
        "historical_dna": "",
        "archive_metrics": {},
        "citations": [],
        "analysis_data": "",
        "market_pulse": "",
        "seer_report": "",
        "research_data": "",
        "tavily_queries": [],
        "strategy_document": "",
        "strategy_flow": "",
        "budget_table": "",
        "previous_strategy": "",
        "target_node": "",
        "router_reasoning": "",
        "human_feedback": "",
        "feedback_history": [],
        "is_approved": False,
        "strategy_versions": [],
        "execution_log": [],
        "sentinel_recommendations": "",
        "seer_recommendations": "",
        "feedback_impact": "",
        "loop_count": 0,
    }

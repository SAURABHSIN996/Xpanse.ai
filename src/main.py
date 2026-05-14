"""Xpanse.ai — Phase 3 Main Orchestrator with Feedback Router.

Three-Agent + Router Pipeline:
    1. Performance Sentinel (KB RAG) → 2. Strategic Seer (Tavily) →
    3. Campaign Architect (Strategy Synthesis) → [INTERRUPT] →
    4. Feedback Router (LLM intent classification) → loops or END

The graph pauses after 'campaign_architect' for human review.
User provides feedback, and the router intelligently directs it.
"""

import logging
import uuid

from langgraph.checkpoint.memory import MemorySaver

from src.graph.state import create_initial_state
from src.graph.workflow import build_graph

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared checkpointer and compiled graph
# ---------------------------------------------------------------------------

_checkpointer = MemorySaver()
_app = build_graph(checkpointer=_checkpointer)


# ---------------------------------------------------------------------------
# Run the pipeline (up to HITL interrupt after Campaign Architect)
# ---------------------------------------------------------------------------


def run_strategy(
    campaign_aim: str,
    target_audience: str = "",
    budget: float = 0.0,
    duration: str = "",
    constraints: str = "",
    is_expansion: bool = False,
    target_region: str | None = None,
) -> str:
    """Run the pipeline from Performance Sentinel through Campaign Architect.

    The graph pauses after campaign_architect via interrupt_after,
    waiting for human review and feedback.

    Args:
        campaign_aim: Primary campaign objective.
        target_audience: Description of the target audience.
        budget: Campaign budget in dollars.
        duration: Campaign duration string.
        constraints: Forbidden content or mandatory disclaimers.
        is_expansion: Whether geographic expansion is enabled.
        target_region: Target region (only used if is_expansion=True).

    Returns:
        The thread_id for this run (needed for resume/feedback).
    """
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = create_initial_state(
        campaign_aim=campaign_aim,
        target_audience=target_audience,
        budget=budget,
        duration=duration,
        constraints=constraints,
        is_expansion=is_expansion,
        target_region=target_region,
    )

    logger.info("=" * 60)
    logger.info("Starting Xpanse Phase 3 Pipeline")
    logger.info("  Objective : %s", campaign_aim[:80])
    logger.info("  Expansion : %s → %s", is_expansion, target_region or "N/A")
    logger.info("  Thread    : %s", thread_id)
    logger.info("=" * 60)

    final_state = None
    for state_snapshot in _app.stream(initial_state, config=config, stream_mode="values"):
        final_state = state_snapshot

    # Print results
    print("\n" + "=" * 60)
    print("  STRATEGY PIPELINE — Paused for Human Review")
    print("=" * 60)

    if final_state:
        strategy = final_state.get("strategy_document", "")
        if strategy:
            print("\n── CAMPAIGN STRATEGY (for review) ──────────────────────")
            print(strategy[:800] + "..." if len(strategy) > 800 else strategy)

    print("\n" + "=" * 60)
    print(f"  Thread: {thread_id}")
    print("  Call provide_feedback() or approve_strategy() to continue.")
    print("=" * 60 + "\n")

    return thread_id


# ---------------------------------------------------------------------------
# Provide feedback (routed by the Feedback Router)
# ---------------------------------------------------------------------------


def provide_feedback(thread_id: str, feedback: str) -> None:
    """Provide feedback — the Feedback Router will determine which agent to re-run.

    Args:
        thread_id: The thread ID from run_strategy().
        feedback: Human feedback text. The router analyzes this to decide routing.
    """
    config = {"configurable": {"thread_id": thread_id}}

    state_update = {
        "human_feedback": feedback,
        "is_approved": False,
    }

    logger.info("Providing feedback to thread %s: %s", thread_id, feedback[:60])

    _app.update_state(config, state_update, as_node="campaign_architect")

    final_state = None
    for state_snapshot in _app.stream(None, config=config, stream_mode="values"):
        final_state = state_snapshot

    if final_state:
        target = final_state.get("target_node", "unknown")
        strategy = final_state.get("strategy_document", "")
        print(f"\n── Router Decision: {target} ────────────────────────────")
        if strategy:
            print(strategy[:800] + "..." if len(strategy) > 800 else strategy)
        print("\n" + "=" * 60)
        print(f"  Thread: {thread_id}")
        print("  Call provide_feedback() or approve_strategy() again.")
        print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Approve the strategy
# ---------------------------------------------------------------------------


def approve_strategy(thread_id: str) -> None:
    """Approve the strategy — routes to END via the Feedback Router.

    Args:
        thread_id: The thread ID from run_strategy().
    """
    config = {"configurable": {"thread_id": thread_id}}

    state_update = {
        "human_feedback": "approve",
        "is_approved": True,
        "target_node": "end",
    }

    _app.update_state(config, state_update, as_node="campaign_architect")

    final_state = None
    for state_snapshot in _app.stream(None, config=config, stream_mode="values"):
        final_state = state_snapshot

    logger.info("Strategy APPROVED for thread %s", thread_id)
    print("\n✅ Strategy approved. Campaign strategy is finalized.\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    thread = run_strategy(
        campaign_aim="Expand Sneaker Rewards Program to increase Gen-Z enrollment by 15%",
        target_audience="Gen-Z consumers aged 18-25 interested in streetwear and sneaker culture",
        budget=50000.0,
        duration="14 Days",
        constraints="No misleading claims about reward values. Must include unsubscribe option.",
        is_expansion=True,
        target_region="Japan",
    )

    # Interactive loop:
    # provide_feedback(thread, "I need more data on past campaign metrics")
    # provide_feedback(thread, "Research competitor trends in Japan market")
    # approve_strategy(thread)

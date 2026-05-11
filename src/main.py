"""Xpanse Agents — Main Orchestrator Entry Point.

Execution model
---------------
Stage 1 (Blueprint):
    compliance ──┐
                 ├──► human_review  ──► [INTERRUPT]
    strategy   ──┘

The graph pauses before the 'architect' node, waiting for a human to review
the Expansion Blueprint and set is_approved=True (or provide feedback).

Stage 2 (Implementation) — triggered by resume_with_approval():
    architect ──► qa ──► END
"""

import logging
import uuid

from langgraph.checkpoint.memory import MemorySaver

from src.graph.state import create_initial_state #from state.py
from src.graph.workflow import build_graph #from workflow.py

# ---------------------------------------------------------------------------
# Logging python
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

# MemorySaver keeps state in-process. For production, swap in SqliteSaver or
# a Postgres-backed checkpointer to persist state across restarts.
_checkpointer = MemorySaver()
_app = build_graph(checkpointer=_checkpointer)


# ---------------------------------------------------------------------------
# Stage 1: Run the Blueprint phase
# ---------------------------------------------------------------------------


def run_expansion(region: str, goal: str) -> str:
    """Initialise and run Stage 1 of the Xpanse Agent pipeline.

    Invokes the graph from START through the compliance + strategy nodes
    (in parallel) and the human_review node, then pauses at the
    interrupt_before=["architect"] gate.

    Args:
        region: Target geographic region (e.g. 'Japan').
        goal:   The campaign objective as a plain-English string.

    Returns:
        The thread_id for this run. Pass it to resume_with_approval() later.
    """
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = create_initial_state(
        target_region=region,
        campaign_goal=goal,
    )

    logger.info("=" * 60)
    logger.info("Starting Xpanse Agent pipeline")
    logger.info("  Region : %s", region)
    logger.info("  Goal   : %s", goal)
    logger.info("  Thread : %s", thread_id)
    logger.info("=" * 60)

    # stream_mode="values" yields the full state after each node completes.
    # The graph will stop automatically at interrupt_before=["architect"].
    final_state = None
    for state_snapshot in _app.stream(initial_state, config=config, stream_mode="values"):
        final_state = state_snapshot

    # -----------------------------------------------------------------------
    # Print the Expansion Blueprint (Stage 1 outputs)
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("  EXPANSION BLUEPRINT — Stage 1 Complete")
    print("=" * 60)

    compliance = (final_state or {}).get("compliance_output")
    strategy = (final_state or {}).get("strategy_output")

    if compliance:
        print("\n── COMPLIANCE RISK REPORT ──────────────────────────────")
        print(compliance)
    else:
        print("\n[Compliance output not yet available]")

    if strategy:
        print("\n── LOCALISED STRATEGY ──────────────────────────────────")
        print(strategy)
    else:
        print("\n[Strategy output not yet available]")

    print("\n" + "=" * 60)
    print("  Graph paused before 'architect' node.")
    print("  Review the blueprint above, then call:")
    print(f"    resume_with_approval(thread_id='{thread_id}', approved=True)")
    print("  Or provide feedback:")
    print(f"    resume_with_approval(thread_id='{thread_id}', approved=False,")
    print("                         feedback='<your notes here>')")
    print("=" * 60 + "\n")

    return thread_id


# ---------------------------------------------------------------------------
# Stage 2: Resume after human review
# ---------------------------------------------------------------------------


def resume_with_approval(
    thread_id: str,
    approved: bool,
    feedback: str | None = None,
) -> None:
    """Resume the graph after human review of the Expansion Blueprint.

    This function injects the human decision into the persisted state and
    resumes execution from the interrupt point.

    Args:
        thread_id: The thread ID returned by run_expansion().
        approved:  True to proceed to the architect; False to loop back to
                   the strategy node with optional feedback.
        feedback:  Optional reviewer notes passed to the Cultural Strategist
                   on the next strategy iteration (only used when approved=False).

    Example — approve and proceed to Stage 2:
        resume_with_approval(thread_id="abc-123", approved=True)

    Example — reject with feedback:
        resume_with_approval(
            thread_id="abc-123",
            approved=False,
            feedback="Increase cashback percentage for Gen-Z segment.",
        )
    """
    config = {"configurable": {"thread_id": thread_id}}

    # Build the state update to inject before resuming
    state_update: dict = {"is_approved": approved}
    if feedback:
        state_update["human_feedback"] = feedback

    logger.info(
        "Resuming thread %s — approved=%s feedback=%s",
        thread_id,
        approved,
        repr(feedback),
    )

    # Update the persisted state, then resume by invoking with None input
    _app.update_state(config, state_update)

    final_state = None
    for state_snapshot in _app.stream(None, config=config, stream_mode="values"):
        final_state = state_snapshot

    if approved:
        artifacts = (final_state or {}).get("technical_artifacts", {})
        print("\n" + "=" * 60)
        print("  TECHNICAL ARTIFACTS — Stage 2 Complete")
        print("=" * 60)

        sql = artifacts.get("sql")
        python_code = artifacts.get("python")
        qa_report = artifacts.get("qa_report")

        if sql:
            print("\n── SNOWFLAKE SQL ────────────────────────────────────────")
            print(sql)
        if python_code:
            print("\n── AWS LAMBDA PYTHON ────────────────────────────────────")
            print(python_code)
        if qa_report:
            print("\n── QA REPORT ────────────────────────────────────────────")
            print(qa_report)

        print("\n" + "=" * 60 + "\n")
    else:
        logger.info(
            "Strategy loop triggered. Call run_expansion() output or "
            "resume_with_approval() again after reviewing the updated blueprint."
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Test run: Japan / Sneaker Rewards expansion
    thread = run_expansion(
        region="Japan",
        goal="Expand Sneaker Rewards Program",
    )

    # -----------------------------------------------------------------------
    # To continue to Stage 2, uncomment and run:
    #
    resume_with_approval(thread_id=thread, approved=True)
    #
    # Or to loop back with feedback:
    #
    # resume_with_approval(
    #     thread_id=thread,
    #     approved=False,
    #     feedback="Increase point multiplier for limited-edition drops.",
    # )
    # -----------------------------------------------------------------------

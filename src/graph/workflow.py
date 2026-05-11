"""LangGraph StateGraph orchestrating the Xpanse Agents pipeline.

Flow
----
START
  └─► [compliance] ──┐
                     ├─► [human_review]  ──(interrupt_before architect)──►
  └─► [strategy]  ──┘        │
                              │ is_approved=True  ──► [architect] ──► [qa] ──► END
                              │ is_approved=False ──► [strategy]  (loop with feedback)
"""

import logging
from typing import Literal

from langgraph.graph import END, START, StateGraph

from src.agents.prompts import (
    COMPLIANCE_SENTINEL,
    CULTURAL_STRATEGIST,
    QA_VALIDATOR,
    TECHNICAL_ARCHITECT,
)
from src.graph.state import AgentState
from src.utils.bedrock import invoke_agent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------


def compliance_node(state: AgentState) -> dict:
    """Run the Compliance Sentinel against the campaign goal and target region."""
    logger.info("Running compliance node for region: %s", state["target_region"])

    user_content = (
        f"Target Region: {state['target_region']}\n"
        f"Campaign Goal: {state['campaign_goal']}"
    )
    result = invoke_agent(COMPLIANCE_SENTINEL, user_content)
    return {"compliance_output": result}


def strategy_node(state: AgentState) -> dict:
    """Run the Cultural Strategist, optionally incorporating human feedback."""
    logger.info("Running strategy node")

    user_content = (
        f"Target Region: {state['target_region']}\n"
        f"Campaign Goal: {state['campaign_goal']}\n"
    )

    if state.get("compliance_output"):
        user_content += f"\nCompliance Risks:\n{state['compliance_output']}"

    if state.get("human_feedback"):
        user_content += f"\nHuman Reviewer Feedback:\n{state['human_feedback']}"

    result = invoke_agent(CULTURAL_STRATEGIST, user_content)
    return {"strategy_output": result}


def human_review_node(state: AgentState) -> dict:
    """Placeholder node that surfaces outputs for human review.

    In production this node is a no-op — the actual human decision is injected
    externally by updating `is_approved` (and optionally `human_feedback`) on
    the persisted state before resuming the graph after the interrupt.
    """
    logger.info(
        "Human review node reached. Awaiting external approval decision. "
        "is_approved=%s",
        state.get("is_approved"),
    )
    # No state mutation — the interrupt_before on 'architect' pauses execution
    # here and waits for the caller to resume with updated state.
    return {}


def architect_node(state: AgentState) -> dict:
    """Run the Technical Architect to generate SQL and Python artifacts."""
    logger.info("Running architect node")

    user_content = (
        f"Target Region: {state['target_region']}\n"
        f"Campaign Goal: {state['campaign_goal']}\n"
        f"Approved Strategy:\n{state['strategy_output']}\n"
        f"Compliance Risks:\n{state['compliance_output']}"
    )

    result = invoke_agent(TECHNICAL_ARCHITECT, user_content)

    # Parse the two artifacts out of the structured response
    artifacts = _parse_architect_output(result)
    return {"technical_artifacts": artifacts}


def qa_node(state: AgentState) -> dict:
    """Run the QA Validator to audit the Architect's code against compliance risks."""
    logger.info("Running QA node")

    artifacts = state.get("technical_artifacts", {})
    sql_code = artifacts.get("sql", "No SQL artifact found.")
    python_code = artifacts.get("python", "No Python artifact found.")

    user_content = (
        f"Compliance Risks:\n{state['compliance_output']}\n\n"
        f"Snowflake SQL:\n```sql\n{sql_code}\n```\n\n"
        f"AWS Lambda Python:\n```python\n{python_code}\n```"
    )

    result = invoke_agent(QA_VALIDATOR, user_content)
    # Store QA report alongside the code artifacts
    updated_artifacts = {**artifacts, "qa_report": result}
    return {"technical_artifacts": updated_artifacts}


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------


def approval_router(state: AgentState) -> Literal["architect", "strategy"]:
    """Route after human_review based on the is_approved flag."""
    if state.get("is_approved"):
        logger.info("Approval granted — routing to architect")
        return "architect"
    logger.info("Not approved — routing back to strategy with feedback")
    return "strategy"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def _parse_architect_output(raw: str) -> dict[str, str]:
    """Extract SQL and Python code blocks from the Architect's structured output.

    Expected format (from the TECHNICAL_ARCHITECT prompt):
        ## Snowflake SQL
        ```sql
        ...
        ```
        ## AWS Lambda Python
        ```python
        ...
        ```
    """
    artifacts: dict[str, str] = {"raw": raw}

    try:
        if "```sql" in raw and "```" in raw:
            sql_start = raw.index("```sql") + len("```sql")
            sql_end = raw.index("```", sql_start)
            artifacts["sql"] = raw[sql_start:sql_end].strip()

        if "```python" in raw and "```" in raw:
            py_start = raw.index("```python") + len("```python")
            py_end = raw.index("```", py_start)
            artifacts["python"] = raw[py_start:py_end].strip()
    except ValueError:
        logger.warning("Could not fully parse architect output; storing raw.")

    return artifacts


def build_graph(checkpointer=None):
    """Construct and compile the LangGraph StateGraph.

    Graph topology
    --------------
    START ──► compliance ──┐
                           ├──► human_review ──(conditional)──► architect ──► qa ──► END
    START ──► strategy  ──┘                         │
                           ◄────────────────────────┘ (loop back on rejection)

    The `interrupt_before=["architect"]` compile option pauses execution after
    human_review so an external caller can inspect state, set `is_approved`,
    and resume.

    Args:
        checkpointer: An optional LangGraph checkpointer (e.g. MemorySaver).
                      Required for interrupt/resume and thread-based persistence.
    """
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("compliance", compliance_node)
    graph.add_node("strategy", strategy_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("architect", architect_node)
    graph.add_node("qa", qa_node)

    # START → parallel compliance + strategy
    graph.add_edge(START, "compliance")
    graph.add_edge(START, "strategy")

    # Both parallel branches converge at human_review
    graph.add_edge("compliance", "human_review")
    graph.add_edge("strategy", "human_review")

    # Conditional gate after human_review
    graph.add_conditional_edges(
        "human_review",
        approval_router,
        {
            "architect": "architect",  # approved
            "strategy": "strategy",    # rejected → loop with feedback
        },
    )

    # Happy path: architect → qa → END
    graph.add_edge("architect", "qa")
    graph.add_edge("qa", END)

    # Compile with interrupt_before architect so the human can review first.
    # Pass checkpointer when provided — required for thread-based state persistence.
    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["architect"],
    )
    return compiled

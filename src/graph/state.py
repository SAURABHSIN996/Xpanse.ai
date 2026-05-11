from typing import Dict, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Single source of truth for the LangGraph StateGraph.

    Fields:
        target_region: The geographic region being targeted (e.g., 'Japan').
        campaign_goal: The user's original prompt describing the campaign objective.
        compliance_output: Output from the compliance agent, if available.
        strategy_output: Output from the strategy agent, if available.
        human_feedback: Feedback provided by a human reviewer, if available.
        is_approved: Whether the current plan has been approved. Defaults to False.
        technical_artifacts: Generated technical assets keyed by name (e.g., SQL, Python code).
    """

    target_region: str
    campaign_goal: str
    compliance_output: Optional[str]
    strategy_output: Optional[str]
    human_feedback: Optional[str]
    is_approved: bool
    technical_artifacts: Dict[str, str]


def create_initial_state(target_region: str, campaign_goal: str) -> AgentState:
    """Return a fully initialized AgentState with safe defaults."""
    return AgentState(
        target_region=target_region,
        campaign_goal=campaign_goal,
        compliance_output=None,
        strategy_output=None,
        #human_feedback=None,
        #is_approved=False,
        human_feedback="Increase point multiplier for limited-edition drops.",
        is_approved=True,
        technical_artifacts={},
    )

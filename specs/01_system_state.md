# Spec 01: System State

## Goal

Define the single source of truth.

## Content for Kiro

Define a TypedDict named `AgentState` for LangGraph. It must include:

- `target_region`: `str` (e.g., 'Japan')
- `campaign_goal`: `str` (The user's original prompt)
- `compliance_output`: `Optional[str]`
- `strategy_output`: `Optional[str]`
- `human_feedback`: `Optional[str]`
- `is_approved`: `bool` (Default: `False`)
- `technical_artifacts`: `Dict[str, str]` (For SQL and Python code)

Ensure all fields are initialized properly for a LangGraph StateGraph.

# Spec 03: Graph Workflow

## Goal

Define the parallel-then-sequential flow.

## Content for Kiro

Implement a LangGraph StateGraph in `workflow.py`:

**Nodes:** `compliance`, `strategy`, `human_review`, `architect`, `qa`.

**Edge Logic:**

1. Start → Parallel[`compliance`, `strategy`].
2. Parallel → `human_review`.
3. **The Gate:** Use `interrupt_before=["architect"]`.
4. If `is_approved` is `True` → `architect` → `qa` → End.
5. If `is_approved` is `False` → Loop back to `strategy` with `human_feedback`.


you can use Lang Graph MCP server to fetch additional data.
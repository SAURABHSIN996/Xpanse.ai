# Spec: Main Orchestrator Entrypoint (`main.py`)

**Goal:**
Create an executable script that compiles the LangGraph workflow, initializes a thread-based checkpointer, and executes the Stage 1 "Blueprint" phase.

---

## Instruction for Kiro:

Generate `src/main.py` to act as the entry point for the Xpanse Agent system. Follow these requirements:

### Imports:
- Import `StateGraph` and `START` from `langgraph.graph`
- Import `MemorySaver` from `langgraph.checkpoint.memory`
- Import `AgentState` and node functions from local files.

### Graph Assembly:
- Initialize `StateGraph(AgentState)`.
- Add nodes for **compliance**, **strategist**, **architect**, and **qa**.

### Edges:
- Connect `START` to both **compliance** and **strategist** (Parallel Stage 1).
- Connect both Stage 1 nodes to a dummy `human_review` node.
- From `human_review`, add a conditional edge:
  - If `is_approved` is True, go to **architect**;
  - Otherwise, go to END (or loop back).

### The Gate:
Compile the graph using a `MemorySaver()` checkpointer and set `interrupt_before=["architect"].

# Execution Logic

Define a `run_expansion(region, goal)` function.

- It should initialize a `thread_id`.
- Invoke the graph with the initial state.
- Print the outputs of **Stage 1**.

## Placeholder for Human Approval
Add a placeholder comment or function `resume_with_approval()` that shows how a human would later trigger the `'is_approved'` flag to resume the graph.

## CLI Interface
Add an `if __name__ == "__main__":` block that allows me to trigger a test run for `'Japan'` and `'Expand Sneaker Rewards Program'`.
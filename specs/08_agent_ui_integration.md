# Agent-UI Communication Protocol

## 1. The Session State Handshake
To maintain the connection between the UI and the Agents, the following variables must be stored in `st.session_state`:
- `thread_id`: A unique UUID for the current expansion session.
- `graph_app`: The compiled LangGraph instance.
- `current_stage`: Tracking if we are in 'Analysis', 'Awaiting Review', or 'Completed'.

## 2. Communication Lifecycle
### Phase 1: Initialization
- When the user clicks `Launch`, the UI initializes the `AgentState` with `target_region` and `campaign_goal`.
- The UI calls `graph_app.stream(initial_input, thread_id)`.

### Phase 2: The Interrupt (Stage 2)
- The Graph reaches the `human_review` node and pauses due to `interrupt_before`.
- The UI detects the pause, stops the spinner, and displays the **Review Panel** from `04_ui_design.md`.

### Phase 3: State Injection (The Resume)
- **Approval:** UI calls `app.update_state(config, {"is_approved": True})`.
- **Refinement:** UI calls `app.update_state(config, {"human_feedback": user_input, "is_approved": False})`.
- The UI then calls `app.stream(None, config)` to resume execution.

## 3. Data Extraction
- The UI must parse the `AgentState` after every node completion to extract specific keys:
    - `compliance_report` -> Displayed in Compliance Card.
    - `localized_strategy` -> Displayed in Strategy Card.
    - `technical_artifacts` -> Populated in Stage 3 Tabs.

# UI Architecture & Technology Stack

## 1. Core Technology Stack (Strict)
- **Framework:** Streamlit (Latest Stable)
- **Runtime:** Python 3.12+
- **Backend Bridge:** LangGraph + Boto3 (AWS Bedrock Runtime)
- **Styling:** Streamlit built-in components + custom CSS injection for "Card" borders.

## 2. Architecture Principles
- **State-Driven Rendering:** The UI should re-render based on the current `AgentState`.
- **Non-Blocking Execution:** Use Streamlit's `st.status` or `st.spinner` during LLM invocations to prevent the UI from appearing frozen.
- **Asynchronous Streaming:** Utilize `app.stream()` to update the UI as each individual node (Compliance, Strategist) completes its task.

## 3. Security & Environment
- **Credential Management:** No AWS keys in the UI code. Must pull from `st.secrets` or local environment variables.
- **Persistence:** Utilize `MemorySaver` within the LangGraph compilation to ensure that a page refresh doesn't lose the agent's progress.

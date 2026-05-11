# UI Design Specification: Xpanse Agent Command Center

## 1. Overview
The UI is designed as a **Progressive Dashboard**. Instead of displaying all information at once, it unlocks sections sequentially as the LangGraph workflow progresses. The aesthetic is "Enterprise Dark Mode" with high-contrast accents for status alerts.

## 2. Layout Structure
- **Global Sidebar:** Fixed on the left. Contains configuration and system health.
- **Dynamic Main Canvas:** Occupies the center/right. Divided into three vertical stages representing the Agent Lifecycle.

## 3. Feature List
### A. The Sidebar (Control Panel)
- **Target Region:** Dropdown selector (Japan, Germany, UK, etc.).
- **Expansion Goal:** Multi-line text input for the specific business objective.
- **Primary CTA:** `[Launch Expansion Squad]` button (triggers the Graph).
- **System Status:** LED indicator showing `Bedrock Connection: Active`.

### B. Stage 1: Analysis & Strategy (Parallel View)
- **Compliance Card:** Displays a summary of legal findings (APPI/GDPR rules) with a checklist of verified constraints.
- **Strategy Card:** Displays market-specific insights, currency conversions, and cultural nuances.

### C. Stage 2: The Approval Gate (HITL)
- **Review Panel:** A high-visibility yellow-bordered container that appears only during an `interrupt`.
- **Feedback Input:** Text box for the user to provide "Refinement Instructions."
- **Dual Actions:**
    - `[Refine Plan]`: Sends feedback back to the Strategist.
    - `[Approve & Generate Code]`: Sets `is_approved=True` and triggers Stage 3.

### D. Stage 3: Technical Artifacts (The Output)
- **Code Explorer:** A tabbed interface displaying:
    - **Tab 1 (SQL):** Snowflake/Postgres table creation scripts.
    - **Tab 2 (Python):** AWS Lambda/Backend logic.
    - **Tab 3 (QA):** A report verifying code compliance with the Stage 1 findings.

# ⚡ Xpanse.ai — AI-Powered Marketing Campaign Intelligence Platform

Xpanse.ai is a multi-agent AI system that generates data-driven marketing campaign strategies and culturally-adapted content. Built on LangGraph with Amazon Bedrock (Nova Pro), it combines historical campaign analysis, live market research, and intelligent synthesis into an interactive command center.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Agent Pipeline Details](#agent-pipeline-details)
- [Human-in-the-Loop Workflow](#human-in-the-loop-workflow)
- [License](#license)

---

## Features

### 🎯 Mode 1: Campaign Strategy Engine

- **Performance Sentinel** — Mines historical campaign archives via AWS Bedrock Knowledge Bases (RAG) to identify winning and failing patterns with metric-based reasoning.
- **Strategic Seer** — Validates historical insights against live market data using Tavily web search; highlights conflicts between past patterns and current trends.
- **Campaign Architect** — Synthesizes a complete campaign strategy with budget allocation tables, Mermaid.js campaign flow diagrams, messaging frameworks, and constraint compliance checks.
- **Feedback Router** — LLM-powered intent classifier that routes human feedback to the correct agent for targeted re-generation.
- **Version History & Diff** — Tracks every strategy iteration with side-by-side diff views.

### 🌍 Mode 2: Content Transcreator (Market Mirror)

- **Cultural Researcher** — Researches local slang, purchasing psychology, taboos, and communication norms for a target market.
- **Content Drafter** — Transcreates (not translates) English marketing copy into culturally-resonant local content.
- **Cultural Critic** — Scores output on authenticity, emotional resonance, idiom usage, and friction points (1-10 scale). Auto-loops until quality ≥ 7/10.
- **Human Approval Gate** — Final human review before content is finalized.

### 🖥️ Streamlit Command Center UI

- Dual-mode interface with real-time agent progress visualization
- Interactive feedback loop with intelligent routing
- Strategy version history with diff comparison
- Visual pipeline flow graph with active/completed/pending states

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Campaign Strategy Pipeline                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  START → Performance Sentinel → Strategic Seer → Campaign Architect
│                                                       │
│                                              [INTERRUPT: Human Review]
│                                                       │
│                                              Feedback Router
│                                              ┌───┴───┐
│                                         (loop back)   END
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   Content Transcreator Pipeline                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  START → Cultural Researcher → Content Drafter → Cultural Critic
│                                       ↑               │
│                                       └── (score < 7) ┘
│                                              │
│                                       (score ≥ 7 or max loops)
│                                              │
│                                    [INTERRUPT: Human Approval]
│                                              │
│                                             END
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) (StateGraph with checkpointing) |
| LLM | Amazon Bedrock — Nova Pro v1 (Converse API) |
| Knowledge Bases | AWS Bedrock Knowledge Bases (Archive KB + Brand KB) |
| Web Search | [Tavily](https://tavily.com/) (live market research) |
| UI | [Streamlit](https://streamlit.io/) |
| AWS SDK | boto3 |
| Python | 3.14+ |
| Package Manager | [uv](https://docs.astral.sh/uv/) |

---

## Project Structure

```
Xpanse.ai/
├── src/
│   ├── main.py                 # CLI orchestrator (run_strategy, provide_feedback, approve_strategy)
│   ├── ui.py                   # Streamlit dual-mode Command Center UI
│   ├── tools.py                # Tavily web search tool wrapper
│   ├── agents/
│   │   └── prompts.py          # System prompts for all 7 agents
│   ├── graph/
│   │   ├── state.py            # TypedDict state definitions (AgentState, TranscreatorState)
│   │   ├── workflow.py         # Campaign Strategy LangGraph (4 nodes + router)
│   │   └── transcreator.py    # Content Transcreator LangGraph (3 nodes + auto-loop)
│   └── utils/
│       └── bedrock.py          # Amazon Bedrock Converse API wrapper
├── data/                       # Campaign archive data (Knowledge Base source)
├── specs/                      # Feature specifications
├── pyproject.toml              # Project metadata and dependencies
├── .env                        # Environment variables (not committed)
└── README.md
```

---

## Prerequisites

- **Python 3.14+**
- **AWS Account** with access to:
  - Amazon Bedrock (Nova Pro model enabled in `us-east-1`)
  - Bedrock Knowledge Bases (two KBs: Archive + Brand)
  - IAM credentials with `bedrock:InvokeModel` and `bedrock:Retrieve` permissions
- **Tavily API Key** — for live web search capabilities
- **uv** (recommended) — Python package manager

---

## Installation

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd Xpanse.ai
   ```

2. **Create a virtual environment and install dependencies:**

   ```bash
   uv venv
   uv sync
   ```

   Or with pip:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   # source .venv/bin/activate  # macOS/Linux
   pip install -e .
   ```

---

## Configuration

Create a `.env` file in the project root with the following variables:

```env
# Tavily — Live web search for market research
TAVILY_API_KEY=your_tavily_api_key

# AWS Bedrock Knowledge Base IDs
ARCHIVE_KB_ID=your_archive_knowledge_base_id
BRAND_KB_ID=your_brand_knowledge_base_id
```

**AWS Credentials** are resolved via the standard boto3 chain:
- Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- `~/.aws/credentials` file
- IAM instance role (if running on AWS)

The Bedrock model region defaults to `us-east-1`. To change it, update `AWS_REGION` in `src/utils/bedrock.py`.

---

## Usage

### Streamlit UI (Recommended)

```bash
streamlit run src/ui.py
```

This launches the **Xpanse.ai Command Center** with:
- Mode selector (Campaign Strategy / Content Transcreation)
- Input forms for campaign briefs or source content
- Real-time agent progress visualization
- Interactive feedback and approval workflow
- Strategy version history with diff views

### CLI Mode

```bash
python -m src.main
```

Or use the Python API directly:

```python
from src.main import run_strategy, provide_feedback, approve_strategy

# Start a campaign strategy pipeline
thread_id = run_strategy(
    campaign_aim="Increase Gen-Z enrollment by 15%",
    target_audience="Gen-Z consumers aged 18-25",
    budget=50000.0,
    duration="14 Days",
    constraints="No misleading claims. Must include unsubscribe option.",
    is_expansion=True,
    target_region="Japan",
)

# Provide feedback (routed intelligently)
provide_feedback(thread_id, "Research competitor trends in Japan market")

# Approve when satisfied
approve_strategy(thread_id)
```

---

## Agent Pipeline Details

### Campaign Strategy Pipeline

| Agent | Role | Data Source | Output |
|-------|------|-------------|--------|
| Performance Sentinel | Historical Analyst | Bedrock Knowledge Bases (RAG) | Historical DNA report with winning/failing patterns |
| Strategic Seer | Market Forecaster | Tavily Web Search | Market Pulse report with trend validation |
| Campaign Architect | Master Strategist | Sentinel + Seer outputs | Full strategy document with budget, flow, messaging |
| Feedback Router | Intent Classifier | Human feedback text | Routing decision (sentinel / seer / architect / end) |

### Content Transcreator Pipeline

| Agent | Role | Data Source | Output |
|-------|------|-------------|--------|
| Cultural Researcher | Cultural Intelligence | Tavily Web Search | Cultural Intelligence Brief (slang, taboos, triggers) |
| Content Drafter | Transcreation Specialist | Source content + Cultural Brief | Localized marketing copy with adaptation notes |
| Cultural Critic | Native Reviewer | Draft content | Quality score (1-10) with specific revision notes |

---

## Human-in-the-Loop Workflow

The platform uses LangGraph's `interrupt_after` mechanism for human oversight:

1. **Pipeline runs autonomously** through all agents.
2. **Pauses for human review** after the Campaign Architect (or after the Critic passes in Transcreator mode).
3. **Human provides feedback** — free-text input describing what to change.
4. **Feedback Router classifies intent** and routes to the responsible agent:
   - `"Research competitor trends"` → routes to **Strategic Seer**
   - `"Past campaign metrics were wrong"` → routes to **Performance Sentinel**
   - `"Change the budget allocation"` → routes to **Campaign Architect**
   - `"Looks good"` / `"Approve"` → routes to **END**
5. **Targeted agent re-runs** with the feedback context, producing an updated strategy.
6. **Loop repeats** until the human approves.

---

## License

This project is proprietary to Publicis Groupe.

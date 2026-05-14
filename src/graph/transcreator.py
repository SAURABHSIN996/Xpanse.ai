"""LangGraph — Market Mirror Content Transcreator.

Flow:
  START → cultural_researcher → content_drafter → cultural_critic → [conditional]
    │ score < 7 AND loops < max → content_drafter (auto-loop)
    │ score >= 7 OR loops >= max → [INTERRUPT for human approval] → END
"""

import logging
import os
import re
from datetime import datetime, timezone
from typing import Literal

import boto3
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from src.agents.prompts import (
    CONTENT_DRAFTER,
    CULTURAL_CRITIC,
    CULTURAL_RESEARCHER,
)
from src.graph.state import TranscreatorState
from src.tools import web_search_tool
from src.utils.bedrock import invoke_agent

load_dotenv()
logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _log(agent: str, status: str) -> dict:
    return {"agent": agent, "timestamp": _now(), "trigger": "auto", "status": status}


def _retrieve_brand_tone(campaign_context: str = "") -> str:
    """Retrieve brand tone from Brand KB if available."""
    brand_kb_id = os.getenv("BRAND_KB_ID", "")
    if not brand_kb_id:
        return ""
    try:
        region = os.getenv("AWS_REGION", "us-east-1")
        client = boto3.client("bedrock-agent-runtime", region_name=region)
        response = client.retrieve(
            knowledgeBaseId=brand_kb_id,
            retrievalQuery={"text": f"brand voice tone guidelines {campaign_context}"},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 3}},
        )
        results = []
        for item in response.get("retrievalResults", []):
            text = item.get("content", {}).get("text", "")
            if text:
                results.append(text)
        return "\n\n".join(results) if results else ""
    except Exception as e:
        logger.error("Brand KB retrieval error: %s", e)
        return ""


# ---------------------------------------------------------------------------
# Node 1: Cultural Researcher
# ---------------------------------------------------------------------------


def cultural_researcher_node(state: TranscreatorState) -> dict:
    """Research local culture, slang, taboos, and marketing norms."""
    target_market = state.get("target_market", "")
    source_content = state.get("source_content", "")

    logger.info("Cultural Researcher — market: %s", target_market)

    log = list(state.get("execution_log", []))
    log.append(_log("researcher", "running"))

    # Tavily searches
    search_queries = [
        f"marketing communication style {target_market} cultural norms 2025",
        f"consumer purchasing behavior {target_market} what motivates buying",
        f"marketing taboos {target_market} things to avoid advertising",
    ]

    research_data = []
    for q in search_queries:
        results = web_search_tool(q, max_results=3)
        for r in results:
            if r.get("content"):
                research_data.append(f"[{r.get('title', '')}]: {r['content']}")

    research_text = "\n\n".join(research_data) or "No research data retrieved."

    # Get brand tone from KB
    brand_tone = state.get("brand_tone", "") or _retrieve_brand_tone(source_content[:200])

    # Build prompt (replace placeholder)
    prompt = CULTURAL_RESEARCHER.replace("{target_market}", target_market)

    user_content = (
        f"Target Market: {target_market}\n"
        f"Source Content Preview: {source_content[:500]}\n"
        f"\n=== WEB RESEARCH RESULTS ===\n{research_text}\n"
    )
    if brand_tone:
        user_content += f"\n=== BRAND TONE GUIDELINES ===\n{brand_tone}\n"

    result = invoke_agent(prompt, user_content)

    log.append(_log("researcher", "complete"))

    return {
        "cultural_research": result,
        "research_queries": search_queries,
        "brand_tone": brand_tone,
        "active_node": "researcher",
        "execution_log": log,
    }


# ---------------------------------------------------------------------------
# Node 2: Content Drafter
# ---------------------------------------------------------------------------


def content_drafter_node(state: TranscreatorState) -> dict:
    """Transcreate the source content using cultural research."""
    source_content = state.get("source_content", "")
    target_market = state.get("target_market", "")
    cultural_research = state.get("cultural_research", "")
    brand_tone = state.get("brand_tone", "")
    critic_feedback = state.get("critic_feedback", "")
    loops = state.get("reflection_loops", 0)

    logger.info("Content Drafter — loop %d", loops)

    log = list(state.get("execution_log", []))
    log.append(_log("drafter", f"running (loop {loops + 1})"))

    # Save previous draft for diff
    previous_draft = state.get("draft_content", "")

    user_content = (
        f"Target Market: {target_market}\n"
        f"\n=== SOURCE CONTENT (English Original) ===\n{source_content}\n"
        f"\n=== CULTURAL INTELLIGENCE BRIEF ===\n{cultural_research}\n"
    )
    if brand_tone:
        user_content += f"\n=== BRAND TONE ===\n{brand_tone}\n"
    if critic_feedback:
        user_content += (
            f"\n=== CRITIC FEEDBACK (MUST ADDRESS EVERY POINT) ===\n"
            f"{critic_feedback}\n"
        )

    result = invoke_agent(CONTENT_DRAFTER, user_content)

    # Track versions
    versions = list(state.get("draft_versions", []))
    versions.append({
        "version": str(loops + 1),
        "content": result,
        "critic_feedback": critic_feedback,
    })

    log.append(_log("drafter", f"complete (loop {loops + 1})"))

    return {
        "draft_content": result,
        "previous_draft": previous_draft,
        "draft_versions": versions,
        "reflection_loops": loops + 1,
        "active_node": "drafter",
        "execution_log": log,
    }


# ---------------------------------------------------------------------------
# Node 3: Cultural Critic
# ---------------------------------------------------------------------------


def cultural_critic_node(state: TranscreatorState) -> dict:
    """Review the draft and score it. Provide specific fixes if score < 7."""
    draft_content = state.get("draft_content", "")
    target_market = state.get("target_market", "")
    cultural_research = state.get("cultural_research", "")

    logger.info("Cultural Critic — reviewing draft")

    log = list(state.get("execution_log", []))
    log.append(_log("critic", "running"))

    prompt = CULTURAL_CRITIC.replace("{target_market}", target_market)

    user_content = (
        f"Target Market: {target_market}\n"
        f"\n=== DRAFT TO REVIEW ===\n{draft_content}\n"
        f"\n=== CULTURAL CONTEXT (for reference) ===\n{cultural_research[:1000]}\n"
    )

    result = invoke_agent(prompt, user_content)

    # Parse score from output
    score = _parse_critic_score(result)

    log.append(_log("critic", f"complete (score: {score}/10)"))

    return {
        "critic_score": score,
        "critic_feedback": result if score < 7 else "",
        "active_node": "critic",
        "execution_log": log,
    }


def _parse_critic_score(text: str) -> int:
    """Extract the overall score from critic output."""
    # Look for "OVERALL: X/10"
    match = re.search(r"OVERALL[:\s]*(\d+)\s*/\s*10", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    # Fallback: look for any X/10 pattern
    scores = re.findall(r"(\d+)\s*/\s*10", text)
    if scores:
        nums = [int(s) for s in scores]
        return round(sum(nums) / len(nums))
    return 5  # default middle score


# ---------------------------------------------------------------------------
# Conditional routing after critic
# ---------------------------------------------------------------------------


def critic_router(state: TranscreatorState) -> Literal["content_drafter", "__end__"]:
    """Route based on critic score and loop count."""
    score = state.get("critic_score", 0)
    loops = state.get("reflection_loops", 0)
    max_loops = state.get("max_loops", 3)

    if score >= 7 or loops >= max_loops:
        logger.info("Critic passed (score=%d, loops=%d) — proceeding to human review", score, loops)
        return "__end__"

    logger.info("Critic failed (score=%d, loops=%d) — looping back to drafter", score, loops)
    return "content_drafter"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_transcreator_graph(checkpointer=None):
    """Build the Market Mirror transcreation graph.

    Topology:
      START → researcher → drafter → critic → [conditional]
        │ score < 7 AND loops < max → drafter (auto-loop, no interrupt)
        │ score >= 7 OR loops >= max → human_review → END

    A 'human_review' node acts as the interrupt point — it only runs
    when the critic passes, and the interrupt fires before it.
    """
    graph = StateGraph(TranscreatorState)

    graph.add_node("cultural_researcher", cultural_researcher_node)
    graph.add_node("content_drafter", content_drafter_node)
    graph.add_node("cultural_critic", cultural_critic_node)
    graph.add_node("human_review", _human_review_node)

    graph.add_edge(START, "cultural_researcher")
    graph.add_edge("cultural_researcher", "content_drafter")
    graph.add_edge("content_drafter", "cultural_critic")

    graph.add_conditional_edges(
        "cultural_critic",
        critic_router,
        {
            "content_drafter": "content_drafter",
            "__end__": "human_review",
        },
    )

    graph.add_edge("human_review", END)

    # Interrupt BEFORE human_review — this pauses only when critic passes
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"],
    )


def _human_review_node(state: TranscreatorState) -> dict:
    """Passthrough node that marks the content as ready for human approval."""
    return {"is_approved": True}

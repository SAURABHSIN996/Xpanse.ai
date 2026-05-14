"""LangGraph StateGraph — Xpanse V2.0 with execution logging, version history, and diff.

Flow: START → sentinel → seer → architect → [INTERRUPT] → router → (loop or END)
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Literal

import boto3
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from src.agents.prompts import (
    CAMPAIGN_ARCHITECT,
    FEEDBACK_ROUTER_PROMPT,
    PERFORMANCE_SENTINEL,
    STRATEGIC_SEER,
)
from src.graph.state import AgentState
from src.tools import web_search_tool
from src.utils.bedrock import invoke_agent

load_dotenv()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _log_entry(agent: str, trigger: str, status: str) -> dict:
    return {"agent": agent, "timestamp": _now(), "trigger": trigger, "status": status}


def _retrieve_from_kb(kb_id: str, query: str, max_results: int = 5) -> list[dict]:
    if not kb_id:
        return []
    try:
        region = os.getenv("AWS_REGION", "us-east-1")
        client = boto3.client("bedrock-agent-runtime", region_name=region)
        response = client.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": max_results}},
        )
        results = []
        for item in response.get("retrievalResults", []):
            content = item.get("content", {}).get("text", "")
            source = item.get("location", {}).get("s3Location", {}).get("uri", "KB Document")
            results.append({"content": content, "source": source, "score": item.get("score", 0.0)})
        return results
    except Exception as e:
        logger.error("KB retrieval error (kb_id=%s): %s", kb_id, e)
        return []


def _parse_campaign_metrics(content: str) -> dict:
    metrics = {}
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            for key in ("success_score", "target", "performance"):
                if key in data:
                    val = data[key]
                    metrics[key] = json.dumps(val) if isinstance(val, dict) else str(val)
            return metrics
    except (json.JSONDecodeError, TypeError):
        pass
    for key in ("success_score", "target", "performance"):
        m = re.search(rf'"?{key}"?\s*[:=]\s*"?([^"\n,}}]+)"?', content, re.IGNORECASE)
        if m:
            metrics[key] = m.group(1).strip()
    return metrics


# ---------------------------------------------------------------------------
# Node 1: Performance Sentinel
# ---------------------------------------------------------------------------


def performance_sentinel_node(state: AgentState) -> dict:
    campaign_aim = state.get("campaign_aim", "")
    audience = state.get("target_audience", "")
    region = state.get("target_region") or "Global"
    is_expansion = state.get("is_expansion", False)
    trigger = "feedback" if state.get("human_feedback") else "initial"

    log = list(state.get("execution_log", []))
    log.append(_log_entry("sentinel", trigger, "running"))

    brand_kb_id = os.getenv("BRAND_KB_ID", "")
    archive_kb_id = os.getenv("ARCHIVE_KB_ID", "")

    query_parts = [campaign_aim]
    if audience:
        query_parts.append(f"audience: {audience}")
    if is_expansion and region:
        query_parts.append(f"region: {region}")
    query = " | ".join(query_parts)

    brand_results = _retrieve_from_kb(brand_kb_id, f"brand guidelines {campaign_aim}", max_results=3)
    archive_results = _retrieve_from_kb(archive_kb_id, query, max_results=8)

    all_metrics = [_parse_campaign_metrics(r["content"]) for r in archive_results]
    all_metrics = [m for m in all_metrics if m]

    archive_metrics = {}
    if all_metrics:
        scores = [float(m["success_score"]) for m in all_metrics if "success_score" in m]
        if scores:
            archive_metrics["avg_success_score"] = f"{sum(scores)/len(scores):.1f}"
            archive_metrics["campaigns_analyzed"] = str(len(scores))

    citations = list({r["source"] for r in archive_results + brand_results if r.get("source")})

    brand_context = "\n\n".join(f"[Brand: {r['source']}]\n{r['content']}" for r in brand_results) or "None"
    archive_context = "\n\n---\n\n".join(f"[Archive: {r['source']}]\n{r['content']}" for r in archive_results) or "None"

    user_content = (
        f"Campaign Objective: {campaign_aim}\nTarget Audience: {audience}\nRegion: {region}\n"
        f"\n=== BRAND DATA ===\n{brand_context}\n\n=== ARCHIVE DATA ===\n{archive_context}"
    )
    if state.get("human_feedback"):
        user_content += f"\n\n=== HUMAN FEEDBACK ===\n{state['human_feedback']}\nAddress this feedback."

    result = invoke_agent(PERFORMANCE_SENTINEL, user_content)

    # Extract recommendations section for downstream agents
    sentinel_recs = ""
    if "STRATEGIC RECOMMENDATIONS" in result:
        idx = result.index("STRATEGIC RECOMMENDATIONS")
        sentinel_recs = result[idx:]
    elif "HISTORICAL DNA SUMMARY" in result:
        idx = result.index("HISTORICAL DNA SUMMARY")
        sentinel_recs = result[idx:]

    log.append(_log_entry("sentinel", trigger, "complete"))

    return {
        "archive_report": result,
        "historical_dna": result,
        "archive_metrics": archive_metrics,
        "citations": citations,
        "analysis_data": result,
        "sentinel_recommendations": sentinel_recs,
        "active_node": "sentinel",
        "processing_phase": "analysis",
        "execution_log": log,
    }


# ---------------------------------------------------------------------------
# Node 2: Strategic Seer
# ---------------------------------------------------------------------------


def strategic_seer_node(state: AgentState) -> dict:
    campaign_aim = state.get("campaign_aim", "")
    audience = state.get("target_audience", "")
    is_expansion = state.get("is_expansion", False)
    region = state.get("target_region") or "General Market"
    trigger = "feedback" if state.get("human_feedback") else "initial"

    log = list(state.get("execution_log", []))
    log.append(_log_entry("seer", trigger, "running"))

    if is_expansion and region != "General Market":
        search_queries = [
            f"marketing trends {region} 2025 consumer engagement",
            f"{campaign_aim} campaigns {region} best practices",
            f"consumer behavior {region} {audience} preferences",
        ]
    else:
        search_queries = [
            f"{campaign_aim} marketing trends 2025 high engagement",
            f"best practices {campaign_aim} {audience}",
            f"competitor strategies {campaign_aim} current trends",
        ]

    market_data = []
    for q in search_queries:
        results = web_search_tool(q, max_results=3)
        for r in results:
            if r.get("content"):
                market_data.append(f"[{r.get('title', 'N/A')}]: {r['content']}")

    market_text = "\n\n".join(market_data) or "No market data retrieved."

    user_content = (
        f"Campaign Objective: {campaign_aim}\nAudience: {audience}\n"
        f"Expansion: {'YES — ' + region if is_expansion else 'NO'}\n"
        f"\n=== HISTORICAL DNA ===\n{state.get('historical_dna', 'N/A')}\n"
        f"\n=== LIVE MARKET RESEARCH ===\n{market_text}"
    )
    if state.get("human_feedback"):
        user_content += f"\n\n=== HUMAN FEEDBACK ===\n{state['human_feedback']}\nAddress this feedback."

    result = invoke_agent(STRATEGIC_SEER, user_content)

    # Extract recommendations for Architect
    seer_recs = ""
    if "RECOMMENDATIONS FOR ARCHITECT" in result:
        idx = result.index("RECOMMENDATIONS FOR ARCHITECT")
        seer_recs = result[idx:]
    elif "RECOMMENDED APPROACH" in result:
        idx = result.index("RECOMMENDED APPROACH")
        seer_recs = result[idx:]

    log.append(_log_entry("seer", trigger, "complete"))

    return {
        "market_pulse": result,
        "seer_report": result,
        "research_data": result,
        "tavily_queries": search_queries,
        "seer_recommendations": seer_recs,
        "active_node": "seer",
        "processing_phase": "scouting",
        "execution_log": log,
    }


# ---------------------------------------------------------------------------
# Node 3: Campaign Architect
# ---------------------------------------------------------------------------


def campaign_architect_node(state: AgentState) -> dict:
    campaign_aim = state.get("campaign_aim", "")
    audience = state.get("target_audience", "")
    budget = state.get("budget", 0.0)
    duration = state.get("duration", "")
    constraints = state.get("constraints", "")
    is_expansion = state.get("is_expansion", False)
    region = state.get("target_region") or "Home Market"
    trigger = "feedback" if state.get("human_feedback") else "initial"

    log = list(state.get("execution_log", []))
    log.append(_log_entry("architect", trigger, "running"))

    # Save previous strategy for diff
    previous_strategy = state.get("strategy_document", "")

    user_content = (
        f"Campaign Objective: {campaign_aim}\nAudience: {audience}\n"
        f"Budget: ${budget:,.2f}\nDuration: {duration}\n"
        f"Expansion: {'YES — ' + region if is_expansion else 'NO'}\n"
    )
    if constraints:
        user_content += f"Constraints: {constraints}\n"
    user_content += (
        f"\n=== HISTORICAL DNA ===\n{state.get('historical_dna', 'N/A')}\n"
        f"\n=== MARKET PULSE ===\n{state.get('market_pulse', 'N/A')}\n"
    )
    if state.get("human_feedback"):
        user_content += (
            f"\n\n=== HUMAN FEEDBACK ===\n{state['human_feedback']}\n"
            f"Incorporate this feedback and explain what changed."
        )

    result = invoke_agent(CAMPAIGN_ARCHITECT, user_content)

    # Extract mermaid
    strategy_flow = ""
    if "```mermaid" in result:
        try:
            s = result.index("```mermaid") + len("```mermaid")
            e = result.index("```", s)
            strategy_flow = result[s:e].strip()
        except ValueError:
            pass

    # Extract budget table
    budget_table = ""
    lines = result.split("\n")
    table_lines = []
    in_table = False
    for line in lines:
        if "|" in line and ("Category" in line or "---" in line or in_table):
            in_table = True
            table_lines.append(line)
        elif in_table and "|" not in line:
            break
    if table_lines:
        budget_table = "\n".join(table_lines)

    loop_count = state.get("loop_count", 0) + 1

    # Version history
    versions = list(state.get("strategy_versions", []))
    versions.append({
        "version": str(loop_count),
        "document": result,
        "feedback": state.get("human_feedback", ""),
        "target": state.get("target_node", "initial"),
    })

    # Feedback impact summary
    feedback_impact = ""
    if previous_strategy and state.get("human_feedback"):
        # Quick heuristic: count changed lines
        old_lines = set(previous_strategy.split("\n"))
        new_lines = set(result.split("\n"))
        added = len(new_lines - old_lines)
        removed = len(old_lines - new_lines)
        feedback_impact = f"Strategy updated: +{added} lines added, -{removed} lines removed after feedback."

    log.append(_log_entry("architect", trigger, "complete"))

    return {
        "strategy_document": result,
        "strategy_flow": strategy_flow,
        "budget_table": budget_table,
        "previous_strategy": previous_strategy,
        "loop_count": loop_count,
        "strategy_versions": versions,
        "feedback_impact": feedback_impact,
        "active_node": "architect",
        "processing_phase": "synthesis",
        "execution_log": log,
    }


# ---------------------------------------------------------------------------
# Node 4: Feedback Router
# ---------------------------------------------------------------------------


def feedback_router_node(state: AgentState) -> dict:
    feedback = state.get("human_feedback", "")

    log = list(state.get("execution_log", []))
    log.append(_log_entry("router", "feedback", "running"))

    feedback_history = list(state.get("feedback_history", []))
    if feedback:
        feedback_history.append(feedback)

    if not feedback.strip():
        log.append(_log_entry("router", "feedback", "complete"))
        return {
            "target_node": "end",
            "router_reasoning": "No feedback provided — approving.",
            "feedback_history": feedback_history,
            "processing_phase": "complete",
            "active_node": "router",
            "execution_log": log,
        }

    # LLM classification
    user_content = f"Human feedback to analyze:\n\"{feedback}\""
    try:
        result = invoke_agent(FEEDBACK_ROUTER_PROMPT, user_content)
        decision = result.strip().lower().split()[0] if result.strip() else "architect"
        valid = {"sentinel", "seer", "architect", "end"}
        if decision not in valid:
            decision = _keyword_fallback(feedback)
    except Exception:
        decision = _keyword_fallback(feedback)

    # Build reasoning
    reasoning_map = {
        "sentinel": f"Detected historical/archive concern → re-running Sentinel",
        "seer": f"Detected market/trend concern → re-running Seer",
        "architect": f"Detected strategy/structure concern → re-running Architect",
        "end": f"User approved the strategy",
    }
    reasoning = reasoning_map.get(decision, "Routing to Architect by default")

    # Clear stale data on loop-back
    updates: dict = {
        "target_node": decision,
        "router_reasoning": reasoning,
        "feedback_history": feedback_history,
        "active_node": "router",
        "processing_phase": "routing",
        "execution_log": log,
    }
    if decision == "sentinel":
        updates["historical_dna"] = ""
        updates["analysis_data"] = ""
    elif decision == "seer":
        updates["market_pulse"] = ""
        updates["research_data"] = ""

    log.append(_log_entry("router", "feedback", f"complete → {decision}"))
    updates["execution_log"] = log

    return updates


def _keyword_fallback(feedback: str) -> str:
    text = feedback.lower()
    for kw in ("approve", "looks good", "perfect", "accept", "great"):
        if kw in text:
            return "end"
    for kw in ("past", "history", "previous", "metrics", "archive", "historical"):
        if kw in text:
            return "sentinel"
    for kw in ("market", "trends", "competitors", "regions", "research", "web search", "search", "look up", "find out", "investigate", "scout"):
        if kw in text:
            return "seer"
    return "architect"


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def route_after_feedback(state: AgentState) -> Literal["performance_sentinel", "strategic_seer", "campaign_architect", "__end__"]:
    target = state.get("target_node", "end")
    return {
        "sentinel": "performance_sentinel",
        "seer": "strategic_seer",
        "architect": "campaign_architect",
    }.get(target, "__end__")


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def build_graph(checkpointer=None):
    graph = StateGraph(AgentState)

    graph.add_node("performance_sentinel", performance_sentinel_node)
    graph.add_node("strategic_seer", strategic_seer_node)
    graph.add_node("campaign_architect", campaign_architect_node)
    graph.add_node("feedback_router", feedback_router_node)

    graph.add_edge(START, "performance_sentinel")
    graph.add_edge("performance_sentinel", "strategic_seer")
    graph.add_edge("strategic_seer", "campaign_architect")
    graph.add_edge("campaign_architect", "feedback_router")

    graph.add_conditional_edges(
        "feedback_router",
        route_after_feedback,
        {
            "performance_sentinel": "performance_sentinel",
            "strategic_seer": "strategic_seer",
            "campaign_architect": "campaign_architect",
            "__end__": END,
        },
    )

    return graph.compile(checkpointer=checkpointer, interrupt_after=["campaign_architect"])

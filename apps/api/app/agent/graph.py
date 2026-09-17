"""LangGraph 状态机装配：发帖事件流水线（§3.1）。"""
import logging

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import generate_node, guardrail_node, judge_node, postprocess_node, retrieve_node, route_node
from app.agent.state import PipelineState

logger = logging.getLogger(__name__)


def _route_after_guardrail(state: PipelineState) -> str:
    if state.get("decision") in ("hidden", "review"):
        return END
    return "route"


def _route_after_route(state: PipelineState) -> str:
    if not state.get("should_reply"):
        return END
    return "retrieve"


def _route_after_judge(state: PipelineState) -> str:
    if state.get("decision") == "no_evidence":
        return END
    return "generate"


def build_graph() -> StateGraph:
    g = StateGraph(PipelineState)
    g.add_node("guardrail", guardrail_node)
    g.add_node("route", route_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("judge", judge_node)
    g.add_node("generate", generate_node)
    g.add_node("postprocess", postprocess_node)

    g.add_edge(START, "guardrail")
    g.add_conditional_edges("guardrail", _route_after_guardrail, {"route": "route", END: END})
    g.add_conditional_edges("route", _route_after_route, {"retrieve": "retrieve", END: END})
    g.add_edge("retrieve", "judge")
    g.add_conditional_edges("judge", _route_after_judge, {"generate": "generate", END: END})
    g.add_edge("generate", "postprocess")
    g.add_edge("postprocess", END)
    return g

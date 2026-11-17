"""Agent graph.

    START -> preprocess -> router --+--> clarify ------------------------------> END
                                    |
                                    +--> skill node(s) --(sequential)--> skill node
                                                |                            |
                                                +-------> compose <----------+--> END

Skill nodes are generated from the registry. The router's conditional edge fans out with `Send`
(parallel) or starts a chain (sequential); see `nodes/execute.py`.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from skill_agent.config import Settings
from skill_agent.llm import LLMClient
from skill_agent.nodes.execute import CLARIFY, COMPOSE, Scheduler, SkillInput, make_skill_node
from skill_agent.nodes.preprocess import preprocess
from skill_agent.nodes.respond import Composer, clarify
from skill_agent.nodes.router import Router
from skill_agent.state import AgentState


def build_graph(
    llm: LLMClient, settings: Settings, router: Router
) -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    registry = router.registry
    skills = registry.instantiate(llm, settings)
    scheduler = Scheduler(settings)

    graph = StateGraph(AgentState)
    graph.add_node("preprocess", preprocess)
    graph.add_node("router", router)
    graph.add_node(CLARIFY, clarify)
    graph.add_node(COMPOSE, Composer(registry))
    for name, skill in skills.items():
        # Skill nodes receive a `SkillInput` sent by the scheduler, not the whole agent state.
        graph.add_node(name, make_skill_node(skill), input_schema=SkillInput)  # type: ignore[arg-type]

    graph.add_edge(START, "preprocess")
    graph.add_edge("preprocess", "router")
    graph.add_conditional_edges("router", scheduler.dispatch, [*skills, CLARIFY])
    for name in skills:
        graph.add_conditional_edges(name, scheduler.after_skill, [*skills, COMPOSE])
    graph.add_edge(CLARIFY, END)
    graph.add_edge(COMPOSE, END)
    return graph.compile()

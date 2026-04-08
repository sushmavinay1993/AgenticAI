from langgraph.graph import StateGraph

def build_graph(agentA, agentB, agentC):

    graph = StateGraph(dict)

    graph.add_node("agent_a", agentA.run)
    graph.add_node("agent_b", agentB.run)
    graph.add_node("agent_c", agentC.run)

    graph.set_entry_point("agent_a")

    graph.add_edge("agent_a", "agent_b")
    graph.add_edge("agent_b", "agent_c")

    def decision(state):
        return "agent_b" if state["status"] == "FAIL" else "end"

    graph.add_conditional_edges(
        "agent_c",
        decision,
        {
            "agent_b": "agent_b",
            "end": None
        }
    )

    return graph.compile()
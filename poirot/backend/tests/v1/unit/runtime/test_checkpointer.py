from langgraph.checkpoint.memory import InMemorySaver

from poirot.backend.agents.runtime.checkpointer import (
    get_checkpointer,
    reset_checkpointer,
)


def test_get_checkpointer_returns_singleton() -> None:
    reset_checkpointer()
    cp1 = get_checkpointer()
    cp2 = get_checkpointer()
    assert cp1 is cp2


def test_get_checkpointer_returns_in_memory_saver() -> None:
    reset_checkpointer()
    cp = get_checkpointer()
    assert isinstance(cp, InMemorySaver)


def test_reset_checkpointer_creates_new_instance() -> None:
    reset_checkpointer()
    cp1 = get_checkpointer()
    reset_checkpointer()
    cp2 = get_checkpointer()
    assert cp1 is not cp2


def test_checkpoint_roundtrips_application_types_without_unregistered_warnings(caplog):
    import json
    from dataclasses import asdict
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from poirot.backend.agents.state.types import (
        AgentError, Artifact, Citation, IntentState, Observation, PlanStep,
        ReflectionItem, ResearchPlan, Source,
    )
    from poirot.backend.agents.multiagent.types import ArtifactRef

    state = {
        "messages": [HumanMessage(content="Q"), AIMessage(content="A"), ToolMessage(content="failed", status="error", tool_call_id="t1")],
        "intent": IntentState("research", "light", "explain"),
        "plan": ResearchPlan("p1", "explain", (PlanStep("step-1", "compare"),)),
        "observations": [Observation("obs-1", None, "evidence")],
        "sources": [Source("src-1", "https://example.test")],
        "citations": [Citation("c1", "src-1", "quote", "claim")],
        "artifacts": [Artifact("a1", "report", "Title", "report.md")],
        "reflection_items": [ReflectionItem("r1", "run", "gap", "why")],
        "errors": [AgentError("err-1", "tool", "failed")],
        "orchestration": {"specialist_artifacts": [ArtifactRef(path="result.md", artifact_type="report", specialist_name="subagent")]},
    }
    reset_checkpointer()
    try:
        serializer = get_checkpointer().serde
        restored = serializer.loads_typed(serializer.dumps_typed(state))
        assert restored["messages"] == state["messages"]
        # Msgpack arrays may restore tuple fields as lists; check type and values
        # without claiming tuple-preserving serialization.
        for key in state.keys() - {"messages"}:
            assert json.dumps(restored[key], default=asdict) == json.dumps(state[key], default=asdict)
        assert isinstance(restored["plan"].steps[0], PlanStep)
        assert isinstance(restored["observations"][0], Observation)
        assert isinstance(restored["errors"][0], AgentError)
        assert isinstance(restored["orchestration"]["specialist_artifacts"][0], ArtifactRef)
        assert "unregistered type" not in caplog.text
        assert "Blocked deserialization" not in caplog.text
    finally:
        reset_checkpointer()

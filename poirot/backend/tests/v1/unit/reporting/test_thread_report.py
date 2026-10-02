"""generate_report_from_thread 测试：渠道无关报告生成服务。"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage


def _fake_runtime(tmp_path: Path, *, state: dict, save_artifact: bool = True) -> SimpleNamespace:
    """构造满足 _ReportRuntime Protocol 的 fake runtime。"""
    snapshot = SimpleNamespace(values=state)
    graph = SimpleNamespace(get_state=lambda config: snapshot)
    reporter = SimpleNamespace(
        generate_report=lambda s, run_context=None: SimpleNamespace(final_report="# 报告\n正文"),
    )
    artifact_store = SimpleNamespace(
        save_artifact=lambda content, output_dir, title, filename, metadata: SimpleNamespace(
            path=str(Path(output_dir) / filename),
        ),
    )
    registry = SimpleNamespace(get_reporter=lambda: reporter, get_artifact_store=lambda: artifact_store)
    config = SimpleNamespace(reporting=SimpleNamespace(save_artifact=save_artifact))
    return SimpleNamespace(
        leader_agent=SimpleNamespace(graph=graph),
        thread_id="thread-test",
        capability_registry=registry,
        thread_dir=tmp_path,
        config=config,
    )


def test_generate_report_from_thread_returns_final_report(tmp_path) -> None:
    runtime = _fake_runtime(tmp_path, state={"observations": [{"content": "obs1"}]})
    from poirot.backend.agents.reporting import generate_report_from_thread

    result = generate_report_from_thread(runtime=runtime)
    assert result.final_report == "# 报告\n正文"


def test_generate_report_from_thread_saves_artifact(tmp_path) -> None:
    runtime = _fake_runtime(tmp_path, state={"observations": []})
    from poirot.backend.agents.reporting import generate_report_from_thread

    result = generate_report_from_thread(runtime=runtime)
    assert result.artifact_path is not None
    assert result.artifact_path.endswith("report.md")


def test_generate_report_from_thread_no_artifact_when_disabled(tmp_path) -> None:
    runtime = _fake_runtime(tmp_path, state={"observations": []}, save_artifact=False)
    from poirot.backend.agents.reporting import generate_report_from_thread

    result = generate_report_from_thread(runtime=runtime)
    assert result.artifact_path is None


def test_generate_report_from_thread_topic_overrides_research_question(tmp_path) -> None:
    runtime = _fake_runtime(tmp_path, state={"research_question": "原问题"})
    captured = {}
    runtime.capability_registry.get_reporter = lambda: SimpleNamespace(
        generate_report=lambda s, run_context=None: (
            captured.update({"rq": s.get("research_question")}),
            SimpleNamespace(final_report="x"),
        )[1],
    )
    from poirot.backend.agents.reporting import generate_report_from_thread

    generate_report_from_thread(runtime=runtime, topic="自定义主题")
    assert captured["rq"] == "自定义主题"


def test_generate_report_from_thread_empty_state_still_works(tmp_path) -> None:
    """无 checkpoint（snapshot.values 空）→ state 空 dict → reporter fallback。"""
    runtime = _fake_runtime(tmp_path, state={})
    from poirot.backend.agents.reporting import generate_report_from_thread

    result = generate_report_from_thread(runtime=runtime)
    assert result.final_report == "# 报告\n正文"


def test_generate_report_from_thread_none_snapshot(tmp_path) -> None:
    """graph.get_state 返回 None（无 checkpoint）→ state 空。"""
    runtime = _fake_runtime(tmp_path, state={})
    runtime.leader_agent.graph.get_state = lambda config: None
    from poirot.backend.agents.reporting import generate_report_from_thread

    result = generate_report_from_thread(runtime=runtime)
    assert result.final_report  # 非 None（reporter fallback）


@pytest.mark.parametrize("old_report", [None, "Old research report"])
def test_manual_report_saves_latest_answer_despite_old_evidence(tmp_path, old_report):
    from poirot.backend.agents.artifacts.local_store import LocalArtifactStore
    from poirot.backend.agents.reporting import generate_report_from_thread
    from poirot.backend.agents.reporting.markdown_reporter import MarkdownReporter
    from poirot.backend.agents.state.types import Observation

    answer = "## BM25 与向量检索\n\n这是一篇完整的比较短文。"
    state = {
        "messages": [HumanMessage(content="整理短文"), AIMessage(content=answer)],
        "observations": [Observation("obs-1", None, '{"error": "Search failed: No results found."}')],
        "final_report": old_report,
    }
    runtime = _fake_runtime(tmp_path, state=state)
    runtime.capability_registry.get_reporter = lambda: MarkdownReporter()
    runtime.capability_registry.get_artifact_store = lambda: LocalArtifactStore()

    result = generate_report_from_thread(runtime, topic="检索方案比较")
    saved = Path(result.artifact_path).read_text(encoding="utf-8")
    assert answer in saved
    assert "检索方案比较" in saved
    assert "Search failed" not in saved
    assert "Old research report" not in saved
    assert state["final_report"] == old_report  # export does not mutate checkpoint state


def test_manual_report_does_not_export_a_tool_call_as_an_answer(tmp_path):
    from poirot.backend.agents.reporting import generate_report_from_thread
    from poirot.backend.agents.reporting.markdown_reporter import MarkdownReporter

    runtime = _fake_runtime(tmp_path, state={"messages": [
        AIMessage(content="A complete answer"),
        AIMessage(content="Let me search", tool_calls=[{"id": "t1", "name": "web_search", "args": {}}]),
    ]})
    runtime.capability_registry.get_reporter = lambda: MarkdownReporter()
    result = generate_report_from_thread(runtime)
    assert "A complete answer" in result.final_report
    assert "Let me search" not in result.final_report

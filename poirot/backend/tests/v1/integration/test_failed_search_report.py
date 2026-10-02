"""Offline regression for failed search -> follow-up -> manual report export."""

import asyncio
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from rich.console import Console

from poirot.backend.agents.artifacts.local_store import LocalArtifactStore
from poirot.backend.agents.capabilities.registry import CapabilityRegistry
from poirot.backend.agents.config.loader import load_config
from poirot.backend.agents.reporting.markdown_reporter import MarkdownReporter
from poirot.backend.agents.reporting.thread_report import generate_report_from_thread
from poirot.backend.agents.runtime.checkpointer import reset_checkpointer
from poirot.backend.app.bootstrap import _assemble_leader
from poirot.backend.app.cli.stream_handler import StreamRenderer
from poirot.backend.app.services.stream_service import PoirotStreamClient


class _ToolModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def test_failed_search_followup_exports_latest_answer(tmp_path, monkeypatch, caplog):
    import ddgs

    class FailedSearch:
        def text(self, *args, **kwargs):
            raise RuntimeError("No results found.")

    monkeypatch.setattr(ddgs, "DDGS", lambda **kwargs: FailedSearch())
    article = "# Retrieval comparison\n\nBM25 matches terms; embeddings compare representations."
    model = _ToolModel(responses=[
        AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "BM25"}, "id": "search-1"}]),
        AIMessage(content="Search failed. Based on general knowledge, BM25 uses lexical matching."),
        AIMessage(content=article),
    ])
    registry = CapabilityRegistry(
        models={"researcher": model, "reporter": model}, tools={},
        reporter=MarkdownReporter(), artifact_store=LocalArtifactStore(),
    )
    config = load_config(expert_mode=False, cli_overrides={"logs_root": str(tmp_path)})
    reset_checkpointer()
    try:
        leader = _assemble_leader(config, registry)
        stream_config = {"configurable": {"thread_id": "failed-search-report", "expert_mode": False}}

        async def run():
            first = [event async for event in PoirotStreamClient(leader.graph, stream_config).stream("Explain retrieval")]
            second = [event async for event in PoirotStreamClient(leader.graph, stream_config).stream("Write a complete article")]
            return first, second

        first, second = asyncio.run(run())
        tool_events = [event for event in first if event["type"] == "tool_end"]
        assert len(tool_events) == 1
        assert tool_events[0]["tool_status"] == "error"
        assert "".join(event["content"] for event in second if event["type"] == "answer") == article
        state = leader.graph.get_state(stream_config).values
        assert not state.get("observations")
        assert not state.get("sources")
        assert state["errors"][0].kind == "failure"

        output = StringIO()
        renderer = StreamRenderer(Console(file=output, width=100))
        for event in first:
            renderer.render(event)
        assert "✗ web_search" in output.getvalue()
        assert "✓ web_search" not in output.getvalue()

        runtime = SimpleNamespace(
            leader_agent=leader, thread_id="failed-search-report", capability_registry=registry,
            thread_dir=tmp_path, config=config,
        )
        report = generate_report_from_thread(runtime, topic="Retrieval report")
        saved = Path(report.artifact_path).read_text(encoding="utf-8")
        assert article in saved
        assert "Search failed" not in saved
        assert "unregistered type" not in caplog.text
        assert "Blocked deserialization" not in caplog.text
    finally:
        reset_checkpointer()

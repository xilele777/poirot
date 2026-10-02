from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from poirot.backend.agents.middlewares.evidence_middleware import EvidenceMiddleware
from poirot.backend.agents.middlewares.run_journal_middleware import _result_status
from poirot.backend.agents.middlewares.tool_call_middleware import ToolCallMiddleware


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("content,status", [
    ('{"error": "Search failed: No results found.", "query": "test"}', "success"),
    ('{"error": "upstream unavailable at https://example.test/search"}', "success"),
    ("Permission denied", "error"),
])
def test_failed_search_is_not_evidence_and_has_error_status(async_mode, content, status):
    request = SimpleNamespace(
        tool_call={"name": "web_search", "id": "call-1", "args": {}},
        state={"errors": []}, runtime=SimpleNamespace(thread_id="t1", run_id="r1", journal=None),
    )
    message = ToolMessage(content=content, status=status, name="web_search", tool_call_id="call-1")
    evidence, ledger = EvidenceMiddleware(), ToolCallMiddleware()

    if async_mode:
        async def leaf(req):
            return message
        async def inner(req):
            return await evidence.awrap_tool_call(req, leaf)
        result = asyncio.run(ledger.awrap_tool_call(request, inner))
    else:
        result = ledger.wrap_tool_call(request, lambda req: evidence.wrap_tool_call(req, lambda _: message))

    assert isinstance(result, Command)
    assert not result.update.get("observations")
    assert not result.update.get("sources")
    assert result.update["errors"][0].kind == "failure"
    assert result.update["messages"][0].status == "error"
    assert result.update["messages"][0].tool_call_id == "call-1"
    assert _result_status(result) == "error"


def test_successful_search_article_about_errors_remains_evidence():
    request = SimpleNamespace(
        tool_call={"name": "web_search", "id": "call-1", "args": {}},
        state={"errors": []}, runtime=SimpleNamespace(thread_id="t1", run_id="r1", journal=None),
    )
    content = '{"results": [{"url": "https://example.test/docs", "content": "How to debug forbidden / 403 / no results found errors"}]}'
    message = ToolMessage(content=content, name="web_search", tool_call_id="call-1")
    result = ToolCallMiddleware().wrap_tool_call(
        request, lambda req: EvidenceMiddleware().wrap_tool_call(req, lambda _: message),
    )
    assert len(result.update["observations"]) == 1
    assert len(result.update["sources"]) == 1
    assert result.update["errors"][0].kind == "success"
    assert result.update["messages"][0].status == "success"

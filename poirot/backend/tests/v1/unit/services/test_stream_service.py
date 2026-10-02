"""PoirotStreamClient 单测：custom mode 消费 compaction 事件。"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from poirot.backend.app.services.stream_service import PoirotStreamClient


class _FakeGraph:
    """假 graph：astream 产固定 (mode, chunk) 序列。"""

    def __init__(self, chunks: list) -> None:
        self._chunks = chunks

    async def astream(self, state: Any, config: Any = None, stream_mode: Any = None) -> AsyncIterator:
        for c in self._chunks:
            yield c


async def _drain(gen: AsyncIterator) -> list:
    out: list = []
    async for e in gen:
        out.append(e)
    return out


def test_custom_compaction_start_event() -> None:
    """custom mode compaction_start dict → StreamEvent(type=compaction_start, tool_name=P4)。"""
    graph = _FakeGraph([("custom", {"type": "compaction_start", "tool_name": "P4"})])
    client = PoirotStreamClient(graph, config={})
    events = asyncio.run(_drain(client.stream("Q")))
    starts = [e for e in events if e["type"] == "compaction_start"]
    assert len(starts) == 1
    assert starts[0]["tool_name"] == "P4"
    assert events[-1]["type"] == "done"  # astream 结束 yield done


def test_custom_no_type_skipped() -> None:
    """custom chunk 无 type 字段 → 跳过（不 yield），仅末尾 done。"""
    graph = _FakeGraph([("custom", {"foo": "bar"})])
    client = PoirotStreamClient(graph, config={})
    events = asyncio.run(_drain(client.stream("Q")))
    assert all(e["type"] != "compaction_start" for e in events)
    assert events[-1]["type"] == "done"


def test_custom_compaction_end_with_saved() -> None:
    """custom mode compaction_end 含 tool_result(saved) → StreamEvent 透传。"""
    graph = _FakeGraph([("custom", {"type": "compaction_end", "content": "summarize", "tool_result": "1800"})])
    client = PoirotStreamClient(graph, config={})
    events = asyncio.run(_drain(client.stream("Q")))
    ends = [e for e in events if e["type"] == "compaction_end"]
    assert len(ends) == 1
    assert ends[0]["content"] == "summarize"
    assert ends[0]["tool_result"] == "1800"


def test_budget_update_init_zero_frame_filtered() -> None:
    """init_budget 的全零快照（window=0）必须被过滤，避免 TUI 占用率闪烁到 0.0%。

    DefaultStrategy.before_agent → init_budget 会把 budget 重置成
    {total:0, fraction:0.0, window:0}，下一帧 values chunk 把这个零状态带出来。
    track() 跑过后 window 恒 > 0，所以用 window > 0 作为 init 帧的判定阈值。
    """
    init_frame = ("values", {"governance": {"default": {"budget": {
        "input": 0, "output": 0, "total": 0, "window": 0, "fraction": 0.0,
    }}}})
    real_frame = ("values", {"governance": {"default": {"budget": {
        "input": 100, "output": 50, "total": 150, "window": 128000, "fraction": 0.00117,
    }}}})
    graph = _FakeGraph([init_frame, real_frame])
    client = PoirotStreamClient(graph, config={})
    events = asyncio.run(_drain(client.stream("Q")))
    budgets = [e for e in events if e["type"] == "budget_update"]
    # init 帧被过滤，只剩 real 帧一条
    assert len(budgets) == 1
    assert budgets[0]["budget"]["total"] == 150
    assert budgets[0]["budget"]["window"] == 128000


def test_skills_selector_json_filtered_messages_mode() -> None:
    """SkillSelector LLM 输出 {"skills":[]} 通过 messages mode 必须被过滤。

    SkillSelector._llm_select 用 sync llm.invoke 选 skill，internal_llm tag 在
    async 流式 metadata 中可能丢失，content fallback 必须拦截 {"skills":...} JSON。
    """
    from langchain_core.messages import AIMessageChunk, HumanMessage
    chunk = (
        "messages",
        (
            AIMessageChunk(content='{"skills": []}', id="sel-1"),
            {"tags": []},
        ),
    )
    graph = _FakeGraph([chunk])
    client = PoirotStreamClient(graph, config={})
    events = asyncio.run(_drain(client.stream("Q")))
    answers = [e for e in events if e["type"] == "answer"]
    assert all('{"skills"' not in (e["content"] or "") for e in answers)


def test_skills_selector_json_with_prefix_filtered() -> None:
    """LLM 在 JSON 前加了解释文字（如 '没有匹配的 skill。\\n{"skills": []}'）也必须过滤。"""
    from langchain_core.messages import AIMessageChunk
    chunk = (
        "messages",
        (
            AIMessageChunk(content='根据任务没有匹配的 skill。\n{"skills": []}', id="sel-2"),
            {"tags": []},
        ),
    )
    graph = _FakeGraph([chunk])
    client = PoirotStreamClient(graph, config={})
    events = asyncio.run(_drain(client.stream("Q")))
    answers = [e for e in events if e["type"] == "answer"]
    assert all('{"skills"' not in (e["content"] or "") for e in answers)


def test_skills_selector_json_markdown_wrapped_filtered() -> None:
    """LLM 返回 markdown code fence 包裹的 JSON 也必须过滤。"""
    from langchain_core.messages import AIMessageChunk
    chunk = (
        "messages",
        (
            AIMessageChunk(content='```json\n{"skills": ["a"]}\n```', id="sel-3"),
            {"tags": []},
        ),
    )
    graph = _FakeGraph([chunk])
    client = PoirotStreamClient(graph, config={})
    events = asyncio.run(_drain(client.stream("Q")))
    answers = [e for e in events if e["type"] == "answer"]
    assert all('"skills"' not in (e["content"] or "") for e in answers)


def test_skills_selector_json_values_mode_filtered() -> None:
    """非流式模型走 values mode fallback 路径，{"skills":[]} 也必须被过滤。"""
    from langchain_core.messages import AIMessage, HumanMessage
    internal_msg = AIMessage(content='{"skills": []}', id="sel-4")
    graph = _FakeGraph([
        ("values", {"messages": [HumanMessage(content="Q")]}),
        ("values", {"messages": [internal_msg]}),
    ])
    client = PoirotStreamClient(graph, config={})
    events = asyncio.run(_drain(client.stream("Q")))
    answers = [e for e in events if e["type"] == "answer"]
    assert all('{"skills"' not in (e["content"] or "") for e in answers)


def test_normal_answer_not_filtered() -> None:
    """正常 agent 回答（不含 skills JSON）不被误过滤。"""
    from langchain_core.messages import AIMessageChunk
    chunk = (
        "messages",
        (
            AIMessageChunk(content='你好！我是 Poirot 研究助手。', id="ans-1"),
            {"tags": []},
        ),
    )
    graph = _FakeGraph([chunk])
    client = PoirotStreamClient(graph, config={})
    events = asyncio.run(_drain(client.stream("Q")))
    answers = [e for e in events if e["type"] == "answer"]
    assert any("Poirot" in (e["content"] or "") for e in answers)


def test_skills_json_split_across_chunks_filtered() -> None:
    """{"skills":[]} 跨多个 token delta 到达时也必须被过滤（实际 bug 场景）。

    SkillSelector llm.invoke 的输出在 messages mode 以 token delta 流式到达：
    delta1='{"', delta2='skills', delta3='": []}'。逐 delta 检测无法命中，
    必须按 msg_id 累积后判断。
    """
    from langchain_core.messages import AIMessageChunk
    chunks = [
        ("messages", (AIMessageChunk(content='{"', id="sel-5"), {"tags": []})),
        ("messages", (AIMessageChunk(content='skills', id="sel-5"), {"tags": []})),
        ("messages", (AIMessageChunk(content='": []}', id="sel-5"), {"tags": []})),
    ]
    graph = _FakeGraph(chunks)
    client = PoirotStreamClient(graph, config={})
    events = asyncio.run(_drain(client.stream("Q")))
    answers = [e for e in events if e["type"] == "answer"]
    # 所有 answer 事件都不应包含 skills JSON
    combined = "".join(e["content"] or "" for e in answers)
    assert '"skills"' not in combined


def test_skills_json_chunks_then_normal_answer() -> None:
    """selector JSON（多 chunk）+ agent 正常回答（不同 msg_id）：selector 被过滤，answer 保留。"""
    from langchain_core.messages import AIMessageChunk
    chunks = [
        ("messages", (AIMessageChunk(content='{"', id="sel-6"), {"tags": []})),
        ("messages", (AIMessageChunk(content='skills": []}', id="sel-6"), {"tags": []})),
        ("messages", (AIMessageChunk(content='Hello! I am Poirot.', id="ans-2"), {"tags": []})),
    ]
    graph = _FakeGraph(chunks)
    client = PoirotStreamClient(graph, config={})
    events = asyncio.run(_drain(client.stream("Q")))
    answers = [e for e in events if e["type"] == "answer"]
    combined = "".join(e["content"] or "" for e in answers)
    assert '"skills"' not in combined
    assert "Poirot" in combined


def test_answer_starting_with_brace_not_selector() -> None:
    """agent 回答以 { 开头但非 selector JSON（超 200 字符）→ buffer flush 不丢失。"""
    from langchain_core.messages import AIMessageChunk
    long_text = '{"data": "' + "x" * 250 + '"}'
    chunks = [
        ("messages", (AIMessageChunk(content=long_text, id="ans-3"), {"tags": []})),
    ]
    graph = _FakeGraph(chunks)
    client = PoirotStreamClient(graph, config={})
    events = asyncio.run(_drain(client.stream("Q")))
    answers = [e for e in events if e["type"] == "answer"]
    combined = "".join(e["content"] or "" for e in answers)
    assert "x" * 250 in combined


@pytest.mark.parametrize("final_mode", ["values", "messages"])
@pytest.mark.parametrize("answer", ["Hello world", '{"result": "ok"}'])
def test_response_id_and_chunk_id_share_one_answer(final_mode, answer) -> None:
    """Responses starts with its provider ID, then streams using a LangChain ID."""
    metadata = {"langgraph_checkpoint_ns": "model:call-1", "langgraph_step": 3}
    final = AIMessage(content=answer, id="resp-1")
    chunks = [
        ("values", {"messages": [HumanMessage(content="Q", id="human-1")]}),
        ("messages", (AIMessageChunk(content=[], id="resp-1", response_metadata={"id": "resp-1"}), metadata)),
        ("messages", (AIMessageChunk(content=[{"type": "text", "text": answer[:5]}], id="lc-run-1"), metadata)),
        ("messages", (AIMessageChunk(content=[{"type": "text", "text": answer[5:]}], id="lc-run-1"), metadata)),
        (final_mode, {"messages": [final]} if final_mode == "values" else (final, metadata)),
        ("values", {"messages": [final]}),
    ]
    events = asyncio.run(_drain(PoirotStreamClient(_FakeGraph(chunks), {}).stream("Q")))
    assert "".join(e["content"] for e in events if e["type"] == "answer") == answer


@pytest.mark.parametrize("initial", ["empty", "reasoning"])
def test_non_answer_chunks_do_not_hide_final_answer(initial) -> None:
    chunk = AIMessageChunk(
        content="", id="response-1",
        additional_kwargs={"reasoning_content": "Thinking"} if initial == "reasoning" else {},
        response_metadata={"id": "response-1"},
    )
    graph = _FakeGraph([
        ("values", {"messages": []}),
        ("messages", (chunk, {"langgraph_checkpoint_ns": "model:call-1"})),
        ("values", {"messages": [AIMessage(content="Final answer", id="response-1")]}),
    ])
    events = asyncio.run(_drain(PoirotStreamClient(graph, {}).stream("Q")))
    assert "".join(e["content"] for e in events if e["type"] == "answer") == "Final answer"


def test_same_text_from_separate_model_calls_is_not_deduplicated() -> None:
    chunks = [("values", {"messages": []})]
    for index in (1, 2):
        metadata = {"langgraph_checkpoint_ns": f"model:call-{index}", "langgraph_step": index}
        response_id = f"resp-{index}"
        chunks.extend([
            ("messages", (AIMessageChunk(content="", id=response_id, response_metadata={"id": response_id}), metadata)),
            ("messages", (AIMessageChunk(content="Again", id=f"lc-run-{index}"), metadata)),
            ("values", {"messages": [AIMessage(content="Again", id=response_id)]}),
        ])
    events = asyncio.run(_drain(PoirotStreamClient(_FakeGraph(chunks), {}).stream("Q")))
    assert [e["content"] for e in events if e["type"] == "answer"] == ["Again", "Again"]


def test_response_aliases_are_isolated_between_interleaved_calls() -> None:
    first = {"langgraph_checkpoint_ns": "model:first", "langgraph_step": 1}
    second = {"langgraph_checkpoint_ns": "model:second", "langgraph_step": 1}
    graph = _FakeGraph([
        ("values", {"messages": []}),
        ("messages", (AIMessageChunk(content="", id="resp-1", response_metadata={"id": "resp-1"}), first)),
        ("messages", (AIMessageChunk(content="", id="resp-2", response_metadata={"id": "resp-2"}), second)),
        ("messages", (AIMessageChunk(content="First", id="lc-run-1"), first)),
        ("messages", (AIMessageChunk(content="Second", id="lc-run-2"), second)),
        ("values", {"messages": [AIMessage(content="First", id="resp-1"), AIMessage(content="Second", id="resp-2")]}),
    ])
    events = asyncio.run(_drain(PoirotStreamClient(graph, {}).stream("Q")))
    assert [(e["msg_id"], e["content"]) for e in events if e["type"] == "answer"] == [
        ("resp-1", "First"), ("resp-2", "Second"),
    ]


def test_response_alias_ends_before_a_later_call_in_the_same_node() -> None:
    metadata = {"langgraph_checkpoint_ns": "model:call-1", "langgraph_step": 1}
    graph = _FakeGraph([
        ("values", {"messages": []}),
        ("messages", (AIMessageChunk(content="", id="resp-1", response_metadata={"id": "resp-1"}), metadata)),
        ("messages", (AIMessageChunk(content="First", id="lc-run-1", chunk_position="last"), metadata)),
        ("messages", (AIMessageChunk(content="", id="lc-run-2"), metadata)),
        ("values", {"messages": [AIMessage(content="First", id="resp-1"), AIMessage(content="Second", id="lc-run-2")]}),
    ])
    events = asyncio.run(_drain(PoirotStreamClient(graph, {}).stream("Q")))
    assert [e["content"] for e in events if e["type"] == "answer"] == ["First", "Second"]


def test_openai_responses_stream_renders_once_through_real_graph() -> None:
    """Exercise the installed SDK and LangGraph with an offline Responses SSE stream."""
    import json
    import httpx
    from langchain.agents import create_agent
    from langchain_openai import ChatOpenAI

    response = {
        "id": "resp-offline", "object": "response", "created_at": 1,
        "status": "completed", "model": "test-model", "error": None,
        "output": [{
            "id": "msg-offline", "type": "message", "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": "Hello world", "annotations": []}],
        }],
    }
    items = [
        {"type": "response.created", "response": {**response, "status": "in_progress", "output": []}},
        {"type": "response.output_text.delta", "item_id": "msg-offline", "output_index": 0, "content_index": 0, "delta": "Hello "},
        {"type": "response.output_text.delta", "item_id": "msg-offline", "output_index": 0, "content_index": 0, "delta": "world"},
        {"type": "response.output_text.done", "item_id": "msg-offline", "output_index": 0, "content_index": 0, "text": "Hello world"},
        {"type": "response.completed", "response": response},
    ]
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"},
            content="".join(f"event: {item['type']}\ndata: {json.dumps(item)}\n\n" for item in items),
        )

    async def run():
        transport = httpx.MockTransport(respond)
        with httpx.Client(transport=transport) as sync_http:
            async with httpx.AsyncClient(transport=transport) as async_http:
                model = ChatOpenAI(
                    model="test-model", api_key="offline-test-key", base_url="https://example.test/v1",
                    use_responses_api=True, http_client=sync_http, http_async_client=async_http,
                )
                return await _drain(PoirotStreamClient(create_agent(model), {}).stream("Q"))

    events = asyncio.run(run())
    assert len(requests) == 1
    assert requests[0].url.path == "/v1/responses"
    assert "".join(e["content"] for e in events if e["type"] == "answer") == "Hello world"

    from io import StringIO
    from rich.console import Console
    from poirot.backend.app.cli.stream_handler import StreamRenderer

    output = StringIO()
    renderer = StreamRenderer(Console(file=output, width=80))
    for event in events:
        renderer.render(event)
    assert output.getvalue().count("Hello world") == 1

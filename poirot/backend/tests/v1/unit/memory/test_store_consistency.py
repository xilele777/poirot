from dataclasses import replace
import multiprocessing
import time
from unittest.mock import Mock

import pytest

from poirot.backend.agents.memory.schema import MemoryTrace, MemoryType
from poirot.backend.agents.memory.strategies.default.store import MarkdownFileStore
from poirot.backend.agents.memory.strategies.default.retriever import HybridRetriever
from poirot.backend.agents.memory.strategies.default.decay import EbbinghausDecayPolicy
from poirot.backend.agents.memory.types import MemoryQuery


def trace(id, content="alpha"):
    return MemoryTrace(id=id, content=content, type=MemoryType.SEMANTIC, created_at=time.time())


def _writer(directory, prefix, ready):
    ready.wait(timeout=15)
    store = MarkdownFileStore(directory)
    for i in range(8):
        store.add(trace(f"{prefix}{i:x}"))


def test_independent_instances_keep_additions_updates_and_removals(tmp_path):
    a, b = MarkdownFileStore(tmp_path), MarkdownFileStore(tmp_path)
    a.add(trace("a1"))
    b.add(trace("b2"))
    a.update(trace("a1", "new"))
    assert b.get("a1").content == "new"
    assert a.get("b2") is not None
    b.remove("a1")
    assert a.get("a1") is None


def test_process_writers_do_not_lose_records(tmp_path):
    ctx = multiprocessing.get_context("spawn")
    ready = ctx.Barrier(2)
    processes = [ctx.Process(target=_writer, args=(str(tmp_path), prefix, ready)) for prefix in ("a", "b")]
    for process in processes:
        process.start()
    try:
        for process in processes:
            process.join(30)
            assert process.exitcode == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join()
    assert len(MarkdownFileStore(tmp_path).list_all()) == 16


def test_failed_atomic_replace_preserves_disk_and_cache(tmp_path, monkeypatch):
    store = MarkdownFileStore(tmp_path)
    store.add(trace("a1", "original"))
    before = (tmp_path / "traces.md").read_bytes()
    monkeypatch.setattr("poirot.backend.agents.memory.strategies.default.store.os.replace",
                        Mock(side_effect=OSError("replace failed")))
    with pytest.raises(OSError):
        store.update(trace("a1", "lost update"))
    assert (tmp_path / "traces.md").read_bytes() == before
    assert store.get("a1").content == "original"
    assert not list(tmp_path.glob(".traces-*"))


def test_retriever_sees_other_instance_changes(tmp_path):
    a, b = MarkdownFileStore(tmp_path), MarkdownFileStore(tmp_path)
    retriever = HybridRetriever(a, EbbinghausDecayPolicy())
    b.add(trace("a1", "alpha"))
    assert retriever.retrieve(MemoryQuery(text="alpha"))
    b.update(trace("a1", "beta"))
    assert not retriever.retrieve(MemoryQuery(text="alpha"))
    assert retriever.retrieve(MemoryQuery(text="beta"))
    b.remove("a1")
    assert not retriever.retrieve(MemoryQuery(text="beta"))


def test_stale_reinforcement_cannot_restore_modified_or_deleted_trace(tmp_path):
    a, b = MarkdownFileStore(tmp_path), MarkdownFileStore(tmp_path)
    original = trace("a1")
    a.add(original)
    expected = a.get("a1")
    b.update(replace(expected, content="edited by another writer"))
    assert not a.compare_and_update(expected, expected.with_strength(0.8, time.time()))
    assert a.get("a1").content == "edited by another writer"
    expected = a.get("a1")
    b.remove("a1")
    assert not a.compare_and_update(expected, expected.with_strength(0.8, time.time()))
    assert a.get("a1") is None

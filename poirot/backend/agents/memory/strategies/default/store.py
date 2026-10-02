"""Markdown truth source with locked read-modify-write and atomic replacement.

The sidecar lock coordinates independent processes. Cached reads refresh when
another writer replaces the data file. A single trace update remains replacement
semantics; this is not a transaction spanning multiple manager operations.
"""

from __future__ import annotations

import logging
import os
import tempfile
from contextlib import contextmanager
import re
import threading
import time
from pathlib import Path
from typing import Any

import yaml

from poirot.backend.agents.memory.exceptions import (
    MemoryConflictError,
    MemoryNotFoundError,
)
from poirot.backend.agents.memory.schema import (
    Association,
    MemoryTrace,
    MemoryType,
    OperationLog,
)
from poirot.backend.agents.memory.types import MemoryFilter
from poirot.backend.agents.storage.file_lock import exclusive_file_lock

logger = logging.getLogger(__name__)

# <!-- trace: {id} --> 分隔符，捕获 id + body（到下一个分隔符或文件尾）
_TRACE_SEPARATOR = re.compile(
    r"<!-- trace: ([\w-]+) -->\n(.*?)(?=<!-- trace:|$)", re.DOTALL
)


class MarkdownFileStore:
    """Markdown 文件持久化（00 §8.2 truth source）。

    单文件 traces.md + 内存索引 dict[str, MemoryTrace]。
    构造即就绪：读 storage_path/traces.md，解析所有 trace 建内存索引。
    文件锁：sidecar 排他锁覆盖跨进程读取和提交。
    """

    def __init__(self, storage_path: str | Path) -> None:
        """初始化：解析 storage_path + 加载 traces.md 建内存索引。

        Args:
            storage_path: Markdown 持久化根目录（相对路径锚定 cwd fallback，
                          Layer 4 bootstrap 传绝对路径锚定 _PROJECT_ROOT）
        """
        self._root = self._resolve_storage_path(storage_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._traces_file = self._root / "traces.md"
        self._lock = threading.Lock()  # 6B 文件锁（单进程）
        # 内存索引：trace_id → MemoryTrace（启动加载 + 增量维护）
        self._traces: dict[str, MemoryTrace] = {}
        self._signature = None
        with self._transaction():
            if not self._traces_file.exists():
                self._rewrite_file()

    def _resolve_storage_path(self, storage_path: str | Path) -> Path:
        """解析 storage_path（相对路径锚定 cwd fallback，01 D12）。

        Layer 4 bootstrap 负责传绝对路径（_resolve_relative_paths 锚定 _PROJECT_ROOT）。
        L3 fallback：相对路径用 Path.resolve() 锚定 cwd。
        """
        p = Path(storage_path)
        if p.is_absolute():
            return p
        return p.resolve()  # 相对路径锚定 cwd

    def _file_signature(self):
        try:
            stat = self._traces_file.stat()
            return stat.st_mtime_ns, stat.st_size, stat.st_ino
        except FileNotFoundError:
            return None

    def _load(self) -> None:
        traces: dict[str, MemoryTrace] = {}
        if self._traces_file.exists():
            # Called under the sidecar lock: signature and content belong to one revision.
            content = self._traces_file.read_text(encoding="utf-8")
            for match in _TRACE_SEPARATOR.finditer(content):
                trace = self._parse_trace(match.group(1), match.group(2).strip())
                if trace is not None:
                    traces[trace.id] = trace
        self._traces = traces
        self._signature = self._file_signature()

    @contextmanager
    def _transaction(self):
        with self._lock, exclusive_file_lock(self._root / "traces.lock"):
            self._load()
            try:
                yield
            except BaseException:
                self._load()  # discard an uncommitted in-memory update
                raise

    def _snapshot(self) -> dict[str, MemoryTrace]:
        with self._lock, exclusive_file_lock(self._root / "traces.lock"):
            if self._signature != self._file_signature():
                self._load()
            return dict(self._traces)

    def _parse_trace(self, trace_id: str, body: str) -> MemoryTrace | None:
        """解析单条 trace（frontmatter + content）→ MemoryTrace。

        格式：
        ---
        {yaml frontmatter：所有字段除 content}
        ---
        {content 正文}

        容错（2A）：yaml 解析失败 / 字段缺失 / 类型错时 log warning + 返 None（跳过）。
        associations/operation_log list → tuple（MemoryTrace frozen 要求）。
        embedding list → tuple 或 None。
        type string → MemoryType 枚举。
        """
        try:
            # 分离 frontmatter + content
            if not body.startswith("---\n"):
                logger.warning("trace %s missing frontmarker, skipped", trace_id)
                return None
            parts = body[4:].split("\n---\n", 1)
            if len(parts) != 2:
                logger.warning("trace %s malformed frontmatter, skipped", trace_id)
                return None
            frontmatter_text, content = parts
            data = yaml.safe_load(frontmatter_text)
            if not isinstance(data, dict):
                logger.warning("trace %s frontmatter not dict, skipped", trace_id)
                return None

            # 必填字段校验
            if "id" not in data or "type" not in data:
                logger.warning("trace %s missing id/type, skipped", trace_id)
                return None

            # type string → MemoryType 枚举
            type_val = data.pop("type")
            mem_type = MemoryType(type_val) if not isinstance(type_val, MemoryType) else type_val

            # associations list[dict] → tuple[Association]
            assocs_data = data.pop("associations", [])
            associations = tuple(
                Association(**a) for a in assocs_data
            ) if assocs_data else ()

            # operation_log list[dict] → tuple[OperationLog]
            log_data = data.pop("operation_log", [])
            operation_log = tuple(
                OperationLog(**log) for log in log_data
            ) if log_data else ()

            # embedding list → tuple 或 None
            embedding = data.pop("embedding", None)
            if embedding is not None:
                embedding = tuple(embedding)

            return MemoryTrace(
                content=content,
                type=mem_type,
                associations=associations,
                operation_log=operation_log,
                embedding=embedding,
                **data,
            )
        except Exception as exc:
            logger.warning("Failed to parse trace %s: %s", trace_id, exc)
            return None

    def _serialize_trace(self, trace: MemoryTrace) -> str:
        """序列化 MemoryTrace → frontmatter + content 字符串。

        frontmatter（YAML）：所有字段除 content（content 放正文）。
        手动构建 dict 避免 yaml python/tuple tag（safe_load 不认）：
        MemoryType → value string；associations/operation_log tuple → list；
        embedding tuple → list 或 None；diff tuple → list。
        """
        data = {
            "id": trace.id,
            "type": trace.type.value,
            "strength": trace.strength,
            "base_strength": trace.base_strength,
            "decay_rate": trace.decay_rate,
            "access_count": trace.access_count,
            "last_accessed": trace.last_accessed,
            "importance": trace.importance,
            "associations": [
                {"target_id": a.target_id, "strength": a.strength, "type": a.type}
                for a in trace.associations
            ],
            "embedding": list(trace.embedding) if trace.embedding is not None else None,
            "source": trace.source,
            "created_at": trace.created_at,
            "metadata": trace.metadata,
            "operation_log": [
                {
                    "timestamp": log.timestamp,
                    "operation": log.operation,
                    "actor": log.actor,
                    "diff": self._diff_to_serializable(log.diff),
                }
                for log in trace.operation_log
            ],
        }
        frontmatter = yaml.dump(
            data, default_flow_style=False, allow_unicode=True, sort_keys=False
        ).strip()
        return f"---\n{frontmatter}\n---\n{trace.content}"

    @staticmethod
    def _diff_to_serializable(diff: dict[str, Any] | None) -> dict[str, Any] | None:
        """OperationLog.diff tuple → list（yaml safe_load 兼容）。"""
        if diff is None:
            return None
        result: dict[str, Any] = {}
        for k, v in diff.items():
            if isinstance(v, tuple):
                result[k] = list(v)
            else:
                result[k] = v
        return result

    def add(self, trace: MemoryTrace) -> None:
        """新增记忆。trace.id 已存在抛 MemoryConflictError。

        6B 文件锁保护：并发 add 序列化。
        """
        if not re.fullmatch(r"[\w-]+", trace.id):
            raise ValueError("trace id must contain only letters, digits, underscores or hyphens")
        with self._transaction():
            if trace.id in self._traces:
                raise MemoryConflictError(
                    f"trace already exists: {trace.id}",
                    old_id=trace.id, new_id=trace.id,
                )
            self._traces[trace.id] = trace
            self._rewrite_file()

    def get(self, trace_id: str) -> MemoryTrace | None:
        """按 id 取记忆，不存在返 None。"""
        return self._snapshot().get(trace_id)

    def _rewrite_file(self) -> None:
        """Serialize fully before touching disk; replace only a flushed complete file."""
        content = "# Memory Traces\n\n" + "".join(
            f"<!-- trace: {trace.id} -->\n{self._serialize_trace(trace)}\n\n"
            for trace in self._traces.values()
        )
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                             dir=self._root, prefix=".traces-", delete=False) as f:
                temporary = Path(f.name)
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, self._traces_file)
            # YAML normalizes e.g. operation-log tuple values to lists. Cache the
            # committed representation so conditional updates compare like with like.
            self._load()
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def update(self, trace: MemoryTrace) -> None:
        """更新记忆（frozen 语义：替换）。trace.id 不存在抛 MemoryNotFoundError。

        锁内重读最新文件，再替换指定 trace，保留其他实例新增的记录。
        """
        with self._transaction():
            if trace.id not in self._traces:
                raise MemoryNotFoundError(trace.id)
            self._traces[trace.id] = trace
            self._rewrite_file()

    def compare_and_update(self, expected: MemoryTrace, updated: MemoryTrace) -> bool:
        """Commit a retrieval reinforcement only if the trace has not changed."""
        if expected.id != updated.id:
            raise ValueError("compare-and-update cannot change a trace id")
        with self._transaction():
            if self._traces.get(expected.id) != expected:
                return False
            self._traces[updated.id] = updated
            self._rewrite_file()
            return True

    def batch_update(self, traces: list[MemoryTrace]) -> None:
        """批量更新（F2 决策，consolidate 标记 N 条旧 trace forgotten 用）。

        原子性：任一 trace.id 不存在抛 MemoryNotFoundError（全成功或全失败）。
        一次 _rewrite_file 全量重写（非 N 次 O(N²)）。
        6B 文件锁保护（与 update 同锁）。
        """
        with self._transaction():
            for trace in traces:
                if trace.id not in self._traces:
                    raise MemoryNotFoundError(trace.id)
            for trace in traces:
                self._traces[trace.id] = trace
            self._rewrite_file()

    def remove(self, trace_id: str) -> None:
        """删除记忆。不存在静默（幂等）。"""
        with self._transaction():
            if trace_id in self._traces:
                del self._traces[trace_id]
                self._rewrite_file()

    def list_by_type(self, type: MemoryType) -> list[MemoryTrace]:
        """按类型列出。"""
        type_key = type.value if isinstance(type, MemoryType) else str(type)
        return [t for t in self._snapshot().values() if t.type.value == type_key]

    def list_by_filter(self, filter: MemoryFilter) -> list[MemoryTrace]:
        """按过滤器列出（7A 粗筛 + 调用方精算 strength）。

        7A：store 只按 max_age_hours / type / metadata 粗筛（内存索引），
        strength 精算由调用方（forget_policy）逐条 compute_strength。
        """
        result = list(self._snapshot().values())
        # type 过滤
        if filter.type_filter is not None:
            type_key = (
                filter.type_filter.value
                if isinstance(filter.type_filter, MemoryType)
                else str(filter.type_filter)
            )
            result = [t for t in result if t.type.value == type_key]
        # max_age_hours 粗筛（按 last_accessed，<=0 用 created_at，7A）
        if filter.max_age_hours is not None:
            now = time.time()
            max_age_seconds = filter.max_age_hours * 3600.0
            result = [
                t for t in result
                if (now - (t.last_accessed if t.last_accessed > 0 else t.created_at)) <= max_age_seconds
            ]
        # metadata 过滤（全匹配）
        if filter.metadata_filter:
            result = [
                t for t in result
                if all(t.metadata.get(k) == v for k, v in filter.metadata_filter.items())
            ]
        return result

    def list_all(self) -> list[MemoryTrace]:
        """列出全部。"""
        return list(self._snapshot().values())
